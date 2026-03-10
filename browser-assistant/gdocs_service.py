"""
Google Docs Service - OAuth2 based
Creates richly formatted Google Docs WITHOUT using namedStyleType,
because heading named styles override custom colors with theme defaults.
All formatting is applied directly via updateTextStyle + updateParagraphStyle.

Color scheme:
  Title:    Deep Purple #7C4DD3
  Heading:  Google Blue #4285F4
  Key Pts:  Green       #34A853
  Concl.:   Orange      #EA8650
  Meta/URL: Gray        #6C7086
  Footer:   Light gray  #828296
  Body:     Dark        #1E1E2E
"""
import re
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

BASE_DIR = Path(__file__).parent
CLIENT_SECRET_FILE = BASE_DIR / "google_client_secret.json"
TOKEN_FILE = BASE_DIR / "google_token.json"

# ── Color helpers ──────────────────────────────────────────────────────────────

def _rgb(r: int, g: int, b: int) -> dict:
    return {"red": r / 255, "green": g / 255, "blue": b / 255}

COLOR_TITLE   = _rgb(124, 77,  211)   # deep purple
COLOR_HEADING = _rgb(66,  133, 244)   # Google blue
COLOR_ACCENT  = _rgb(52,  168, 83)    # green  (Key Points)
COLOR_ORANGE  = _rgb(234, 134, 80)    # orange (Conclusion)
COLOR_URL     = _rgb(108, 112, 134)   # muted gray
COLOR_FOOTER  = _rgb(130, 130, 150)   # soft gray
COLOR_BODY    = _rgb(30,  30,  46)    # near-black

# ── Auth ───────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(
                    f"Google OAuth client secret not found at: {CLIENT_SECRET_FILE}\n"
                    "Download from Google Cloud Console → APIs & Services → Credentials "
                    "→ OAuth 2.0 Client IDs → Download JSON, rename to 'google_client_secret.json'."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(port=8085)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


# ── Document Builder ───────────────────────────────────────────────────────────

class _DocBuilder:
    """
    Builds Google Docs API batchUpdate requests.
    Key design: we NEVER use namedStyleType, because applying a named heading
    style causes Docs to re-apply its theme colors, overwriting custom colors.
    Instead, all formatting (size, bold, color) is done via updateTextStyle.
    """

    def __init__(self):
        self.requests: list[dict] = []
        self.index = 1  # Google Docs body starts at index 1

    # ── Low-level primitives ───────────────────────────────────────────────────

    def _insert(self, text: str) -> tuple[int, int]:
        start = self.index
        self.requests.append({
            "insertText": {"location": {"index": start}, "text": text}
        })
        self.index += len(text)
        return start, self.index

    def _text_style(self, start: int, end: int,
                    bold: bool = False,
                    italic: bool = False,
                    underline: bool = False,
                    font_size: float = 11,
                    font: str = "Arial",
                    color: dict | None = None):
        """Apply character-level styling to [start, end)."""
        style: dict = {
            "bold": bold,
            "italic": italic,
            "underline": underline,
            "fontSize": {"magnitude": font_size, "unit": "PT"},
            "weightedFontFamily": {"fontFamily": font},
        }
        fields = "bold,italic,underline,fontSize,weightedFontFamily"

        if color:
            style["foregroundColor"] = {"color": {"rgbColor": color}}
            fields += ",foregroundColor"

        self.requests.append({
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "textStyle": style,
                "fields": fields,
            }
        })

    def _para_style(self, start: int, end: int,
                    alignment: str = "START",
                    space_above: float = 0,
                    space_below: float = 0,
                    indent_start: float | None = None):
        """Apply paragraph-level styling (NO namedStyleType — avoids color override)."""
        style: dict = {
            "alignment": alignment,
            "spaceAbove": {"magnitude": space_above, "unit": "PT"},
            "spaceBelow": {"magnitude": space_below, "unit": "PT"},
        }
        fields = "alignment,spaceAbove,spaceBelow"
        if indent_start is not None:
            style["indentStart"] = {"magnitude": indent_start, "unit": "PT"}
            fields += ",indentStart"

        self.requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": style,
                "fields": fields,
            }
        })

    def _bullet(self, start: int, end: int):
        self.requests.append({
            "createParagraphBullets": {
                "range": {"startIndex": start, "endIndex": end},
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }
        })

    # ── High-level section methods ─────────────────────────────────────────────

    def add_title(self, text: str):
        """Big centered purple title."""
        line = text + "\n"
        s, e = self._insert(line)
        self._para_style(s, e, alignment="CENTER", space_below=6)
        self._text_style(s, e - 1, bold=True, font_size=24,
                         color=COLOR_TITLE, font="Google Sans")

    def add_meta(self, label: str, value: str):
        """Small metadata line (e.g. Source: https://...)."""
        line = f"{label}{value}\n"
        s, e = self._insert(line)
        lbl_end = s + len(label)
        self._para_style(s, e, alignment="CENTER", space_above=2, space_below=2)
        self._text_style(s, lbl_end,  bold=True,  font_size=9, color=COLOR_URL)
        self._text_style(lbl_end, e - 1, italic=True, font_size=9, color=COLOR_URL)

    def add_divider(self):
        """A horizontal rule made of em-dashes."""
        line = "─" * 55 + "\n"
        s, e = self._insert(line)
        self._para_style(s, e, alignment="CENTER", space_above=8, space_below=8)
        self._text_style(s, e - 1, font_size=8, color=COLOR_URL)

    def add_section_heading(self, text: str, color: dict | None = None):
        """Coloured, bold section heading — NO namedStyleType."""
        line = text + "\n"
        s, e = self._insert(line)
        self._para_style(s, e, space_above=16, space_below=4)
        self._text_style(s, e - 1, bold=True, font_size=14,
                         color=color or COLOR_HEADING, font="Google Sans")

    def add_body(self, text: str, italic: bool = False):
        """Regular paragraph text."""
        if not text.strip():
            return
        line = text.strip() + "\n"
        s, e = self._insert(line)
        self._para_style(s, e, space_above=0, space_below=4)
        self._text_style(s, e - 1, italic=italic, font_size=11,
                         color=COLOR_BODY, font="Arial")

    def add_bullet(self, text: str):
        """A single disc-bullet item."""
        text = text.lstrip("-•* \t").strip()
        if not text:
            return
        line = text + "\n"
        s, e = self._insert(line)
        self._para_style(s, e, space_above=2, space_below=2)
        self._text_style(s, e - 1, font_size=11, color=COLOR_BODY, font="Arial")
        self._bullet(s, e)

    def add_footer(self, url: str):
        self.add_divider()
        line = f"Source: {url}\nSummarized by Web Chat AI\n"
        s, e = self._insert(line)
        self._para_style(s, e, alignment="CENTER", space_above=0, space_below=0)
        self._text_style(s, e - 1, italic=True, font_size=8, color=COLOR_FOOTER)


# ── Markdown parser ─────────────────────────────────────────────────────────────

def _parse_and_build(builder: _DocBuilder, title: str,
                     summary_md: str, source_url: str):
    SECTION_COLORS = {
        "overview":   COLOR_HEADING,
        "key points": COLOR_ACCENT,
        "conclusion": COLOR_ORANGE,
    }

    builder.add_title(title)
    builder.add_meta("Source: ", source_url)
    builder.add_divider()

    for raw_line in summary_md.splitlines():
        line = raw_line.strip()

        if line.startswith("## "):          # skip duplicate top heading
            continue

        if line.startswith("### "):         # section headings
            heading = line[4:].strip()
            color = SECTION_COLORS.get(heading.lower(), COLOR_HEADING)
            builder.add_section_heading(heading, color=color)
            continue

        if line.startswith(("**URL:**", "**Url:**")):
            continue                        # already in header meta

        if line.startswith(("- ", "* ", "• ")):
            builder.add_bullet(line)
            continue

        if re.match(r"^\d+\.\s", line):     # numbered list
            builder.add_bullet(re.sub(r"^\d+\.\s*", "", line))
            continue

        if not line:
            continue

        # Strip inline bold/italic markers from body text
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        clean = re.sub(r"\*(.+?)\*",     r"\1", clean)
        clean = re.sub(r"__(.+?)__",     r"\1", clean)
        builder.add_body(clean)

    builder.add_footer(source_url)


# ── Public API ─────────────────────────────────────────────────────────────────

def create_google_doc(title: str, summary_md: str, source_url: str = "") -> str:
    """
    Create a richly formatted Google Doc from a markdown summary.
    Returns the Google Docs edit URL.
    """
    creds = _get_credentials()
    docs_service = build("docs", "v1", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)

    # Create blank document
    doc = docs_service.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # Build and apply all formatting in one batchUpdate
    builder = _DocBuilder()
    _parse_and_build(builder, title, summary_md, source_url)

    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": builder.requests},
    ).execute()

    # Anyone with the link can view
    drive_service.permissions().create(
        fileId=doc_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return f"https://docs.google.com/document/d/{doc_id}/edit"

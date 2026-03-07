from youtube_transcript_api import YouTubeTranscriptApi
import re


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_transcript(video_id: str) -> list[dict] | None:
    """
    Fetch transcript using youtube_transcript_api.
    Returns list of {text, start, duration} dicts.
    """
    try:
        api = YouTubeTranscriptApi()
        response = api.fetch(video_id=video_id, languages=["en", "hi"])

        entries = []
        for snippet in response.snippets:
            text = snippet.text.strip()
            if not text:
                continue
            entries.append({
                "text":     text,
                "start":    round(snippet.start, 2),
                "duration": round(snippet.duration, 2),
            })

        return entries if entries else None

    except Exception as e:
        print(f"[YouTube] Transcript fetch error: {e}")
        return None


def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS format."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_timed_chunks(entries: list[dict], chunk_size: int = 30) -> list[dict]:
    """
    Group transcript entries into chunks of ~chunk_size entries.
    Each chunk has: text, start_time, end_time, timestamp_label
    """
    if not entries:
        return []

    chunks = []
    for i in range(0, len(entries), chunk_size):
        group      = entries[i:i + chunk_size]
        text       = " ".join(e["text"] for e in group)
        start_time = group[0]["start"]
        end_time   = group[-1]["start"] + group[-1].get("duration", 2)

        chunks.append({
            "text":            text,
            "start_time":      start_time,
            "end_time":        end_time,
            "timestamp_label": format_timestamp(start_time),
        })

    return chunks
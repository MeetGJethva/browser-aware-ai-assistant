from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from models import URLRequest, ChatRequest, ChatResponse
from browser_manager import browser_manager
from llm_service import get_answer
from fastapi.responses import HTMLResponse, Response
from playwright.async_api import async_playwright
from urllib.parse import urljoin, urlparse, quote, unquote
import httpx
import uvicorn
import re
import base64

@asynccontextmanager
async def lifespan(app: FastAPI):
    await browser_manager.start()
    yield
    await browser_manager.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/load-url")
async def load_url(data: URLRequest):
    await browser_manager.load_url(data.url)
    return {"status": "loaded", "url": data.url}

@app.post("/chat", response_model=ChatResponse)
async def chat(data: ChatRequest):
    # Use extension-provided context if available, else use browser_manager's
    context = data.context or browser_manager.page_text or ""
    answer = get_answer(context, data.message)
    return ChatResponse(answer=answer)


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

# Cache for resources to avoid re-fetching
resource_cache: dict[str, tuple[bytes, str]] = {}


def get_proxy_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def rewrite_html(html: str, page_url: str, proxy_base: str) -> str:
    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    def make_proxy(url: str) -> str:
        if not url:
            return url
        url = url.strip()
        if url.startswith(("javascript:", "data:", "blob:", "#", "mailto:", "tel:")):
            return url
        if url.startswith("//"):
            url = parsed.scheme + ":" + url
        elif url.startswith("/"):
            url = origin + url
        elif not url.startswith("http"):
            url = urljoin(page_url, url)
        return f"{proxy_base}/resource?url={quote(url, safe='')}"

    # Rewrite srcset
    def rewrite_srcset(srcset: str) -> str:
        parts = srcset.split(",")
        result = []
        for part in parts:
            part = part.strip()
            tokens = part.split()
            if tokens:
                tokens[0] = make_proxy(tokens[0])
            result.append(" ".join(tokens))
        return ", ".join(result)

    # Rewrite all attribute URLs
    def rewrite_attr(match):
        full = match.group(0)
        attr = match.group(1)
        val = match.group(2)
        quote_char = match.group(3) if len(match.groups()) >= 3 else '"'

        if attr.lower() == "srcset":
            new_val = rewrite_srcset(val)
        else:
            new_val = make_proxy(val)
        
        return full.replace(val, new_val, 1)

    # Match href, src, action, srcset attributes
    html = re.sub(
        r'(href|src|action|srcset)=(["\'])([^"\']*)\2',
        lambda m: f'{m.group(1)}={m.group(2)}{(rewrite_srcset(m.group(3)) if m.group(1).lower()=="srcset" else make_proxy(m.group(3)))}{m.group(2)}',
        html,
        flags=re.IGNORECASE
    )

    # Rewrite url() in inline styles
    def rewrite_style_url(match):
        url_val = match.group(1).strip("'\"")
        return f"url('{make_proxy(url_val)}')"

    html = re.sub(r"url\(['\"]?([^)'\"]+)['\"]?\)", rewrite_style_url, html)

    # Remove security headers
    html = re.sub(r'<meta[^>]*http-equiv=["\']Content-Security-Policy["\'][^>]*/?>',
                  '', html, flags=re.IGNORECASE)
    html = re.sub(r'<meta[^>]*http-equiv=["\']X-Frame-Options["\'][^>]*/?>',
                  '', html, flags=re.IGNORECASE)

    # Inject interception script right after <head> or at start
    injection = f"""<script>
(function() {{
    const PROXY_BASE = '{proxy_base}';
    const PAGE_URL = '{page_url}';
    const ORIGIN = '{origin}';

    function toResource(url) {{
        if (!url || typeof url !== 'string') return url;
        url = url.trim();
        if (url.startsWith('javascript:') || url.startsWith('data:') ||
            url.startsWith('blob:') || url.startsWith('#') ||
            url.includes(PROXY_BASE)) return url;
        try {{
            if (url.startsWith('//')) url = '{parsed.scheme}:' + url;
            else if (url.startsWith('/')) url = ORIGIN + url;
            else if (!url.startsWith('http')) url = new URL(url, PAGE_URL).href;
        }} catch(e) {{ return url; }}
        return PROXY_BASE + '/resource?url=' + encodeURIComponent(url);
    }}

    function toPage(url) {{
        if (!url || typeof url !== 'string') return url;
        url = url.trim();
        if (url.startsWith('javascript:') || url.startsWith('data:') || url.startsWith('blob:') || url.startsWith('#')) return url;
        if (url.includes(PROXY_BASE)) return url;
        try {{
            if (url.startsWith('//')) url = '{parsed.scheme}:' + url;
            else if (url.startsWith('/')) url = ORIGIN + url;
            else if (!url.startsWith('http')) url = new URL(url, PAGE_URL).href;
        }} catch(e) {{ return url; }}
        return PROXY_BASE + '/proxy?url=' + encodeURIComponent(url);
    }}

    // Override fetch
    const _fetch = window.fetch;
    window.fetch = function(input, init) {{
        if (typeof input === 'string') input = toResource(input);
        else if (input instanceof Request) input = new Request(toResource(input.url), input);
        return _fetch.call(this, input, init);
    }};

    // Override XHR
    const _open = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {{
        return _open.call(this, method, toResource(String(url)), ...rest);
    }};

    // Intercept all clicks
    document.addEventListener('click', function(e) {{
        const a = e.target.closest('a[href]');
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || href.startsWith('javascript:') || href.startsWith('#')) return;
        e.preventDefault();
        e.stopPropagation();
        const newUrl = toPage(href);
        window.parent.postMessage({{ type: 'NAVIGATE', url: a.href }}, '*');
        window.location.href = newUrl;
    }}, true);

    // Override history
    const _push = history.pushState.bind(history);
    const _replace = history.replaceState.bind(history);
    history.pushState = (s, t, url) => _push(s, t, url ? toPage(String(url)) : url);
    history.replaceState = (s, t, url) => _replace(s, t, url ? toPage(String(url)) : url);

    // Patch window.open
    const _open2 = window.open;
    window.open = function(url, ...args) {{
        if (url) url = toPage(String(url));
        return _open2.call(this, url, ...args);
    }};

    console.log('[Proxy] Injection active for', PAGE_URL);
}})();
</script>"""

    if "<head>" in html:
        html = html.replace("<head>", f"<head>{injection}", 1)
    elif "<html>" in html:
        html = html.replace("<html>", f"<html>{injection}", 1)
    else:
        html = injection + html

    return html


@app.get("/proxy")
async def proxy(url: str, request: Request):
    """Fetch and render full page using Playwright, then rewrite URLs."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    proxy_base = get_proxy_base(request)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )

            # Remove automation fingerprint
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait a bit for JS to settle
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except:
                pass

            # Get the fully rendered HTML
            html = await page.content()
            final_url = page.url  # may have redirected

            await browser.close()

        html = rewrite_html(html, final_url, proxy_base)
        return HTMLResponse(content=html)

    except Exception as e:
        return HTMLResponse(
            content=f"""<html><body style='font-family:sans-serif;padding:40px'>
                <h2>⚠️ Failed to load page</h2>
                <p><b>URL:</b> {url}</p>
                <p><b>Error:</b> {str(e)}</p>
            </body></html>""",
            status_code=500
        )


@app.get("/resource")
async def resource(url: str, request: Request):
    """Proxy all static resources (images, CSS, JS, fonts, etc.)"""
    url = unquote(url)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Check cache
    if url in resource_cache:
        content, content_type = resource_cache[url]
        return Response(content=content, media_type=content_type)

    proxy_base = get_proxy_base(request)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20,
            verify=False,
            headers=BROWSER_HEADERS,
        ) as client:
            resp = await client.get(url)

            content_type = resp.headers.get("content-type", "application/octet-stream")
            content = resp.content

            # If it's CSS, rewrite url() references inside it too
            if "text/css" in content_type:
                css_text = resp.text
                parsed = urlparse(url)
                origin = f"{parsed.scheme}://{parsed.netloc}"

                def rewrite_css_url(match):
                    u = match.group(1).strip("'\"")
                    if u.startswith("data:") or u.startswith("//") or u.startswith("http"):
                        pass
                    elif u.startswith("/"):
                        u = origin + u
                    else:
                        u = urljoin(url, u)
                    return f"url('{proxy_base}/resource?url={quote(u, safe='')}')"

                css_text = re.sub(r"url\(['\"]?([^)'\"]+)['\"]?\)", rewrite_css_url, css_text)
                content = css_text.encode("utf-8")

            # Strip security headers
            excluded = {
                "content-security-policy", "x-frame-options",
                "content-encoding", "transfer-encoding",
                "content-length", "strict-transport-security"
            }
            headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
            headers["Access-Control-Allow-Origin"] = "*"

            # Cache non-HTML resources
            if "text/html" not in content_type:
                resource_cache[url] = (content, content_type)

            return Response(content=content, media_type=content_type, headers=headers)

    except Exception as e:
        return Response(content=b"", status_code=404)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)
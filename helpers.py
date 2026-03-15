import base64
import random
import string
import time
import requests
from io import BytesIO
from PIL import Image
from config import GROK_API_KEY, GROK_MODEL, WP_BASE_URL, WP_USERNAME, WP_APP_PASS

CHARS = string.ascii_uppercase + string.digits


def random_sku():
    return "".join(random.choices(CHARS, k=3)) + "-" + "".join(random.choices(CHARS, k=3))


def generate_pattern(prompt, api_key=None, log=None):
    key = api_key or GROK_API_KEY
    if not key:
        raise RuntimeError("No Grok API key provided.")

    def _log(msg):
        if log: log(msg)

    _log(f"  → POST https://api.x.ai/v1/images/generations")
    _log(f"  → Model: {GROK_MODEL}  |  Prompt: {prompt[:60]}...")

    try:
        resp = requests.post(
            "https://api.x.ai/v1/images/generations",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
            },
            json={
                "model":           GROK_MODEL,
                "prompt":          prompt,
                "n":               1,
                "response_format": "b64_json",
            },
            timeout=(10, 120),
        )
    except requests.exceptions.ConnectTimeout:
        raise RuntimeError("Grok API: connection timed out (10s). Possible network block.")
    except requests.exceptions.ReadTimeout:
        raise RuntimeError("Grok API: read timed out after 120s.")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Grok API: cannot connect — {e}")

    _log(f"  → HTTP {resp.status_code}")
    _log(f"  → Response: {resp.text[:500]}")

    if resp.status_code == 401:
        raise RuntimeError("Grok API: 401 Unauthorized — check your API key.")
    if resp.status_code == 403:
        raise RuntimeError("Grok API: 403 Forbidden — key may not have image generation access.")
    if resp.status_code == 404:
        raise RuntimeError(f"Grok API: 404 — model '{GROK_MODEL}' not found.")
    if resp.status_code == 429:
        raise RuntimeError("Grok API: 429 Rate limit hit.")
    if resp.status_code != 200:
        raise RuntimeError(f"Grok API: HTTP {resp.status_code} — {resp.text[:200]}")

    try:
        result = resp.json()
    except Exception:
        raise RuntimeError(f"Grok API: response is not valid JSON — {resp.text[:200]}")

    if "error" in result:
        raise RuntimeError(f"Grok API error: {result['error']}")
    if "data" not in result or not result["data"]:
        raise RuntimeError(f"Grok API: no image data — {str(result)[:200]}")

    item = result["data"][0]
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
    elif "url" in item:
        _log(f"  → Downloading image from URL...")
        img_bytes = requests.get(item["url"], timeout=(10, 60)).content
    else:
        raise RuntimeError(f"Grok API: unknown response format — {str(item)[:200]}")

    _log(f"  → Image received ({len(img_bytes)//1024} KB)")
    return Image.open(BytesIO(img_bytes)).convert("RGBA")


def upload_to_wordpress(file_path, filename, log=None, retries=3, retry_delay=5):
    """
    Upload PNG to WordPress with retry on timeout/connection errors.

    retries     : number of attempts total
    retry_delay : seconds to wait between attempts
    """
    def _log(msg):
        if log: log(msg)

    with open(file_path, "rb") as f:
        data = f.read()

    size_kb = len(data) // 1024
    url = f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/media"

    for attempt in range(1, retries + 1):
        try:
            _log(f"    → Uploading {filename} ({size_kb} KB), attempt {attempt}/{retries}...")
            resp = requests.post(
                url,
                auth=(WP_USERNAME, WP_APP_PASS),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type":        "image/png",
                },
                data=data,
                timeout=(15, 120),   # 15s connect, 120s to finish upload
            )

            if resp.status_code in (200, 201):
                src_url = resp.json()["source_url"]
                _log(f"    → Uploaded OK ({resp.status_code})")
                return src_url

            # Non-retryable errors
            if resp.status_code in (400, 401, 403):
                raise RuntimeError(
                    f"WordPress upload failed ({resp.status_code}): {resp.text[:200]}"
                )

            # Server errors — retry
            _log(f"    → HTTP {resp.status_code} — will retry in {retry_delay}s...")

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            _log(f"    → Connection error on attempt {attempt}: {e}")
            if attempt == retries:
                raise RuntimeError(
                    f"WordPress upload failed after {retries} attempts: {e}"
                )

        if attempt < retries:
            time.sleep(retry_delay)

    raise RuntimeError(f"WordPress upload failed after {retries} attempts.")

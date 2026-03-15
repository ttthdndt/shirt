import base64
import random
import string
import requests
from io import BytesIO
from PIL import Image
from config import GROK_API_KEY, GROK_MODEL, WP_BASE_URL, WP_USERNAME, WP_APP_PASS

CHARS = string.ascii_uppercase + string.digits


def random_sku():
    return "".join(random.choices(CHARS, k=3)) + "-" + "".join(random.choices(CHARS, k=3))


def generate_pattern(prompt, api_key=None, log=None):
    """
    Call Grok image API. Logs every step so you can see exactly where it fails.
    timeout=(10, 120) = 10s to connect, 120s to read response.
    """
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
            timeout=(10, 120),   # (connect timeout, read timeout)
        )
    except requests.exceptions.ConnectTimeout:
        raise RuntimeError("Grok API: connection timed out (10s). Server may be blocking outbound requests to api.x.ai.")
    except requests.exceptions.ReadTimeout:
        raise RuntimeError("Grok API: read timed out after 120s. The API did not respond in time.")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Grok API: cannot connect to api.x.ai — {e}")

    _log(f"  → HTTP {resp.status_code}")

    # Log raw response for debugging (truncated)
    try:
        raw = resp.text[:500]
        _log(f"  → Response: {raw}")
    except Exception:
        pass

    if resp.status_code == 401:
        raise RuntimeError("Grok API: 401 Unauthorized — check your API key.")
    if resp.status_code == 403:
        raise RuntimeError("Grok API: 403 Forbidden — your key may not have image generation access.")
    if resp.status_code == 404:
        raise RuntimeError(f"Grok API: 404 Not Found — model '{GROK_MODEL}' may not exist. Check model name.")
    if resp.status_code == 429:
        raise RuntimeError("Grok API: 429 Rate limit hit. Wait and try again.")
    if resp.status_code != 200:
        raise RuntimeError(f"Grok API: HTTP {resp.status_code} — {resp.text[:200]}")

    try:
        result = resp.json()
    except Exception:
        raise RuntimeError(f"Grok API: response is not valid JSON — {resp.text[:200]}")

    if "error" in result:
        raise RuntimeError(f"Grok API error: {result['error']}")
    if "data" not in result or not result["data"]:
        raise RuntimeError(f"Grok API: no image data in response — {str(result)[:200]}")

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


def upload_to_wordpress(file_path, filename):
    with open(file_path, "rb") as f:
        data = f.read()
    resp = requests.post(
        f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/media",
        auth=(WP_USERNAME, WP_APP_PASS),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type":        "image/png",
        },
        data=data,
        timeout=(10, 60),
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WordPress upload failed ({resp.status_code}): {resp.text[:200]}")
    return resp.json()["source_url"]

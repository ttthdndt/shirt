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
    return (
        "".join(random.choices(CHARS, k=3))
        + "-"
        + "".join(random.choices(CHARS, k=3))
    )


def generate_pattern(prompt, api_key=None, log=None):
    """
    Call the Grok image generation API and return a PIL Image.
    Retries up to 3 times on failure with verbose logging.
    """
    key = api_key or GROK_API_KEY
    if not key:
        raise RuntimeError("No Grok API key provided.")

    def _log(msg):
        if log:
            log(msg)

    payload = {
        "model":  GROK_MODEL,
        "prompt": prompt,
        "n":      1,
    }

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        _log(f"  Grok API attempt {attempt}/{max_retries} (model: {GROK_MODEL})...")
        try:
            resp = requests.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                json=payload,
                timeout=120,   # 2 min — image generation can be slow
            )
        except requests.exceptions.Timeout:
            _log(f"  Timeout on attempt {attempt}.")
            if attempt == max_retries:
                raise RuntimeError("Grok API timed out after 3 attempts.")
            time.sleep(5)
            continue
        except requests.exceptions.RequestException as e:
            _log(f"  Request error: {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Grok API request failed: {e}")
            time.sleep(5)
            continue

        # ── Log raw status ───────────────────────────────────────────────────
        _log(f"  Grok HTTP {resp.status_code}")

        if resp.status_code != 200:
            _log(f"  Response body: {resp.text[:300]}")
            if attempt == max_retries:
                raise RuntimeError(
                    f"Grok API returned {resp.status_code}: {resp.text[:200]}"
                )
            time.sleep(5)
            continue

        # ── Parse JSON ───────────────────────────────────────────────────────
        try:
            result = resp.json()
        except Exception:
            _log(f"  Failed to parse JSON. Raw: {resp.text[:300]}")
            if attempt == max_retries:
                raise RuntimeError("Grok API returned non-JSON response.")
            time.sleep(5)
            continue

        if "error" in result:
            _log(f"  API error: {result['error']}")
            if attempt == max_retries:
                raise RuntimeError(f"Grok API error: {result['error']}")
            time.sleep(5)
            continue

        # ── Extract image bytes ──────────────────────────────────────────────
        if not result.get("data"):
            _log(f"  No 'data' in response: {str(result)[:300]}")
            raise RuntimeError("Grok API response has no image data.")

        item = result["data"][0]
        _log(f"  Response keys: {list(item.keys())}")

        if "b64_json" in item and item["b64_json"]:
            _log("  Decoding b64_json...")
            img_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item and item["url"]:
            _log(f"  Fetching image from URL: {item['url'][:80]}...")
            img_bytes = requests.get(item["url"], timeout=60).content
        else:
            raise RuntimeError(
                f"Grok response has neither b64_json nor url. Keys: {list(item.keys())}"
            )

        _log(f"  Image received ({len(img_bytes):,} bytes). Decoding...")
        return Image.open(BytesIO(img_bytes)).convert("RGBA")

    raise RuntimeError("Grok API failed after all retries.")


def upload_to_wordpress(file_path, filename, log=None):
    def _log(msg):
        if log: log(msg)

    with open(file_path, "rb") as f:
        data = f.read()

    _log(f"  Uploading {filename} ({len(data):,} bytes)...")
    resp = requests.post(
        f"{WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/media",
        auth=(WP_USERNAME, WP_APP_PASS),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type":        "image/png",
        },
        data=data,
        timeout=60,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"WordPress upload failed ({resp.status_code}): {resp.text[:200]}"
        )

    return resp.json()["source_url"]

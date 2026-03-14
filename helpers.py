import base64
import random
import string
import requests
from io import BytesIO
from PIL import Image
from config import GROK_API_KEY, GROK_MODEL, WP_BASE_URL, WP_USERNAME, WP_APP_PASS

CHARS = string.ascii_uppercase + string.digits   # A-Z + 0-9


def random_sku():
    """Return a random SKU in format XXX-XXX (A-Z, 0-9)."""
    return (
        "".join(random.choices(CHARS, k=3))
        + "-"
        + "".join(random.choices(CHARS, k=3))
    )


def generate_pattern(prompt, api_key=None):
    """
    Call the Grok image generation API and return a PIL Image.

    Parameters
    ----------
    prompt  : str
    api_key : str | None — if provided, overrides the value in config.py

    Returns
    -------
    PIL.Image (RGBA)
    """
    key = api_key or GROK_API_KEY
    if not key:
        raise RuntimeError("No Grok API key provided. Please enter one in the UI.")

    resp = requests.post(
        "https://api.x.ai/v1/images/generations",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        },
        json={
            "model":           GROK_MODEL,       # grok-imagine-image
            "prompt":          prompt,
            "n":               1,
            "response_format": "b64_json",
        },
        timeout=60,
    )
    result = resp.json()

    if "error" in result:
        raise RuntimeError(f"Grok API error: {result['error']}")

    item = result["data"][0]
    if "b64_json" in item:
        img_bytes = base64.b64decode(item["b64_json"])
    elif "url" in item:
        img_bytes = requests.get(item["url"], timeout=30).content
    else:
        raise RuntimeError(f"Unexpected Grok response format: {result}")

    return Image.open(BytesIO(img_bytes)).convert("RGBA")


def upload_to_wordpress(file_path, filename):
    """
    Upload a PNG file to the WordPress Media Library.

    Parameters
    ----------
    file_path : str   — local path to the PNG file
    filename  : str   — filename to use on WordPress

    Returns
    -------
    str — public URL of the uploaded media
    """
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
        timeout=60,
    )

    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"WordPress upload failed ({resp.status_code}): {resp.text[:200]}"
        )

    return resp.json()["source_url"]

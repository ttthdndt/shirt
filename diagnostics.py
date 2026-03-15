import requests
import base64
from io import BytesIO


def check_grok_api(api_key):
    """Test Grok API with a tiny prompt. Returns dict with ok, status, message, detail."""
    if not api_key:
        return {"ok": False, "message": "No API key provided.", "detail": ""}
    try:
        resp = requests.post(
            "https://api.x.ai/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "grok-imagine-image", "prompt": "a red dot", "n": 1, "response_format": "b64_json"},
            timeout=90,
        )
        data = resp.json()
        if resp.status_code == 401:
            return {"ok": False, "message": "Invalid API key (401 Unauthorized).", "detail": str(data)}
        if resp.status_code == 403:
            return {"ok": False, "message": "API key has no permission for image generation (403).", "detail": str(data)}
        if resp.status_code == 429:
            return {"ok": False, "message": "Rate limit hit (429). Try again in a moment.", "detail": str(data)}
        if "error" in data:
            return {"ok": False, "message": f"Grok error: {data['error']}", "detail": str(data)}
        if "data" not in data or not data["data"]:
            return {"ok": False, "message": "Grok returned no image data.", "detail": str(data)}

        # Try to decode the image
        item = data["data"][0]
        if "b64_json" in item:
            img_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            img_bytes = requests.get(item["url"], timeout=30).content
        else:
            return {"ok": False, "message": "Unknown response format from Grok.", "detail": str(data)}

        size_kb = len(img_bytes) // 1024
        return {"ok": True, "message": f"Grok OK — image received ({size_kb} KB).", "detail": ""}

    except requests.exceptions.Timeout:
        return {"ok": False, "message": "Grok API timed out after 90 seconds.", "detail": "The API may be slow or unreachable from this server."}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": "Cannot reach api.x.ai — possible network block.", "detail": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"Unexpected error: {type(e).__name__}", "detail": str(e)}


def check_wordpress(wp_base_url, wp_username, wp_app_pass):
    """Test WordPress REST API auth."""
    try:
        resp = requests.get(
            f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/users/me",
            auth=(wp_username, wp_app_pass),
            timeout=15,
        )
        if resp.status_code == 200:
            name = resp.json().get("name", "unknown")
            return {"ok": True, "message": f"WordPress OK — logged in as '{name}'.", "detail": ""}
        if resp.status_code == 401:
            return {"ok": False, "message": "WordPress auth failed (401). Check username / application password.", "detail": resp.text[:200]}
        if resp.status_code == 404:
            return {"ok": False, "message": "WordPress REST API not found (404). Is the site URL correct?", "detail": resp.text[:200]}
        return {"ok": False, "message": f"WordPress returned HTTP {resp.status_code}.", "detail": resp.text[:200]}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": f"Cannot reach {wp_base_url}.", "detail": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"Unexpected error: {type(e).__name__}", "detail": str(e)}


def check_garments(garment_urls):
    """Test that garment URLs are reachable."""
    results = []
    for url in garment_urls:
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                results.append({"url": url, "ok": True, "message": "OK"})
            else:
                results.append({"url": url, "ok": False, "message": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"url": url, "ok": False, "message": str(e)[:80]})
    return results


def check_vercel_env():
    """Report relevant environment info."""
    import sys, os
    return {
        "python": sys.version,
        "tmp_writable": os.access("/tmp", os.W_OK),
        "env_vars_set": {
            "GROK_API_KEY": bool(os.getenv("GROK_API_KEY")),
            "WP_APP_PASS":  bool(os.getenv("WP_APP_PASS")),
            "WP_BASE_URL":  bool(os.getenv("WP_BASE_URL")),
        }
    }

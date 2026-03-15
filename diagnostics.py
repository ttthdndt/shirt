import requests
import base64
import socket


def check_grok_api(api_key):
    """Test Grok API — distinguishes network block vs auth error vs model error."""
    if not api_key:
        return {"ok": False, "message": "No API key provided.", "detail": ""}

    # Step 1: DNS resolution
    try:
        ip = socket.gethostbyname("api.x.ai")
    except socket.gaierror as e:
        return {
            "ok": False,
            "message": "DNS failed: cannot resolve api.x.ai — this server cannot reach the Grok API at all.",
            "detail": f"socket.gaierror: {e}\n→ This is a Vercel network restriction. Deploy on a VPS instead.",
            "cause": "dns_block"
        }

    # Step 2: TCP connect
    try:
        s = socket.create_connection(("api.x.ai", 443), timeout=5)
        s.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        return {
            "ok": False,
            "message": "TCP connect to api.x.ai:443 failed — outbound HTTPS is blocked.",
            "detail": f"{type(e).__name__}: {e}\n→ This is a Vercel network restriction. Deploy on a VPS instead.",
            "cause": "tcp_block"
        }

    # Step 3: Actual API call with short timeout
    try:
        resp = requests.post(
            "https://api.x.ai/v1/images/generations",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "grok-imagine-image", "prompt": "a red circle", "n": 1, "response_format": "b64_json"},
            timeout=(5, 30),
        )
    except requests.exceptions.ConnectTimeout:
        return {"ok": False, "message": "Connect timeout (5s) — server is blocking outbound requests to api.x.ai.", "detail": "→ Deploy on a VPS instead.", "cause": "connect_timeout"}
    except requests.exceptions.ReadTimeout:
        return {"ok": False, "message": "Read timeout (30s) — Grok API connected but did not respond in time.", "detail": "", "cause": "read_timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": f"Connection error — {e}", "detail": "→ Deploy on a VPS instead.", "cause": "connection_error"}

    if resp.status_code == 401:
        return {"ok": False, "message": "Invalid API key (401 Unauthorized).", "detail": resp.text[:200], "cause": "auth"}
    if resp.status_code == 403:
        return {"ok": False, "message": "API key has no image generation permission (403).", "detail": resp.text[:200], "cause": "permission"}
    if resp.status_code == 429:
        return {"ok": False, "message": "Rate limit hit (429).", "detail": resp.text[:200], "cause": "rate_limit"}
    if resp.status_code != 200:
        return {"ok": False, "message": f"HTTP {resp.status_code}", "detail": resp.text[:300], "cause": "api_error"}

    try:
        data = resp.json()
        if "error" in data:
            return {"ok": False, "message": f"API error: {data['error']}", "detail": "", "cause": "api_error"}
        img_bytes = base64.b64decode(data["data"][0]["b64_json"])
        size_kb = len(img_bytes) // 1024
        return {"ok": True, "message": f"Grok OK — image received ({size_kb} KB).", "detail": "", "cause": ""}
    except Exception as e:
        return {"ok": False, "message": f"Could not decode response: {e}", "detail": resp.text[:200], "cause": "decode_error"}


def check_wordpress(wp_base_url, wp_username, wp_app_pass):
    try:
        resp = requests.get(
            f"{wp_base_url.rstrip('/')}/wp-json/wp/v2/users/me",
            auth=(wp_username, wp_app_pass),
            timeout=15,
        )
        if resp.status_code == 200:
            return {"ok": True, "message": f"WordPress OK — logged in as '{resp.json().get('name', '?')}'.", "detail": ""}
        return {"ok": False, "message": f"WordPress HTTP {resp.status_code}.", "detail": resp.text[:200]}
    except Exception as e:
        return {"ok": False, "message": f"Cannot reach WordPress: {e}", "detail": ""}


def check_garments(garment_urls):
    results = []
    for url in garment_urls:
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            results.append({"url": url, "ok": resp.status_code == 200, "message": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"url": url, "ok": False, "message": str(e)[:80]})
    return results


def check_vercel_env():
    import sys, os
    return {
        "python": sys.version.split(" ")[0],
        "tmp_writable": os.access("/tmp", os.W_OK),
        "env_vars_set": {
            "GROK_API_KEY": bool(os.getenv("GROK_API_KEY")),
            "WP_APP_PASS":  bool(os.getenv("WP_APP_PASS")),
            "WP_BASE_URL":  bool(os.getenv("WP_BASE_URL")),
        }
    }

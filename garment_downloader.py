import os
import requests
from PIL import Image
from config import GARMENT_IMAGES, GARMENT_LABELS, GARMENT_FOLDER


def download_all_garments(log=None):
    """
    Download all garment images (cached — skips if already on disk).

    Parameters
    ----------
    log : callable | None
        Optional logger function, e.g. print or a job status appender.

    Returns
    -------
    list of (label: str, image: PIL.Image)
    """
    os.makedirs(GARMENT_FOLDER, exist_ok=True)
    garments = []

    for src, label in zip(GARMENT_IMAGES, GARMENT_LABELS):
        local_path = os.path.join(GARMENT_FOLDER, src.split("/")[-1])

        if not os.path.exists(local_path):
            _log(log, f"Downloading garment: {label}...")
            try:
                r = requests.get(src, timeout=30)
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                raise RuntimeError(f"Failed to download garment '{label}': {e}")
        else:
            _log(log, f"Garment cached: {label}")

        img = Image.open(local_path).convert("RGBA")
        garments.append((label, img))

    _log(log, f"{len(garments)} garments ready.")
    return garments


def _log(log_fn, msg):
    if log_fn:
        log_fn(msg)

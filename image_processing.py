import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, label as nd_label


def build_shirt_mask(arr):
    """
    Build a boolean mask of the shirt area from a garment image array.

    Strategy:
    - If the image has a real alpha channel → use it directly.
    - Otherwise → flood-fill from border pixels to find the white
      background, then invert to get the shirt silhouette.

    Parameters
    ----------
    arr : np.ndarray   shape (H, W, 4), dtype uint8

    Returns
    -------
    np.ndarray   shape (H, W), dtype bool — True = shirt, False = background
    """
    # Case 1: image already has meaningful alpha
    if not np.all(arr[:, :, 3] == 255):
        return arr[:, :, 3] > 10

    # Case 2: solid background — detect near-white border pixels
    rgb = arr[:, :, :3]
    is_white = np.all(rgb >= 245, axis=2)

    # Label connected white regions
    labeled, _ = nd_label(is_white)

    # Identify background = any white region that touches a border edge
    border = np.zeros_like(is_white)
    border[0,  :] = is_white[0,  :]
    border[-1, :] = is_white[-1, :]
    border[:,  0] = is_white[:,  0]
    border[:, -1] = is_white[:, -1]

    bg_labels = set(labeled[border].flatten()) - {0}
    bg_mask   = np.isin(labeled, list(bg_labels))

    # Shirt = everything NOT background; fill interior holes (collar gap, buttons)
    return binary_fill_holes(~bg_mask)


def apply_pattern(garment_img, pattern_img, out_path):
    """
    Resize a pattern to match the garment, mask it to the shirt silhouette,
    and apply a multiply blend using the garment's luminance (preserves
    wrinkles and fabric shading).

    Parameters
    ----------
    garment_img : PIL.Image (RGBA)
    pattern_img : PIL.Image (RGBA)
    out_path    : str — where to save the composited PNG

    Returns
    -------
    PIL.Image (RGBA) — composited image on white background
    """
    arr  = np.array(garment_img)
    mask = build_shirt_mask(arr)

    # Resize pattern to match garment dimensions
    pat = pattern_img.resize(garment_img.size, Image.LANCZOS).convert("RGB")

    # ── Luminance light map (same as Photoshop Multiply mode) ───────────────
    g_rgb = np.array(garment_img.convert("RGB")).astype(np.float32) / 255.0
    lum   = (
        0.299 * g_rgb[:, :, 0]
        + 0.587 * g_rgb[:, :, 1]
        + 0.114 * g_rgb[:, :, 2]
    )
    # Normalize: mean shirt brightness → 1.0; shadows < 1.0; highlights > 1.0
    lum_mean  = lum[mask].mean() if mask.any() else 0.85
    light_map = np.clip(lum / lum_mean, 0.3, 1.4)

    # ── Multiply blend ───────────────────────────────────────────────────────
    pat_np  = np.array(pat).astype(np.float32) / 255.0
    blended = np.clip(pat_np * light_map[:, :, np.newaxis], 0.0, 1.0)

    # ── Apply shirt mask as alpha channel ────────────────────────────────────
    alpha  = (mask * 255).astype(np.uint8)
    result = Image.fromarray(
        np.dstack([(blended * 255).astype(np.uint8), alpha]), "RGBA"
    )

    # ── Composite on white and save ──────────────────────────────────────────
    bg = Image.new("RGBA", garment_img.size, (255, 255, 255, 255))
    bg.paste(result, mask=result)
    bg.save(out_path)
    return bg

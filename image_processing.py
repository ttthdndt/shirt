import time
import numpy as np
from PIL import Image
from scipy.ndimage import binary_fill_holes, label as nd_label


def build_shirt_mask(arr):
    """
    Boolean mask: True = shirt, False = background.
    Tries alpha channel first, falls back to white flood-fill.
    """
    if not np.all(arr[:, :, 3] == 255):
        return arr[:, :, 3] > 10

    rgb      = arr[:, :, :3]
    is_white = np.all(rgb >= 245, axis=2)
    labeled, _ = nd_label(is_white)

    border = np.zeros_like(is_white)
    border[0,  :] = is_white[0,  :]
    border[-1, :] = is_white[-1, :]
    border[:,  0] = is_white[:,  0]
    border[:, -1] = is_white[:, -1]

    bg_labels = set(labeled[border].flatten()) - {0}
    return binary_fill_holes(~np.isin(labeled, list(bg_labels)))


def apply_pattern(garment_img, pattern_img, out_path, log=None):
    """
    Resize pattern → mask to shirt silhouette → multiply blend → save.
    Logs timing for each sub-step when log= is provided.
    """
    def _t(label, start):
        if log:
            log(f"      · {label}: {time.time()-start:.3f}s")

    t0 = time.time()

    # 1. Build mask
    t = time.time()
    arr  = np.array(garment_img)
    mask = build_shirt_mask(arr)
    _t("build_shirt_mask", t)

    # 2. Resize pattern
    t = time.time()
    pat = pattern_img.resize(garment_img.size, Image.LANCZOS).convert("RGB")
    _t("pattern resize (LANCZOS)", t)

    # 3. Luminance light map
    t = time.time()
    g_rgb = np.array(garment_img.convert("RGB")).astype(np.float32) / 255.0
    lum   = 0.299 * g_rgb[:,:,0] + 0.587 * g_rgb[:,:,1] + 0.114 * g_rgb[:,:,2]
    lum_mean  = lum[mask].mean() if mask.any() else 0.85
    light_map = np.clip(lum / lum_mean, 0.3, 1.4)
    _t("luminance light map", t)

    # 4. Multiply blend
    t = time.time()
    pat_np  = np.array(pat).astype(np.float32) / 255.0
    blended = np.clip(pat_np * light_map[:, :, np.newaxis], 0.0, 1.0)
    _t("multiply blend", t)

    # 5. Apply alpha mask
    t = time.time()
    alpha  = (mask * 255).astype(np.uint8)
    result = Image.fromarray(
        np.dstack([(blended * 255).astype(np.uint8), alpha]), "RGBA"
    )
    _t("apply alpha mask", t)

    # 6. Composite on white + save
    t = time.time()
    bg = Image.new("RGBA", garment_img.size, (255, 255, 255, 255))
    bg.paste(result, mask=result)
    bg.save(out_path)
    _t("composite + save PNG", t)

    if log:
        log(f"      · TOTAL mask+blend: {time.time()-t0:.3f}s")

    return bg

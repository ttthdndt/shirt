import csv
import io
from config import WC_COLUMNS


def write_output_csv(output_rows):
    """
    Serialize WooCommerce output rows into a UTF-8-sig encoded CSV string
    (BOM included so Excel opens it correctly on Windows).

    Parameters
    ----------
    output_rows : list[dict]

    Returns
    -------
    str — CSV content ready to be sent as a file download
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=WC_COLUMNS,
        extrasaction="ignore",   # ignore any keys not in WC_COLUMNS
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(output_rows)

    # Prepend UTF-8 BOM so Excel on Windows doesn't mangle special characters
    return "\ufeff" + buf.getvalue()


def summary_table(output_rows):
    """
    Return a list of summary dicts for display in the UI.

    Each dict has: sku, title, image_count, first_url
    """
    table = []
    for r in output_rows:
        urls = [u for u in r.get("Images", "").split(", ") if u.strip()]
        table.append({
            "sku":         r.get("SKU", ""),
            "title":       r.get("Name", ""),
            "image_count": len(urls),
            "first_url":   urls[0] if urls else "",
        })
    return table

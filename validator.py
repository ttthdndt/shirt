import csv
import io
from config import REQUIRED_COLUMNS


def validate_csv(file_storage):
    """
    Validate an uploaded CSV file.

    Parameters
    ----------
    file_storage : werkzeug.FileStorage
        The uploaded file from Flask request.files.

    Returns
    -------
    dict with keys:
        ok      : bool
        rows    : list[dict] | None   — parsed rows if ok
        error   : str | None          — human-readable error if not ok
        missing : list[str]           — missing required columns
        extra   : list[str]           — extra unexpected columns
    """
    # ── 1. Read raw bytes and decode ─────────────────────────────────────────
    try:
        raw = file_storage.read().decode("utf-8-sig")   # strip BOM if present
    except UnicodeDecodeError:
        return _fail("File encoding error — please save the CSV as UTF-8.")

    if not raw.strip():
        return _fail("The uploaded file is empty.")

    # ── 2. Parse CSV ──────────────────────────────────────────────────────────
    try:
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
        columns = set(reader.fieldnames or [])
    except Exception as e:
        return _fail(f"Could not parse CSV: {e}")

    if not rows:
        return _fail("The CSV has a header row but no data rows.")

    # ── 3. Column check ───────────────────────────────────────────────────────
    missing = sorted(REQUIRED_COLUMNS - columns)
    extra   = sorted(columns - REQUIRED_COLUMNS)

    if missing:
        msg_parts = [f"Missing column(s): {', '.join(missing)}"]
        if extra:
            msg_parts.append(f"Unknown column(s): {', '.join(extra)}")
        return {
            "ok":      False,
            "rows":    None,
            "error":   " | ".join(msg_parts),
            "missing": missing,
            "extra":   extra,
        }

    # ── 4. Row-level check — no empty prompts ─────────────────────────────────
    empty_prompt_rows = [
        i + 2  # +2 = 1-indexed + skip header
        for i, r in enumerate(rows)
        if not r.get("pattern_prompt", "").strip()
    ]
    if empty_prompt_rows:
        return _fail(
            f"Empty 'pattern_prompt' on row(s): {', '.join(map(str, empty_prompt_rows))}"
        )

    return {
        "ok":      True,
        "rows":    rows,
        "error":   None,
        "missing": [],
        "extra":   extra,   # non-empty = warning only, not an error
    }


def _fail(msg):
    return {"ok": False, "rows": None, "error": msg, "missing": [], "extra": []}

import os
import uuid
import threading
from flask import Flask, request, jsonify, render_template, Response, abort
from config import UPLOAD_FOLDER, OUTPUT_FOLDER, MAX_CONTENT_MB, GARMENT_IMAGES, WP_BASE_URL, WP_USERNAME, WP_APP_PASS
from validator import validate_csv
from garment_downloader import download_all_garments
from pipeline import run_pipeline
from csv_writer import write_output_csv, summary_table
from diagnostics import check_grok_api, check_wordpress, check_garments, check_vercel_env

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "shirt-pipeline-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_MB * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

JOBS: dict[str, "Job"] = {}


class Job:
    def __init__(self, job_id):
        self.id            = job_id
        self.status        = "queued"
        self.status_detail = ""
        self.logs          = []
        self.progress      = 0
        self.result_csv    = None
        self.summary       = []
        self.error_msg     = None
        self.cancelled     = False
        self._lock         = threading.Lock()

    def log(self, msg):
        with self._lock:
            self.logs.append(msg)

    def set_progress(self, done, total):
        self.progress = int(done / total * 100) if total else 100


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/diagnose", methods=["POST"])
def diagnose():
    """Run all diagnostics and return results. Called from UI before pipeline."""
    api_key = request.json.get("api_key", "").strip()

    # Run checks (Grok is slow — run in parallel)
    import concurrent.futures
    results = {}

    def run_grok():
        results["grok"] = check_grok_api(api_key)

    def run_wp():
        results["wordpress"] = check_wordpress(WP_BASE_URL, WP_USERNAME, WP_APP_PASS)

    def run_garments():
        results["garments"] = check_garments(GARMENT_IMAGES[:2])  # check first 2 only

    def run_env():
        results["environment"] = check_vercel_env()

    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = [ex.submit(run_grok), ex.submit(run_wp), ex.submit(run_garments), ex.submit(run_env)]
        concurrent.futures.wait(futures)

    all_ok = results["grok"]["ok"] and results["wordpress"]["ok"]
    return jsonify({"ok": all_ok, **results})


@app.route("/validate", methods=["POST"])
def validate():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided."}), 400
    result = validate_csv(request.files["file"])
    if not result["ok"]:
        return jsonify(result), 422
    preview = [
        {"prompt": r["pattern_prompt"][:80], "title": r["title"]}
        for r in result["rows"][:5]
    ]
    return jsonify({"ok": True, "row_count": len(result["rows"]), "extra": result["extra"], "preview": preview})


@app.route("/run", methods=["POST"])
def run():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided."}), 400

    api_key    = request.form.get("api_key", "").strip() or None
    validation = validate_csv(request.files["file"])
    if not validation["ok"]:
        return jsonify(validation), 422

    job_id       = str(uuid.uuid4())
    job          = Job(job_id)
    JOBS[job_id] = job

    def worker():
        job.status = "running"
        try:
            job.log("Downloading garments...")
            garments = download_all_garments(log=job.log)
            job.log(f"Starting pipeline ({len(validation['rows'])} prompts)...")
            output_rows    = run_pipeline(validation["rows"], garments, job, api_key=api_key)
            job.result_csv = write_output_csv(output_rows)
            job.summary    = summary_table(output_rows)
            job.status     = "done"
            job.log("Pipeline complete!")
        except Exception as e:
            job.status    = "error"
            job.error_msg = str(e)
            job.log(f"ERROR: {e}")

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"ok": True, "job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    return jsonify({
        "status":        job.status,
        "status_detail": job.status_detail,
        "progress":      job.progress,
        "logs":          job.logs[-80:],
        "error":         job.error_msg,
        "summary":       job.summary if job.status == "done" else [],
    })


@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or job.status != "done" or not job.result_csv:
        abort(404)
    return Response(
        job.result_csv,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=output_wc.csv"},
    )


@app.route("/cancel/<job_id>", methods=["POST"])
def cancel(job_id):
    job = JOBS.get(job_id)
    if job:
        job.cancelled = True
        job.log("Cancellation requested.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)

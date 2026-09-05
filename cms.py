"""Local CMS for ddsverified.ir — localhost-only, no auth, no DB.

Starts an HTTP server on 127.0.0.1:8765 that lets the owner edit the
PRODUCTS array in index.html through a browser form, then on save:

  1. Backs up index.html to .cms-backups/
  2. Surgically rewrites the PRODUCTS block (atomic, tmpfile + os.replace)
  3. Runs the existing pipeline: extract_products -> generate_pages ->
     emalls_feed -> torob_feed -> pytest
  4. If all green: git add + commit + push (with one auto-rebase retry)
  5. Streams every step's stdout/stderr live back to the browser

Never touches index.html outside the PRODUCTS block. Never pushes if
tests fail. Single source of truth stays the PRODUCTS array literal in
index.html (per ddsverified-pipeline skill rule).
"""
from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from tools.serialize_products import serialize_products, rewrite_index  # noqa: E402

PORT = 8765
HOST = "127.0.0.1"
BACKUP_DIR = ROOT / ".cms-backups"
JOBS: dict[str, dict] = {}  # job_id -> {"events": list, "done": Event, "ok": bool|None, ...}
JOBS_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Pipeline runner — streams events to an in-memory queue per job
# ---------------------------------------------------------------------------
PIPELINE = [
    ("extract", [sys.executable, "tools/extract_products.py"]),
    ("generate_pages", [sys.executable, "generate_pages.py"]),
    ("emalls", [sys.executable, "tools/generate_emalls_feed.py"]),
    ("torob", [sys.executable, "tools/generate_torob_feed.py"]),
    ("tests", [sys.executable, "-m", "pytest",
               "test_generate.py", "test_emalls_feed.py", "test_torob_feed.py",
               "-q", "--tb=line"]),
]


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _run_step(name: str, cmd: list[str], push) -> bool:
    """Run one pipeline step. push(line, level) is called for each line.
    Returns True on success."""
    push(f"\n──── {name} ────", "step")
    push(f"$ {' '.join(cmd)}", "cmd")
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            push(line, "out")
    rc = proc.wait()
    if rc != 0:
        push(f"[FAIL] exit {rc}", "err")
        return False
    push("[OK]", "ok")
    return True


def _run_git(commit_msg: str, push_fn) -> tuple[bool, str]:
    """git add + commit + push. One auto-rebase retry on rejection.
    Returns (ok, sha_or_msg)."""
    push_fn("\n──── git ────", "step")
    # stage everything (CI may have generated artifacts)
    r = subprocess.run(["git", "add", "-A"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        push_fn(f"[FAIL] git add: {r.stderr}", "err")
        return False, r.stderr
    # Check if anything to commit
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if r.returncode == 0:
        push_fn("nothing to commit (no diff)", "info")
        # still return success: user wanted "publish" but there was nothing new
        return True, "no-changes"
    r = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        push_fn(f"[FAIL] git commit: {r.stderr}", "err")
        return False, r.stderr
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
        capture_output=True, text=True,
    ).stdout.strip()
    push_fn(f"committed {sha}", "ok")
    # Push
    r = subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        # Try one rebase-and-retry (CI bot may have raced)
        push_fn(f"push failed: {r.stderr.strip()}. Trying pull --rebase...", "warn")
        rb = subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if rb.returncode != 0:
            push_fn(f"[FAIL] pull --rebase: {rb.stderr}", "err")
            return False, rb.stderr
        r2 = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r2.returncode != 0:
            push_fn(f"[FAIL] push after rebase: {r2.stderr}", "err")
            return False, r2.stderr
    push_fn("pushed to origin/main", "ok")
    return True, sha


def run_save_job(job_id: str, products: list[dict], commit_msg: str) -> None:
    """Run the full save pipeline in a background thread."""
    events: list[dict] = []
    done_evt = threading.Event()

    def push(line: str, level: str) -> None:
        events.append({"t": _now(), "l": level, "m": line})
        print(f"[{job_id}] {level}: {line}", flush=True)

    with JOBS_LOCK:
        JOBS[job_id] = {
            "events": events, "done": done_evt, "ok": None,
            "started": time.time(), "step": "init",
        }

    try:
        push(f"job {job_id[:8]} — {len(products)} products", "info")
        # 1. backup + rewrite
        push("\n──── rewrite ────", "step")
        backup_dir = BACKUP_DIR
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-") + f"{time.time_ns() % 1_000_000:06d}"
        import shutil
        shutil.copy2(ROOT / "index.html", backup_dir / f"index.html.{ts}")
        # prune
        backups = sorted(backup_dir.glob("index.html.*"), key=lambda p: p.name)
        for old in backups[:-20]:
            old.unlink()
        push(f"backup -> .cms-backups/index.html.{ts}", "info")

        new_text = rewrite_index(ROOT / "index.html", products, backup_dir=backup_dir)
        push(f"index.html rewritten ({len(new_text):,} bytes)", "ok")

        with JOBS_LOCK:
            JOBS[job_id]["step"] = "pipeline"

        # 2. pipeline
        for name, cmd in PIPELINE:
            with JOBS_LOCK:
                JOBS[job_id]["step"] = name
            if not _run_step(name, cmd, push):
                with JOBS_LOCK:
                    JOBS[job_id]["ok"] = False
                    JOBS[job_id]["step"] = f"{name}_failed"
                done_evt.set()
                return

        # 3. git
        with JOBS_LOCK:
            JOBS[job_id]["step"] = "git"
        ok, info = _run_git(commit_msg, push)
        with JOBS_LOCK:
            JOBS[job_id]["ok"] = ok
            JOBS[job_id]["step"] = "done" if ok else "git_failed"
            JOBS[job_id]["info"] = info
        push("\n✓ done" if ok else "\n✗ git failed", "ok" if ok else "err")
    except Exception as e:
        push(f"[EXC] {type(e).__name__}: {e}", "err")
        with JOBS_LOCK:
            JOBS[job_id]["ok"] = False
            JOBS[job_id]["step"] = "exception"
    finally:
        done_evt.set()


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------
INDEX_HTML = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>DDSVerified — Local CMS</title>
<style>
  :root {
    --bg: #f7f7f5; --card: #fff; --border: #e5e5e0;
    --fg: #1a1a1a; --muted: #777;
    --accent: #1565c0; --ok: #2e7d32; --err: #c62828; --warn: #ef6c00;
    --add: #e8f5e9; --edit: #fff8e1; --del: #ffebee;
  }
  * { box-sizing: border-box; }
  body { font: 14px/1.4 -apple-system, "Segoe UI", Tahoma, sans-serif;
         margin: 0; background: var(--bg); color: var(--fg); }
  header { background: var(--card); border-bottom: 1px solid var(--border);
           padding: 12px 20px; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header .meta { color: var(--muted); font-size: 12px; margin-right: auto;
                 font-family: ui-monospace, Consolas, monospace; }
  header .meta span { margin-left: 12px; }
  main { padding: 20px; max-width: 1400px; margin: 0 auto; }
  .toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  input[type=search] { flex: 1; min-width: 200px; padding: 8px 12px;
                       border: 1px solid var(--border); border-radius: 6px;
                       background: var(--card); font: inherit; }
  button { padding: 8px 14px; border: 1px solid var(--border);
           background: var(--card); border-radius: 6px; cursor: pointer;
           font: inherit; }
  button:hover { background: #f0f0eb; }
  button.primary { background: var(--accent); color: #fff; border-color: var(--accent); }
  button.primary:hover { background: #0d47a1; }
  button.danger { background: var(--err); color: #fff; border-color: var(--err); }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 6px;
          overflow: hidden; }
  th, td { padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--border); }
  th { background: #fafaf7; font-weight: 600; font-size: 12px;
       color: var(--muted); text-transform: uppercase; letter-spacing: 0.3px; }
  tr:hover { background: #fafaf7; }
  tr.row-add { background: var(--add); }
  tr.row-edit { background: var(--edit); }
  tr.row-del { background: var(--del); opacity: 0.7; text-decoration: line-through; }
  td.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; }
  td.num { text-align: left; font-variant-numeric: tabular-nums; }
  .pill { display: inline-block; padding: 1px 6px; border-radius: 10px;
          font-size: 11px; background: #e3f2fd; color: #1565c0; }
  .pill.warn { background: #fff3e0; color: #ef6c00; }
  .pill.ok { background: #e8f5e9; color: #2e7d32; }
  /* Modal */
  .overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4);
             align-items: center; justify-content: center; z-index: 100; }
  .overlay.open { display: flex; }
  .modal { background: var(--card); border-radius: 8px; padding: 20px;
           width: 600px; max-width: 90vw; max-height: 90vh; overflow: auto;
           box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
  .modal h2 { margin-top: 0; }
  .form-grid { display: grid; grid-template-columns: 100px 1fr; gap: 8px 12px;
               align-items: center; margin-bottom: 16px; }
  .form-grid label { font-weight: 500; }
  .form-grid input, .form-grid select { padding: 6px 8px; border: 1px solid var(--border);
                                        border-radius: 4px; font: inherit; width: 100%; }
  .form-grid .err { color: var(--err); font-size: 12px; grid-column: 2; }
  .modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
  /* Log panel */
  #logPanel { background: #1e1e1e; color: #d4d4d4; padding: 12px;
              border-radius: 6px; font-family: ui-monospace, Consolas, monospace;
              font-size: 12px; max-height: 400px; overflow-y: auto;
              margin-top: 16px; white-space: pre-wrap; }
  #logPanel .step { color: #569cd6; font-weight: bold; }
  #logPanel .cmd  { color: #9cdcfe; }
  #logPanel .ok   { color: #6a9955; }
  #logPanel .err  { color: #f48771; }
  #logPanel .warn { color: #dcdcaa; }
  #logPanel .info { color: #808080; }
  #logPanel .out  { color: #d4d4d4; }
  .status { padding: 8px 12px; border-radius: 6px; margin-top: 12px;
            font-weight: 500; }
  .status.ok { background: var(--add); color: var(--ok); }
  .status.err { background: var(--del); color: var(--err); }
  .status.run { background: #e3f2fd; color: var(--accent); }
  footer { padding: 20px; text-align: center; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1>DDSVerified — Local CMS</h1>
  <div class="meta">
    <span id="repo">__ROOT__</span>
    <span id="branch"></span>
    <span id="count"></span>
  </div>
</header>
<main>
  <div class="toolbar">
    <input type="search" id="search" placeholder="جستجو: model، shape، diameter…">
    <button onclick="openAdd()">+ افزودن محصول</button>
    <button onclick="openDiff()" id="diffBtn" disabled>تأیید تغییرات و انتشار (0)</button>
    <button onclick="discardChanges()" id="discardBtn" disabled>لغو تغییرات</button>
  </div>

  <table id="tbl">
    <thead><tr>
      <th>model</th><th>shape</th><th>grit</th>
      <th>iso</th><th>usa</th><th>diameter</th><th>length</th>
      <th>inventory</th><th>mult</th><th>price</th><th></th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table>

  <div id="logPanel" style="display:none"></div>
  <div id="status" style="display:none"></div>
</main>

<div class="overlay" id="modal">
  <div class="modal">
    <h2 id="modalTitle">ویرایش محصول</h2>
    <div class="form-grid" id="formGrid"></div>
    <div class="modal-actions">
      <button onclick="closeModal()">انصراف</button>
      <button class="danger" id="delBtn" style="display:none" onclick="deleteCurrent()">حذف</button>
      <button class="primary" onclick="saveModal()">ذخیره</button>
    </div>
  </div>
</div>

<footer>
  Local-only. <kbd>Esc</kbd> close, <kbd>Ctrl+S</kbd> save in form.
  Source of truth: <code>index.html → PRODUCTS = [...]</code>
</footer>

<script>
const SHAPES = __SHAPES__;
const GRITS = __GRITS__;
const REPO = "__ROOT__";

// --- state ---
let original = [];   // server state at page load
let current = [];    // working copy (what UI renders)
let editing = null;   // index of product being edited, or null for add

function loadData() {
  fetch("/api/products").then(r=>r.json()).then(data=>{
    original = data.products.map(p => ({...p}));
    current = data.products.map(p => ({...p}));
    document.getElementById("count").textContent = `${current.length} محصول`;
    render();
  });
}
function render() {
  const q = document.getElementById("search").value.trim().toLowerCase();
  const tbody = document.getElementById("tbody");
  tbody.innerHTML = "";
  current.forEach((p, i) => {
    if (q && !JSON.stringify(p).toLowerCase().includes(q)) return;
    const orig = original[i];
    const isNew = !orig;
    const isDel = !p && orig;
    if (isDel) return;  // deleted rows shown in diff only
    const isEdit = orig && JSON.stringify(orig) !== JSON.stringify(p);
    const tr = document.createElement("tr");
    if (isNew) tr.className = "row-add";
    else if (isEdit) tr.className = "row-edit";
    tr.innerHTML = `
      <td class="mono"><b>${esc(p.model)}</b></td>
      <td>${esc(SHAPES[p.shape] || p.shape)}</td>
      <td>${esc(p.grit)}</td>
      <td class="mono">${esc(p.iso||"")}</td>
      <td class="mono">${esc(p.usa||"")}</td>
      <td class="num">${esc(p.diameter||"")}</td>
      <td class="num">${esc(p.length||"")}</td>
      <td class="num">${p.inventory||0}</td>
      <td>${p.multiplier||5}</td>
      <td>${p.price ? p.price.toLocaleString()+" <span class='pill warn'>تومان</span>" : '<span class="pill">پلکانی</span>'}</td>
      <td><button onclick='openEdit(${i})'>ویرایش</button></td>`;
    tr.querySelector("td:first-child").ondblclick = () => openEdit(i);
    tbody.appendChild(tr);
  });
  updateDiffBtn();
}

function diffStats() {
  let added=0, edited=0, deleted=0;
  for (let i=0;i<current.length;i++) {
    const p = current[i], o = original[i];
    if (!o && p) added++;
    else if (o && !p) deleted++;
    else if (o && p && JSON.stringify(o)!==JSON.stringify(p)) edited++;
  }
  return {added, edited, deleted};
}
function updateDiffBtn() {
  const {added,edited,deleted} = diffStats();
  const n = added+edited+deleted;
  const btn = document.getElementById("diffBtn");
  const dbtn = document.getElementById("discardBtn");
  btn.disabled = n===0;
  btn.textContent = `تأیید تغییرات و انتشار (${n})`;
  dbtn.disabled = n===0;
}

function openAdd() {
  editing = current.length;
  current.push({shape:"needle", model:"", iso:"", usa:"", diameter:"",
                length:"", grit:"Y🟡", inventory:100, multiplier:5});
  openForm(true);
}
function openEdit(i) {
  editing = i;
  openForm(false);
}
function openForm(isNew) {
  const p = current[editing];
  document.getElementById("modalTitle").textContent = isNew ? "افزودن محصول" : "ویرایش "+p.model;
  document.getElementById("delBtn").style.display = isNew ? "none" : "inline-block";
  const grid = document.getElementById("formGrid");
  grid.innerHTML = "";
  const fields = [
    ["model","model","text"], ["shape","shape","select:shapes"],
    ["iso","iso","text"], ["usa","usa","text"],
    ["diameter","diameter","text"], ["length","length","text"],
    ["grit","grit","select:grits"], ["inventory","inventory","number"],
    ["multiplier","multiplier","select:1,5"], ["price","price","number"],
  ];
  for (const [k, label, type] of fields) {
    const lbl = document.createElement("label"); lbl.textContent = label;
    const inp = document.createElement("input");
    if (type.startsWith("select:")) {
      const sel = document.createElement("select");
      const opts = type==="select:shapes" ? SHAPES :
                   type==="select:grits"   ? GRITS  :
                   type.split(":")[1].split(",");
      for (const o of Object.keys(opts)) {
        const opt = document.createElement("option");
        opt.value = o; opt.textContent = type==="select:shapes"||type==="select:grits" ? `${o} — ${opts[o]||""}` : o;
        if (String(p[k]) === String(o)) opt.selected = true;
        sel.appendChild(opt);
      }
      grid.appendChild(lbl); grid.appendChild(sel);
      sel.id = "f_"+k;
    } else {
      inp.type = type;
      inp.value = p[k] ?? "";
      inp.id = "f_"+k;
      grid.appendChild(lbl); grid.appendChild(inp);
    }
  }
  document.getElementById("modal").classList.add("open");
}
function closeModal() {
  // if was an unsaved add, remove the placeholder
  if (editing !== null && !original[editing] && !current[editing].model) {
    current.pop();
  }
  editing = null;
  document.getElementById("modal").classList.remove("open");
  render();
}
function saveModal() {
  const p = current[editing];
  for (const k of ["model","shape","iso","usa","diameter","length","grit","inventory","multiplier"]) {
    const el = document.getElementById("f_"+k);
    if (!el) continue;
    p[k] = k==="inventory" || k==="multiplier" ? parseInt(el.value)||0 : el.value;
  }
  const priceEl = document.getElementById("f_price");
  if (priceEl && priceEl.value) p.price = parseInt(priceEl.value);
  else delete p.price;
  if (!p.model.trim()) { alert("model نمی‌تواند خالی باشد"); return; }
  editing = null;
  document.getElementById("modal").classList.remove("open");
  render();
}
function deleteCurrent() {
  if (!confirm("این محصول حذف شود؟")) return;
  current[editing] = null;
  editing = null;
  document.getElementById("modal").classList.remove("open");
  render();
}
function discardChanges() {
  if (!confirm("همه تغییرات لغو شود؟")) return;
  current = original.map(p => ({...p}));
  render();
}

// --- publish ---
function openDiff() {
  const {added,edited,deleted} = diffStats();
  const msg = [
    added  ? `+ ${added} محصول جدید` : "",
    edited ? `~ ${edited} محصول ویرایش‌شده` : "",
    deleted? `- ${deleted} محصول حذف‌شده` : "",
  ].filter(Boolean).join("  •  ");
  const commitMsg = prompt("پیام commit:", `cms: ${msg || "update products"}`);
  if (!commitMsg) return;
  publish(commitMsg);
}
function publish(commitMsg) {
  // Strip deleted rows
  const products = current.filter(Boolean);
  const log = document.getElementById("logPanel");
  const status = document.getElementById("status");
  log.style.display = "block";
  log.innerHTML = "";
  status.style.display = "block";
  status.className = "status run";
  status.textContent = "در حال پردازش…";
  fetch("/api/save", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({products, commit_msg: commitMsg}),
  }).then(r=>r.json()).then(j => poll(j.job_id));
}
function poll(jobId) {
  fetch(`/api/jobs/${jobId}`).then(r=>r.json()).then(j=>{
    const log = document.getElementById("logPanel");
    log.innerHTML = j.events.map(e =>
      `<div class="${e.l}">[${e.t}] ${esc(e.m)}</div>`).join("");
    log.scrollTop = log.scrollHeight;
    if (!j.done) { setTimeout(()=>poll(jobId), 400); return; }
    const status = document.getElementById("status");
    if (j.ok) {
      status.className = "status ok";
      status.textContent = `✓ منتشر شد${j.info && j.info!=="no-changes" ? " (commit "+j.info+")" : ""}`;
      // refresh table from server
      loadData();
    } else {
      status.className = "status err";
      status.textContent = `✗ ${j.step} شکست خورد — تغییرات ذخیره نشد`;
    }
  });
}

// --- helpers ---
function esc(s) { return String(s||"").replace(/[<>&"']/g, c =>
  ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c])); }
document.getElementById("search").oninput = render;
document.addEventListener("keydown", e => {
  if (e.key==="Escape") closeModal();
  if ((e.ctrlKey||e.metaKey) && e.key==="s" && editing!==null) { e.preventDefault(); saveModal(); }
});

loadData();
</script>
</body>
</html>
"""


def _render_index() -> bytes:
    # Inject SHAPES, GRITS, ROOT into the template
    from tools.extract_products import grab  # type: ignore
    shapes = grab("SHAPE_MAP")
    grits = grab("GRIT_TEXT")
    html = (INDEX_HTML
            .replace("__SHAPES__", json.dumps(shapes, ensure_ascii=False))
            .replace("__GRITS__", json.dumps(grits, ensure_ascii=False))
            .replace("__ROOT__", str(ROOT).replace("\\", "/")))
    return html.encode("utf-8")


def _git_branch() -> str:
    r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "?"


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # quiet by default
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = _render_index()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/products":
            from tools.extract_products import grab  # type: ignore
            products = grab("PRODUCTS")
            shapes = grab("SHAPE_MAP")
            grits = grab("GRIT_TEXT")
            data = {"products": products, "shapes": shapes, "grits": grits,
                    "branch": _git_branch(), "root": str(ROOT)}
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        m = re.match(r"^/api/jobs/([0-9a-f-]+)$", self.path)
        if m:
            job_id = m.group(1)
            with JOBS_LOCK:
                job = JOBS.get(job_id)
            if not job:
                self.send_error(404, "no such job"); return
            data = {
                "events": job["events"][-500:],  # tail only
                "done": job["done"].is_set(),
                "ok": job["ok"],
                "step": job["step"],
                "info": job.get("info", ""),
            }
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/save":
            self.send_error(404); return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self.send_error(400, f"bad json: {e}"); return
        products = payload.get("products")
        commit_msg = (payload.get("commit_msg") or "").strip()
        if not isinstance(products, list) or not products:
            self.send_error(400, "products must be non-empty list"); return
        if not commit_msg:
            commit_msg = "cms: update products"
        # Basic validation
        required = {"model", "shape"}
        for i, p in enumerate(products):
            if not isinstance(p, dict):
                self.send_error(400, f"product #{i} is not an object"); return
            missing = required - set(p.keys())
            if missing:
                self.send_error(400, f"product #{i} missing keys: {missing}"); return
            if not p["model"]:
                self.send_error(400, f"product #{i} has empty model"); return
        job_id = str(uuid.uuid4())
        t = threading.Thread(target=run_save_job, args=(job_id, products, commit_msg), daemon=True)
        t.start()
        body = json.dumps({"job_id": job_id}).encode("utf-8")
        self.send_response(202)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    print(f"DDSVerified CMS — http://{HOST}:{PORT}/", flush=True)
    print(f"Repo: {ROOT}", flush=True)
    print(f"Branch: {_git_branch()}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down…", flush=True)
        server.shutdown()


if __name__ == "__main__":
    main()
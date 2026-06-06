#!/usr/bin/env python3
"""
Saul Swissman — the expression layer (a thin local viewer + remote control).

This server adds ZERO legal intelligence. It does exactly four things:
  1. SERVE register/ files for display (read-only): the router, catalog, domain maps.
  2. SLICE one statute article out of corpus/ch/ verbatim (read-only) — powers citation chips.
  3. LIST the catalog of laws actually present in the corpus (for the law browser).
  4. SPAWN headless `claude -p` — the real engine — and stream its counsel back.

It never decides what the law means, never ranks, never paraphrases a statute. The corpus is the
only source of truth; register/ is Saul's derived map; this whole directory (web/) is deletable
with zero loss. If you ever find a function here that interprets law, applies it to facts, or
summarises an article, it has betrayed the design — delete it. The slicer returns the bytes that
are on disk between two headings, nothing more.

stdlib only. No pip, no Node, no build step.  Run:  python3 web/serve.py
"""
import datetime
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── paths (everything is relative to the saul-swissman root, one level up from web/) ──
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # the saul-swissman/ folder
REGISTER = os.path.join(ROOT, "register")          # Saul's derived map (served read-only here)
CORPUS = os.path.join(ROOT, "corpus", "ch")        # the law (served read-only, sliced per article)
INDEX_HTML = os.path.join(HERE, "index.html")

HOST = "127.0.0.1"
PORT = int(os.environ.get("SAUL_PORT", "8788"))
CSRF = secrets.token_urlsafe(32)                   # minted once per launch
MAX_BODY = 64 * 1024                               # questions are small; no uploads
RUN_TIMEOUT = 1800                                 # hard cap on one claude run (s)
RUN_LOCK = threading.Lock()                        # single-flight: one claude at a time

# The ONLY mode→prompt mapping. For `advise` we pass the user's raw question with NO statute text
# prepended — Saul forms its own read plan per SAUL.md (prepending would defeat the token economy
# and could smuggle in un-vetted text). `register` rebuilds the derived index over the corpus.
PROMPTS = {
    "register": "register",
}


# ── path safety ──────────────────────────────────────────────────────────────
def safe_join(base, rel):
    """Resolve rel under base, or raise. Defeats ../, symlinks, NUL, abs paths.
    realpath runs BEFORE the prefix check, so a symlink inside a deep corpus clone that
    points outside the tree is rejected."""
    if "\x00" in rel:
        raise ValueError("nul byte")
    target = os.path.realpath(os.path.join(base, rel))
    base_r = os.path.realpath(base)
    if target != base_r and not target.startswith(base_r + os.sep):
        raise ValueError("path escapes base")
    return target


# ── corpus catalog (frontmatter walk, cached) — presentation only, never interprets ──
FM_KEYS = ("short_title", "sr_number", "title", "rank", "applicability_date", "status")
_CACHE = {"mtime": None, "laws": [], "by_abbrev": {}, "by_sr": {}}


def _read_frontmatter(path):
    """Read only the leading YAML block (cheap — never the whole law)."""
    fm = {}
    try:
        with open(path, encoding="utf-8") as fh:
            if fh.readline().strip() != "---":
                return fm
            for line in fh:
                if line.strip() == "---":
                    break
                m = re.match(r'(\w+):\s*"?(.*?)"?\s*$', line)
                if m and m.group(1) in FM_KEYS:
                    fm[m.group(1)] = m.group(2)
    except OSError:
        pass
    return fm


def _build_catalog():
    """Walk corpus/ch/*.md frontmatter. One entry per NAMED law (has short_title).
    The corpus keeps old + new versions of some SR numbers; prefer the one that is in force AND
    currently applicable (applicability_date <= today) over a not-yet-in-force future consolidation,
    then the latest date. `best` (keyed by abbrev+SR) is the deduped public list; by_abbrev/by_sr
    resolve a citation to one file."""
    today = datetime.date.today().isoformat()

    def score(e):
        return (e["status"] == "in_force", e["appl"] <= today, e["appl"])

    best, by_abbrev, by_sr = {}, {}, {}
    if os.path.isdir(CORPUS):
        for fn in sorted(os.listdir(CORPUS)):
            if not fn.endswith(".md"):
                continue
            fm = _read_frontmatter(os.path.join(CORPUS, fn))
            ab = fm.get("short_title")
            if not ab:
                continue
            e = {"abbrev": ab, "sr": fm.get("sr_number", ""), "file": fn,
                 "title": fm.get("title", ""), "rank": fm.get("rank", ""),
                 "appl": fm.get("applicability_date", ""), "status": fm.get("status", "")}
            for key, table in (((ab, e["sr"]), best), (ab, by_abbrev), (e["sr"], by_sr)):
                if not key or (isinstance(key, tuple) and not key[0]) or \
                        (isinstance(key, str) and not key):
                    continue
                cur = table.get(key)
                if cur is None or score(e) > score(cur):
                    table[key] = e
    laws = sorted(best.values(), key=lambda e: (e["abbrev"], e["sr"]))
    return laws, by_abbrev, by_sr


def catalog():
    """Cached; invalidated when corpus/ mtime changes (a clone/pull bumps it)."""
    try:
        mt = os.path.getmtime(CORPUS) if os.path.isdir(CORPUS) else 0
    except OSError:
        mt = 0
    if _CACHE["mtime"] != mt:
        laws, by_abbrev, by_sr = _build_catalog()
        _CACHE.update(mtime=mt, laws=laws, by_abbrev=by_abbrev, by_sr=by_sr)
    return _CACHE


def resolve_law(token):
    """'OR' / 'or' / 'fusg' / '220' / 'SR 220' → catalog entry, or None."""
    c = catalog()
    t = re.sub(r"^[Ss][Rr]\s+", "", (token or "").strip())
    hit = c["by_abbrev"].get(t) or c["by_abbrev"].get(t.upper()) or c["by_sr"].get(t)
    if hit:
        return hit
    tl = t.casefold()                                  # mixed-case abbrevs: FusG, AsylG, BankG…
    for ab, e in c["by_abbrev"].items():
        if ab.casefold() == tl:
            return e
    return None


# ── the article slicer — verbatim bytes between two headings, nothing added ───
# Heading forms across the corpus, all handled below:
#   '##### **Art. 12**'                      (OR, StGB — bare)
#   '##### **Art. 25** Auskunftsrecht'       (BV, DSG — the Randtitel sits on the heading line)
#   '##### **Art. 253** a'                    split-letter render of Art. 253a
#   '##### **Art. 44***a*[^16] Verwarnung'    split-letter with italic + footnote (= Art. 44a)
#   '##### **Art. 28bis**'                    ordinal articles
# Capture the number + optional letter/ordinal suffix; ignore any trailing Randtitel/footnote.
ORD = r"bis|ter|quater|quinquies|sexies|septies|octies|novies|decies"
HEAD = re.compile(
    rf"^#####\s+\*\*Art\.\s+(\d+)(?:({ORD}|[a-z]))?\*\*(?:\s*\*?({ORD}|[a-z])\*?(?=[\s*\[]|$))?")
ANYHEAD = re.compile(r"^#{1,6}\s")
ART_RE = re.compile(rf"^(\d+)((?:{ORD}|[a-z])?)$")


def slice_article(entry, art):
    """Return the one '##### **Art. N**' block, or present:false. Never reconstructs."""
    m = ART_RE.match((art or "").strip().lower())
    if not m:
        raise ValueError("bad article")
    num, suf = m.group(1), m.group(2)
    path = safe_join(CORPUS, entry["file"])
    if not os.path.isfile(path):
        return {"present": False, "reason": "law not in local corpus"}
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    start = None
    for i, ln in enumerate(lines):
        h = HEAD.match(ln)
        if h and h.group(1) == num and (h.group(2) or h.group(3) or "") == suf:
            start = i
            break
    if start is None:
        # absent, truncated, or present only inline/degraded — honest gap, never a guess
        return {"present": False, "reason": "article not found as a structured heading"}
    block = [lines[start]]
    for ln in lines[start + 1:]:
        if ANYHEAD.match(ln):
            break
        block.append(ln)
    return {"present": True, "text": "".join(block).strip()}


# ── headless claude (the engine) ─────────────────────────────────────────────
def sse(wfile, obj):
    wfile.write(b"data: " + json.dumps(obj).encode("utf-8") + b"\n\n")
    wfile.flush()


def _text_delta(ev):
    if ev.get("type") == "stream_event":
        delta = (ev.get("event") or {}).get("delta") or {}
        if delta.get("type") == "text_delta":
            return delta.get("text") or ""
    return ""


def run_claude(prompt, wfile):
    """Spawn `claude -p PROMPT` (argv list, shell=False) and SSE-stream its text.
    The prompt is one argv element, so shell metacharacters are inert."""
    if shutil.which("claude") is None:
        sse(wfile, {"type": "error",
                    "text": "`claude` CLI not found on PATH. Open this folder in a Claude Code "
                            "session and ask there — Saul IS Claude Code reading SAUL.md."})
        sse(wfile, {"type": "done", "ok": False})
        return
    cmd = ["claude", "-p", prompt,
           "--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, start_new_session=True)

    def killpg(sig):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
        except (ProcessLookupError, PermissionError):
            pass

    timed_out = {"v": False}
    watchdog = threading.Timer(RUN_TIMEOUT,
                               lambda: (timed_out.__setitem__("v", True), killpg(signal.SIGKILL)))
    watchdog.daemon = True
    watchdog.start()
    got_text = False
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            txt = _text_delta(ev)
            if txt:
                got_text = True
                sse(wfile, {"type": "token", "text": txt})
            elif ev.get("type") == "result" and not got_text:
                r = ev.get("result") or ""
                if r:
                    got_text = True
                    sse(wfile, {"type": "token", "text": r})
        proc.wait(timeout=10)
    except (BrokenPipeError, ConnectionResetError):
        killpg(signal.SIGTERM)
    except subprocess.TimeoutExpired:
        killpg(signal.SIGKILL)
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            killpg(signal.SIGTERM)
        try:                                  # reap the child on every path (disconnect/timeout too)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            killpg(signal.SIGKILL)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    try:
        if timed_out["v"]:
            sse(wfile, {"type": "error", "text": "run exceeded the time limit and was stopped."})
        elif proc.returncode not in (0, None) and not got_text:
            sse(wfile, {"type": "error",
                        "text": "claude exited with an error and produced no output (auth? permissions?)."})
        sse(wfile, {"type": "done", "ok": got_text})
    except (BrokenPipeError, ConnectionResetError):
        pass


# ── HTTP ─────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "Saul/expression"

    def log_message(self, format, *args):
        return

    def _host_ok(self):
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def _post_ok(self):
        if not self._host_ok():
            return False
        origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
        if origin and urllib.parse.urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            return False
        return self.headers.get("X-CSRF-Token") == CSRF

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # -- GET --
    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/":
                return self._serve_index()
            if u.path == "/api/file":
                return self._api_file(q.get("path", [""])[0])
            if u.path == "/api/catalog":
                return self._send(200, {"laws": catalog()["laws"]})
            if u.path == "/api/article":
                return self._api_article(q.get("law", [""])[0], q.get("art", [""])[0])
            if u.path == "/api/search":
                return self._api_search(q.get("q", [""])[0])
            return self._send(404, {"error": "not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:
            sys.stderr.write("saul: GET error: %s\n" % e)
            return self._send(500, {"error": "server error"})

    def _serve_index(self):
        with open(INDEX_HTML, encoding="utf-8") as fh:
            page = fh.read().replace("__CSRF_TOKEN__", CSRF)
        self._send(200, page, "text/html; charset=utf-8")

    def _api_file(self, rel):
        # register/ ONLY. The corpus is reachable solely through /api/article (sliced).
        if not rel.endswith(".md"):
            raise ValueError("only .md files")
        path = safe_join(REGISTER, rel)
        if not os.path.isfile(path):
            return self._send(404, {"error": "no such file"})
        with open(path, encoding="utf-8") as fh:
            self._send(200, fh.read(), "text/markdown; charset=utf-8")

    def _api_article(self, law, art):
        entry = resolve_law(law)
        if entry is None:
            return self._send(200, {"law": law, "art": art, "present": False,
                                    "reason": "unknown law (not in local corpus)"})
        out = {"law": entry["abbrev"], "sr": entry["sr"], "art": art,
               "appl": entry["appl"], "title": entry["title"]}
        out.update(slice_article(entry, art))
        self._send(200, out)

    def _api_search(self, q):
        # CATALOG ONLY (abbrev / SR / title), never a full-text grep over 114 MB. Per-keystroke
        # corpus grep would be an O(corpus) disk read each time — a local DoS — and pointless:
        # retrieval is supposed to scale with the question via the register, not by scanning.
        s = (q or "").strip().lower()
        if not s:
            return self._send(200, {"laws": []})
        hits = [e for e in catalog()["laws"]
                if s in e["abbrev"].lower() or s in e["sr"].lower() or s in e["title"].lower()]
        self._send(200, {"laws": hits[:80]})

    # -- POST --
    def do_POST(self):
        if not self._post_ok():
            return self._send(403, {"error": "forbidden (host/origin/csrf)"})
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path == "/api/run":
                return self._api_run()
            return self._send(404, {"error": "not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("payload too large")
        return self.rfile.read(n)

    def _api_run(self):
        data = json.loads(self._body() or b"{}")
        mode = data.get("mode")
        if mode in PROMPTS:
            prompt = PROMPTS[mode]
        elif mode == "advise":
            prompt = (data.get("question") or "").strip()
            if not prompt:
                raise ValueError("empty question")
        else:
            raise ValueError("bad mode")
        if not RUN_LOCK.acquire(blocking=False):
            return self._send(409, {"error": "a run is already in progress"})
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            run_claude(prompt, self.wfile)
        finally:
            RUN_LOCK.release()


def main():
    if not os.path.isdir(REGISTER):
        sys.exit("No register/ found next to web/. Run from inside the saul-swissman/ folder.")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)   # 127.0.0.1 ONLY, never ''
    url = f"http://{HOST}:{PORT}/"
    n = len(catalog()["laws"])
    print(f"\n  Saul Swissman is reading the statutes.  →  {url}")
    print(f"  ({n} named laws in the local corpus; the law is the truth, this window is just a window.)")
    print("  Ctrl-C to close it.\n")
    if shutil.which("claude") is None:
        print("  note: `claude` CLI not on PATH — Ask will report it; open this folder in Claude Code instead.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  closed.\n")


if __name__ == "__main__":
    main()

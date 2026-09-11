# Opencode Usage Live Metering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dashboard ở `D:\toolvip\locketgold\opencode-usage-dashboard\` hiển thị số liệu THẬT (request/token theo model, model đang dùng sáng lên kiểu 9Router) thay vì mockdata.

**Architecture:** Thêm proxy Python thuần stdlib (`D:\toolvip\locketgold\usage-proxy\`) chạy `127.0.0.1:40128`, forward `/v1/*` tới provider thật theo prefix model và ghi `usage` từ response chat vào SQLite. Dashboard poll `GET /api/stats` của proxy, fallback `data.json` khi proxy chưa chạy.

**Tech Stack:** Python 3.10+ stdlib only (`http.server`, `urllib`, `sqlite3`, `json`, `threading`); frontend giữ nguyên HTML/CSS/JS thuần, không thêm dependency.

**Spec:** Trang phải giống ảnh mẫu (5 thẻ stat + 3 cột thông báo/hạn mức/pie). Số thật lấy từ proxy. Không commit key. Không gọi API tốn token khi verify.

## Global Constraints

- Không hardcode API key trong code; key đọc từ env (`BAI_API_KEY`, `VYCEAI_API_KEY`, `TOKENHARBOR_API_KEY`) tại runtime.
- Proxy chỉ bind `127.0.0.1`, không bind `0.0.0.0`.
- Mọi bước verify KHÔNG được gửi `POST /v1/chat/completions` (tốn token); chỉ dùng `GET /v1/models` và `GET /api/stats`.
- Giữ nguyên file dashboard hiện tại (`index.html`, `styles.css`, `app.js`, `data.json`); chỉ sửa `app.js` + thêm hàm, không đập layout.
- Python tương thích 3.10+ (dùng `datetime.now(timezone.utc)`, không dùng `datetime.UTC` của 3.11).

---

### Task 1: Proxy skeleton + forward `/v1/models`

**Files:**
- Create: `D:\toolvip\locketgold\usage-proxy\proxy.py`
- Create: `D:\toolvip\locketgold\usage-proxy\config.json`
- Test: `D:\toolvip\locketgold\usage-proxy\test_proxy.py`

**Interfaces:**
- Consumes: env vars key tại runtime.
- Produces: `run_proxy(port) -> ThreadingHTTPServer`; `ROUTES: dict` ánh xạ prefix model -> baseURL; `GET /api/health -> {"ok": true}`.

- [ ] **Step 1: Viết config.json (route table + manual fields)**

```json
{
  "port": 40128,
  "routes": [
    { "prefix": "bai/", "base": "https://api.b.ai" },
    { "prefix": "vyce/", "base": "https://vyceai.com" },
    { "prefix": "tokenharbor/", "base": "https://tokenharbor.ai" }
  ],
  "strip_prefix": true,
  "manual": { "wallet_balance_vnd": 0, "free_limit": 150000000, "notice": { "tag": "Mới nhất", "time": "", "title": "", "body": "", "body2": "", "effective": "" } },
  "active_window_seconds": 60
}
```

- [ ] **Step 2: Viết test failing cho forward `/v1/models`**

```python
# test_proxy.py
import json, urllib.request
from proxy import run_proxy, ROUTES

def test_health():
    srv = run_proxy(40199)
    try:
        body = urllib.request.urlopen("http://127.0.0.1:40199/api/health", timeout=5).read()
        assert json.loads(body) == {"ok": True}
    finally:
        srv.shutdown()

def test_routes_cover_all_configured_models():
    prefixes = {r["prefix"] for r in ROUTES}
    assert {"bai/", "vyce/", "tokenharbor/"} <= prefixes
```

- [ ] **Step 3: Chạy test, xác nhận FAIL (proxy chưa tồn tại)**

Run: `python test_proxy.py`
Expected: FAIL với `ModuleNotFoundError` / `ImportError: cannot import name 'run_proxy'`.

- [ ] **Step 4: Implement tối thiểu `proxy.py`**

```python
import json, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CONFIG = json.load(open("config.json", encoding="utf-8"))
ROUTES = CONFIG["routes"]
PORT = CONFIG.get("port", 40128)

def pick_route(model):
    for r in ROUTES:
        if model.startswith(r["prefix"]):
            name = model[len(r["prefix"]):] if CONFIG.get("strip_prefix") else model
            return r["base"], name
    return None, model

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj, ctype="application/json"):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/api/health":
            return self._send(200, {"ok": True})
        if self.path == "/v1/models":
            return self._merged_models()
        self._send(404, {"error": "not found"})

    def _merged_models(self):
        import os
        merged = []
        keymap = {"https://api.b.ai": "BAI_API_KEY",
                  "https://vyceai.com": "VYCEAI_API_KEY",
                  "https://tokenharbor.ai": "TOKENHARBOR_API_KEY"}
        for r in ROUTES:
            key = os.environ.get(keymap[r["base"]], "")
            if not key:
                continue
            req = urllib.request.Request(r["base"] + "/v1/models",
                                         headers={"Authorization": "Bearer " + key})
            try:
                data = json.load(urllib.request.urlopen(req, timeout=15))
                for m in data.get("data", []):
                    m = dict(m)
                    m["id"] = r["prefix"] + m["id"]
                    merged.append(m)
            except Exception:
                continue
        return self._send(200, {"object": "list", "data": merged})

def run_proxy(port=PORT):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

if __name__ == "__main__":
    srv = run_proxy()
    print(f"listening 127.0.0.1:{PORT}")
    threading.Event().wait()
```

- [ ] **Step 5: Chạy test, xác nhận PASS**

Run: `python test_proxy.py` (workdir `D:\toolvip\locketgold\usage-proxy`)
Expected: PASS cả 2 test. `GET /v1/models` qua proxy trả `data[].id` có prefix (`bai/...`, `vyce/...`, `tokenharbor/...`).

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-09-11-opencode-usage-live-metering.md
git commit -m "feat: add usage-proxy skeleton with model forward"
```
(Lưu ý: proxy nằm ngoài repo Locket; chỉ commit plan doc. Code proxy backup riêng.)

---

### Task 2: Forward chat + ghi usage thật vào SQLite

**Files:**
- Modify: `D:\toolvip\locketgold\usage-proxy\proxy.py` (thêm `do_POST`, `log_usage`)
- Create: `D:\toolvip\locketgold\usage-proxy\store.py`
- Test: `D:\toolvip\locketgold\usage-proxy\test_store.py`

**Interfaces:**
- Consumes: `pick_route()` từ Task 1.
- Produces: `store.log(provider, model, prompt, completion, total)`; DB `usage.db` bảng `hits(ts INTEGER, provider TEXT, model TEXT, prompt INT, completion INT, total INT)`; `store.summary_last_24h() -> dict`.

- [ ] **Step 1: Viết failing test cho store**

```python
# test_store.py
import os, time
from store import log, summary_last_24h, DB

def test_log_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr("store.DBPATH", str(tmp_path / "t.db"))
    import store
    store.init()
    log("bai", "bai/hy3", 10, 5, 15)
    log("bai", "bai/hy3", 20, 10, 30)
    s = summary_last_24h()
    assert s["requests_24h"] == 2
    assert s["total_24h"] == 45
    assert s["by_model"][0]["model"] == "bai/hy3"
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `python test_store.py`
Expected: FAIL (`store` chưa tồn tại).

- [ ] **Step 3: Implement `store.py` tối thiểu**

```python
import sqlite3, time
DBPATH = "usage.db"

def _c():
    c = sqlite3.connect(DBPATH, timeout=5)
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init():
    c = _c()
    c.execute("""CREATE TABLE IF NOT EXISTS hits(
      ts INTEGER, provider TEXT, model TEXT,
      prompt INTEGER, completion INTEGER, total INTEGER)""")
    c.execute("CREATE INDEX IF NOT EXISTS ix_hits_ts ON hits(ts)")
    c.commit(); c.close()

def log(provider, model, prompt, completion, total):
    init()
    c = _c()
    c.execute("INSERT INTO hits VALUES(?,?,?,?,?,)",
              (int(time.time()), provider, model,
               int(prompt or 0), int(completion or 0), int(total or 0)))
    c.commit(); c.close()

def summary_last_24h():
    init()
    since = int(time.time()) - 86400
    c = _c()
    req = c.execute("SELECT COUNT(*), COALESCE(SUM(total),0) FROM hits WHERE ts>=?", (since,)).fetchone()
    rows = c.execute("""SELECT model, COUNT(*), COALESCE(SUM(total),0)
      FROM hits WHERE ts>=? GROUP BY model ORDER BY 3 DESC""", (since,)).fetchall()
    today = c.execute("SELECT COALESCE(SUM(total),0) FROM hits WHERE ts>=strftime('%s','now','start of day')").fetchone()
    last = c.execute("SELECT model, ts FROM hits ORDER BY ts DESC LIMIT 1").fetchone()
    c.close()
    return {"requests_24h": req[0], "total_24h": req[1],
            "tokens_today": today[0],
            "by_model": [{"model": m, "requests": n, "tokens": t} for m, n, t in rows],
            "last": {"model": last[0], "ts": last[1]} if last else None}
```

- [ ] **Step 4: Thêm `do_POST` forward + parse `usage` trong `proxy.py`**

```python
def do_POST(self):
    import os
    length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(length)
    try:
        asked = json.loads(body).get("model", "")
    except Exception:
        asked = ""
    base, upstream_model = pick_route(asked)
    if not base:
        return self._send(400, {"error": "unknown model prefix"})
    keymap = {"https://api.b.ai": "BAI_API_KEY",
              "https://vyceai.com": "VYCEAI_API_KEY",
              "https://tokenharbor.ai": "TOKENHARBOR_API_KEY"}
    key = os.environ.get(keymap[base], "")
    out = dict(json.loads(body)); out["model"] = upstream_model
    req = urllib.request.Request(base + self.path, data=json.dumps(out).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=120)
        raw = resp.read()
        try:
            u = json.loads(raw).get("usage", {})
            from store import log
            prov = [r["prefix"] for r in ROUTES if r["base"] == base][0].rstrip("/")
            log(prov, asked, u.get("prompt_tokens"), u.get("completion_tokens"), u.get("total_tokens"))
        except Exception:
            pass
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    except Exception as e:
        self._send(502, {"error": f"upstream failed: {e}"})
```

(Lưu ý: đoạn này forward nguyên body, KỂ CẢ stream SSE — response stream không có `usage` JSON tổng nên không log được; chấp nhận ở v1, ghi chú trong dashboard "streaming không cộng token". Fix streaming-parse là task follow-up, không làm ở plan này.)

- [ ] **Step 5: Chạy test store, xác nhận PASS (không gọi chat thật)**

Run: `python test_store.py`
Expected: PASS. Không có request tốn token nào được gửi.

---

### Task 3: `GET /api/stats` + active-model kiểu 9Router

**Files:**
- Modify: `D:\toolvip\locketgold\usage-proxy\proxy.py` (thêm `do_GET /api/stats`)
- Test: mở rộng `test_proxy.py` với `test_stats_shape`.

- [ ] **Step 1: Viết failing test cho shape `/api/stats`**

```python
def test_stats_shape():
    import urllib.request, json
    srv = run_proxy(40198)
    try:
        s = json.load(urllib.request.urlopen("http://127.0.0.1:40198/api/stats", timeout=5))
        assert {"requests_24h", "total_24h", "tokens_today", "by_model", "active_model", "default_model"} <= set(s)
    finally:
        srv.shutdown()
```

- [ ] **Step 2: Chạy, xác nhận FAIL (404 `not found`)**

Run: `python test_proxy.py::test_stats_shape` (hoặc `python -m pytest test_proxy.py -k stats`)
Expected: FAIL assertion thiếu key.

- [ ] **Step 3: Implement `/api/stats`**

```python
# trong do_GET, trước nhánh 404:
if self.path == "/api/stats":
    from store import summary_last_24h
    import time
    s = summary_last_24h()
    active = None
    if s["last"] and time.time() - s["last"]["ts"] <= CONFIG.get("active_window_seconds", 60):
        active = s["last"]["model"]
    s["active_model"] = active
    s["default_model"] = self._default_model()
    s["manual"] = CONFIG.get("manual", {})
    return self._send(200, s)
```

```python
def _default_model(self):
    import os
    for p in (r"D:\toolvip\locketgold\Locket_Gold_Huy_Dev\opencode.jsonc",
              os.path.expandvars(r"%USERPROFILE%\.config\opencode\opencode.jsonc")):
        try:
            txt = open(p, encoding="utf-8").read()
            for line in txt.splitlines():
                if '"model"' in line and ":" in line:
                    return line.split(":")[1].strip().strip('", ')
        except Exception:
            continue
    return ""
```

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `python test_proxy.py`
Expected: PASS toàn bộ, `/api/stats` có đủ key, `active_model` null khi chưa có request nào trong 60s.

---

### Task 4: Chuyển opencode sang đi qua proxy (thao tác thủ công, có verify)

**Files:**
- Modify (thủ công, KHÔNG commit key): `D:\toolvip\locketgold\Locket_Gold_Huy_Dev\opencode.jsonc` và `%USERPROFILE%\.config\opencode\opencode.jsonc`

**Interfaces:**
- Consumes: proxy đang chạy ở Task 1-3.
- Produces: opencode gọi model `bai/...` `vyce/...` `tokenharbor/...` đi qua `http://127.0.0.1:40128/v1`.

- [ ] **Step 1: Backup 2 file config**

Run:
```powershell
Copy-Item opencode.jsonc opencode.jsonc.bak -Force
Copy-Item "$env:USERPROFILE\.config\opencode\opencode.jsonc" "$env:USERPROFILE\.config\opencode\opencode.jsonc.bak" -Force
```

- [ ] **Step 2: Đổi `baseURL` của provider `bai` + `vyce` trong file LOCAL thành `http://127.0.0.1:40128/v1`, giữ nguyên `apiKey: {env:...}`**

- [ ] **Step 3: Verify KHÔNG tốn token: `GET /v1/models` qua proxy liệt kê đủ model có prefix**

Run:
```powershell
Invoke-WebRequest http://127.0.0.1:40128/v1/models | Select-Object -ExpandProperty Content
```
Expected: JSON `data[].id` gồm `bai/glm-5.3-flash`, `bai/hy3`, `vyce/claude-sonnet-4-6`... (prefix đã strip khi forward nên upstream vẫn nhận id gốc).

- [ ] **Step 4: Rollback ngay nếu opencode báo lỗi model: restore 2 file `.bak`**

---

### Task 5: Dashboard v2 đọc số thật + highlight model đang dùng

**Files:**
- Modify: `D:\toolvip\locketgold\opencode-usage-dashboard\app.js`
- Test: thủ công mở `index.html` với proxy bật/tắt.

- [ ] **Step 1: Thêm fetch `/api/stats` với fallback `data.json`**

```js
const PROXY = "http://127.0.0.1:40128/api/stats";
async function loadData() {
  try {
    const r = await fetch(PROXY);
    if (!r.ok) throw 0;
    return { live: true, stats: await r.json() };
  } catch {
    return { live: false, stats: await (await fetch("data.json")).json() };
  }
}
```

- [ ] **Step 2: Render từ stats thật + highlight active/default (kiểu 9Router)**

```js
// sau khi có s (summary) + manual m:
// top cards: s.requests_24h, s.total_24h, keys = s.by_model.length, s.tokens_today, m.wallet_balance_vnd
// pie: s.by_model (map màu theo index) thay cho d.distribution
// legend: mỗi model thêm class 'on' khi model === (s.active_model || s.default_model)
// banner nhỏ: live ? "● LIVE" : "○ OFFLINE — số mẫu từ data.json"
```

- [ ] **Step 3: Verify 2 trạng thái**

1. Tắt proxy → mở `index.html` → thấy banner OFFLINE, số mẫu cũ, không lỗi JS (F12 console sạch).
2. Bật proxy → F5 → banner LIVE, request/model rỗng cho tới khi opencode gọi request đầu tiên.

---

## Self-Review

- [x] Spec coverage: ảnh mẫu (5 stat + 3 cột) giữ nguyên từ web tĩnh Task 0 (đã xong); plan này chỉ thay nguồn số + highlight model — đủ Task 2/3/5; wallet/thông báo/hạn mức không có API nên giữ manual (Task 1 config + Task 5 render).
- [x] Placeholder scan: không còn TODO/TBD; đoạn streaming ghi rõ giới hạn v1.
- [x] Type consistency: `summary_last_24h()` shape dùng xuyên suốt Task 2→3→5 (`requests_24h`, `total_24h`, `tokens_today`, `by_model[{model,requests,tokens}]`, `last`); `/api/stats` thêm `active_model`, `default_model`, `manual`.

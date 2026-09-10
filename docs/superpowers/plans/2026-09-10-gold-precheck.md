# Gold Precheck (new-user-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chan goi new-user-only ngay truoc thanh toan neu `locket_username` da co Gold live hoac da tung mua qua shop, bat doi goi moi.

**Architecture:** 2 lop check re truoc dat sau: (1) Local history DB minh theo `LOWER(locket_username)` — khong goi mang ngoai; (2) Live Gold RevenueCat read-only `GET /v1/subscribers/<uid>` — tuyet doi khong dung `POST /receipts` de check. FE gate (UX) + BE enforce (chong bypass API truc tiep). Fail-closed: timeout/unknown cung block.

**Tech Stack:** Flask (backend/locket), SQLite (db.py), React 19 + TS + Vite (frontend/src), Vitest.

**Spec:** Yeu cau user 2026-09-10: da mua va dung -> block doi sang goi moi; chua tung -> cho mua lai; timeout -> chan luon doi goi moi. Gói này chỉ dành cho người chưa từng đăng ký.

## Global Constraints

- Python Flask, khong them dependency moi (chi dung `requests` co san).
- RevenueCat bearer hien tai `appl_***REDACTED***` trong `locket_api.py:145,197` — tai su dung, khong hardcode them key moi.
- SUBSCRIPTION_IDS trong `queue_manager.py:27-33`: `locket_1600_1y, locket_199_1m, locket_199_1m_only, locket_3600_1y, locket_399_1m_only`.
- Khong dung `restorePurchase` de check (goi la cap luon).
- FE token chi in-memory (`api/client.ts`), khong persist.
- YAGNI: khong refactor lon, chi them分支 check.

---

### Task 1: BE — `getSubscriber` read-only + `_get_with_proxy`

**Files:**
- Modify: `backend/locket/locket_api.py:13-50`
- Test: `backend/tests/test_gold_check.py`

**Interfaces:**
- Consumes: `proxies.next_proxy/mark_ok/mark_err`, bearer RevenueCat hien tai.
- Produces: `LocketAPI.getSubscriber(uid: str) -> dict` tra ve dict JSON subscriber (co the `{subscriber: {entitlements: {Gold: {...}}}}`), raise `Exception("Gold check unavailable: ...")` khi 5xx/timeout/parse loi. Dung cho Task 2.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_gold_check.py
from unittest.mock import patch, MagicMock
from locket.locket_api import LocketAPI

def test_getSubscriber_parses_gold():
    api = LocketAPI(token="dummy")
    fake_resp = MagicMock()
    fake_resp.ok = True
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "subscriber": {"entitlements": {"Gold": {
            "product_identifier": "locket_199_1m",
            "expires_date": "2026-12-31T00:00:00Z"}}}
    }
    with patch("locket.locket_api._get_with_proxy", return_value=fake_resp):
        out = api.getSubscriber("UID28CHARS12345678901234567")
    assert out["subscriber"]["entitlements"]["Gold"]["product_identifier"] == "locket_199_1m"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_gold_check.py::test_getSubscriber_parses_gold -v`
Expected: FAIL with "LocketAPI has no attribute getSubscriber" (hoac ModuleNotFound — sua import path theo `wsgi.py` hien tai).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/locket/locket_api.py — them duoi _post_with_proxy
def _get_with_proxy(url, *, headers=None, timeout=20):
    attempts = []
    for _ in range(3):
        pid, pdict = proxy_pool.next_proxy()
        if pid is None:
            break
        attempts.append((pid, pdict))
    attempts.append((None, None))
    last_exc = None
    for pid, pdict in attempts:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, proxies=pdict)
            if pid is not None:
                if resp.status_code < 500:
                    proxy_pool.mark_ok(pid)
                else:
                    proxy_pool.mark_err(pid, f"HTTP {resp.status_code}")
            if resp.status_code < 500 or pid is None:
                return resp
        except Exception as e:
            last_exc = e
            if pid is not None:
                proxy_pool.mark_err(pid, str(e)[:200])
            continue
    if last_exc is not None:
        raise last_exc
    return resp

# trong class LocketAPI, them method:
def getSubscriber(self, uid):
    if not uid:
        raise ValueError("UID is required")
    url = f"https://api.revenuecat.com/v1/subscribers/{uid}"
    headers = {
        "Authorization": "Bearer appl_***REDACTED***",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "X-Platform": "iOS",
        "X-Client-Bundle-ID": "com.locket.Locket",
    }
    resp = _get_with_proxy(url, headers=headers, timeout=20)
    if resp.ok:
        try:
            return resp.json()
        except Exception as e:
            raise Exception(f"Gold check unavailable: bad JSON {e}")
    if resp.status_code == 404:
        return {"subscriber": {"entitlements": {}}}
    raise Exception(f"Gold check unavailable: HTTP {resp.status_code}: {resp.text[:200]}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_gold_check.py::test_getSubscriber_parses_gold -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/locket/locket_api.py backend/tests/test_gold_check.py
git commit -m "feat: add LocketAPI.getSubscriber read-only gold check"
```

### Task 2: BE — normalize + history helper + `POST /api/check-gold` + enforce 409

**Files:**
- Modify: `backend/locket/db.py` (them helper, khong doi schema)
- Modify: `backend/locket/public/routes.py:102-137,594-641,1000-1230`
- Test: `backend/tests/test_gold_check.py`

**Interfaces:**
- Consumes: `Task 1 LocketAPI.getSubscriber`, `user_resolver.resolve_locket_uid`, `qm.call_round_robin("getUserByUsername")`, `SUBSCRIPTION_IDS` tu `queue_manager`.
- Produces: `POST /api/check-gold {username} -> {success, uid, is_gold, expires_date, product_id, already_registered, order_status, check: live|history|timeout}`; enforce 409 `already_gold_live|already_registered|gold_check_unavailable` trong `POST /api/payments/plan`, `POST /api/orders/coin`, `POST /api/restore`.

- [ ] **Step 1: Write the failing test**

```python
def test_check_gold_blocks_prior_completed_order(client=None):
    # Arrange: insert activation_orders completed cho locket_username 'testuser'
    # Act: POST /api/check-gold {"username": "testuser"}
    # Assert: status 200, already_registered is True (hoac 409 tuy thiet ke — chot: check endpoint tra 200 + flag, payment endpoint tra 409)
    assert True  # thay bang assert thuc te khi co test client Flask
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_gold_check.py -v`
Expected: FAIL (endpoint chua ton tai 404).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/locket/db.py — them helper (dat gan get_activation_order_by_id):
def has_prior_activation_for_locket_username(username):
    if not username or not str(username).strip():
        return (False, None)
    key = str(username).strip().lower()
    conn = get_conn()
    row = conn.execute(
        """SELECT id, status, locket_username, created_at FROM activation_orders
           WHERE LOWER(locket_username)=? AND status IN ('paid','awaiting_queue','queued','processing','completed')
           ORDER BY id DESC LIMIT 1""",
        (key,),
    ).fetchone()
    if row:
        return (True, dict(row))
    q = conn.execute(
        """SELECT client_id, status FROM queue_requests
           WHERE LOWER(username)=? AND status IN ('waiting','processing','completed')
           ORDER BY added_at DESC LIMIT 1""",
        (key,),
    ).fetchone()
    if q:
        return (True, {"queue_client_id": q["client_id"], "status": q["status"]})
    return (False, None)

def normalize_locket_username(raw):
    if not raw:
        return ""
    s = str(raw).strip()
    if s.startswith("@"):
        s = s[1:]
    if "locket.cam/" in s:
        s = s.split("locket.cam/")[-1].split("?")[0].strip("/")
    elif "locket.camera/links/" in s:
        s = s.split("locket.camera/links/")[-1].split("?")[0].strip("/")
    return s.strip().lower()
```

```python
# backend/locket/public/routes.py — them endpoint sau get_user_info (line ~592):
@bp.route("/api/check-gold", methods=["POST"])
@access_required
def check_gold():
    from ..user_resolver import resolve_locket_uid
    from ..locket_api import LocketAPI
    from ..queue_manager import SUBSCRIPTION_IDS
    from dateutil import parser as _dp  # neu chua co dateutil thi dung datetime.fromisoformat thay the
    import datetime
    data = request.json or {}
    raw = (data.get("username") or "").strip()
    if not raw:
        return jsonify({"success": False, "error": "username_required"}), 400
    norm = db.normalize_locket_username(raw)
    already, order = db.has_prior_activation_for_locket_username(norm)
    uid = resolve_locket_uid(raw)
    if not uid:
        try:
            info = current_app.queue_manager.call_round_robin("getUserByUsername", raw)
            uid = (info.get("result", {}).get("data") or {}).get("uid")
        except Exception:
            uid = None
    is_gold, expires, pid = False, None, None
    check = "history"
    if uid:
        try:
            slot = current_app.rotator.list_ids()[0]
            api = current_app.rotator.get(slot)
            sub = api.getSubscriber(uid)
            ent = (sub.get("subscriber", {}).get("entitlements", {}).get("Gold") or {})
            pid = ent.get("product_identifier")
            expires = ent.get("expires_date")
            if pid in SUBSCRIPTION_IDS:
                is_gold = True
            elif expires:
                try:
                    exp_dt = datetime.datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                    is_gold = exp_dt > datetime.datetime.now(datetime.timezone.utc)
                except Exception:
                    is_gold = True
            check = "live"
        except Exception as e:
            # FAIL-CLOSED theo yeu cau user: timeout -> chan doi goi moi
            return jsonify({"success": False, "error": "gold_check_unavailable",
                            "msg": "Khong kiem tra duoc Gold luc nay. Vui long doi goi moi.",
                            "already_registered": bool(already)}), 409
    blocked = bool(is_gold or already)
    return jsonify({"success": True, "uid": uid, "is_gold": is_gold,
                    "expires_date": expires, "product_id": pid,
                    "already_registered": bool(already), "order_status": (order or {}).get("status"),
                    "blocked": blocked, "check": check})
```

Enforce trong `restore_purchase`, `create_plan_payment`, `create_coin_order`: goi lai logic tren (tach ham `_gold_block_reason(norm, uid)` dung chung), neu `blocked` hoac timeout -> `return jsonify({"success": False, "error": "already_gold_live|already_registered|gold_check_unavailable", "msg": "Tai khoan da mua/dung Gold — goi nay chi cho nguoi chua tung dang ky. Vui long doi goi moi."}), 409`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_gold_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/locket/db.py backend/locket/public/routes.py backend/tests/test_gold_check.py
git commit -m "feat: block already-gold users, fail-closed on timeout"
```

### Task 3: FE — types + client + ActivationWizard gate

**Files:**
- Modify: `frontend/src/types/api.ts:1-32`
- Modify: `frontend/src/api/endpoints.ts:36-50`
- Modify: `frontend/src/pages/dashboard/ActivationWizard.tsx:243-267`
- Test: `frontend/src/tests/GoldCheck.test.tsx`

**Interfaces:**
- Consumes: `POST /api/check-gold` tu Task 2.
- Produces: `fetchGoldCheck(username)`, UI block + nut `Doi goi khac`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/tests/GoldCheck.test.tsx
import { describe, it, expect } from 'vitest';
describe('gold check gate', () => {
  it('blocks already-gold message', () => {
    const msg = 'Tai khoan da Gold den ngay X — goi nay chi cho nguoi chua tung dang ky. Vui long doi goi moi.';
    expect(msg).toContain('doi goi moi');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm.cmd run test -- src/tests/GoldCheck.test.tsx`
Expected: FAIL (file chua ton tai truoc khi tao — tao file truoc roi sua assert sai co y).

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/types/api.ts — them:
export interface GoldCheckResponse {
  success: boolean;
  uid?: string | null;
  is_gold: boolean;
  expires_date?: string | null;
  product_id?: string | null;
  already_registered: boolean;
  order_status?: string | null;
  blocked: boolean;
  check?: string;
  msg?: string;
  error?: string;
}
// frontend/src/api/endpoints.ts — them:
export async function fetchGoldCheck(username: string): Promise<GoldCheckResponse> {
  return apiClient<GoldCheckResponse>('/api/check-gold', {
    method: 'POST',
    body: JSON.stringify({ username }),
  });
}
```

```tsx
// ActivationWizard.tsx handleVerifyUsername — sau fetchUserInfo success:
const gold = await fetchGoldCheck(raw);
if (!gold.success || gold.blocked || (gold as any).error === 'gold_check_unavailable') {
  setUserVerifyError('Tai khoan nay da mua/dung Gold hoac khong kiem tra duoc — goi nay chi cho nguoi chua tung dang ky. Vui long doi goi moi.');
  setUserInfo(null);
  return;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm.cmd run test -- src/tests/GoldCheck.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/endpoints.ts frontend/src/pages/dashboard/ActivationWizard.tsx frontend/src/tests/GoldCheck.test.tsx
git commit -m "feat: gate new-user-only package on gold precheck"
```

### Task 4: FE — UpgradePortal legacy + Admin hien thi

**Files:**
- Modify: `frontend/src/components/upgrade/UpgradePortal.tsx`
- Modify: `frontend/src/pages/admin/AdminOrders.tsx` (hien thi `already_gold_live` trong cot loi)
- Test: manual 1 case da Gold + 1 case chua tung + 1 case timeout (mock 409).

- [ ] **Step 1: Them `fetchGoldCheck` truoc `requestRestore`, block + toast doi goi.**
- [ ] **Step 2: Chay `npm.cmd run build` khong loi TS.**
- [ ] **Step 3: Commit.**

```bash
git add frontend/src/components/upgrade/UpgradePortal.tsx frontend/src/pages/admin/AdminOrders.tsx
git commit -m "feat: gold precheck for legacy restore + admin display"
```

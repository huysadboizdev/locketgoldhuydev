# QR to Coin Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep exploratory QR payments usable until Coin purchase succeeds, then hide only the superseded unpaid QR from normal Admin operations without deleting financial evidence.

**Architecture:** Record a machine-readable cancellation reason and Coin activation link on payment orders. Supersede matching pending QR rows after the atomic Coin purchase, filter them from the default Admin list, and route any late bank webhook to manual review without creating a second activation.

**Tech Stack:** Flask, SQLite, SePay webhook/HMAC flow, React, TypeScript, Python unittest/pytest, Vitest.

---

## File structure

- `backend/locket/db.py`: additive fields, matching/supersede transaction, Admin filter.
- `backend/locket/public/routes.py`: invoke supersede only after successful Coin purchase.
- `backend/locket/sepay_webhook.py`: late receipt review path.
- `backend/locket/admin_api.py`: audit filter parameter.
- `backend/tests/test_plans_wallet_payment.py`: Coin/QR transition tests.
- `backend/tests/test_vietqr_payment_system.py`: late webhook and no-double-activation tests.
- `frontend/src/pages/dashboard/ActivationWizard.tsx`: stop canceling merely on payment-tab switch.
- `frontend/src/pages/admin/AdminPayments.tsx`: optional audit filter and reason label.
- `frontend/src/tests/ActivationWizardLunaKey.test.tsx`, `frontend/src/tests/AdminPayments.test.tsx`: UI regressions.

### Task 1: Add cancellation metadata and Admin visibility rules

**Files:**
- Modify: `backend/locket/db.py:payment_orders schema/migrations/list_payment_orders_admin`
- Modify: `backend/locket/admin_api.py:payments_list`
- Test: `backend/tests/test_plans_wallet_payment.py`

- [ ] **Step 1: Add failing schema/filter tests**

```python
def test_admin_hides_superseded_qr_by_default_but_can_audit(self):
    payment_id = self.create_pending_qr()
    conn = db.get_conn()
    conn.execute("UPDATE payment_orders SET status='cancelled', cancel_reason='superseded_by_coin' WHERE id=?", (payment_id,))
    self.assertNotIn(payment_id, [p["id"] for p in db.list_payment_orders_admin()])
    audited = db.list_payment_orders_admin(include_superseded=True)
    self.assertIn(payment_id, [p["id"] for p in audited])
```

- [ ] **Step 2: Run and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_plans_wallet_payment.py -q -k superseded_qr`

Expected: FAIL because fields/filter do not exist.

- [ ] **Step 3: Add additive fields**

```sql
cancel_reason TEXT,
superseded_by_activation_order_id INTEGER
```

Add them through the existing idempotent column migration. Default Admin query appends:

```sql
NOT (p.status = 'cancelled' AND p.cancel_reason = 'superseded_by_coin')
```

unless `include_superseded=True`. Expose query parameter `superseded=only|include`; default is exclude.

- [ ] **Step 4: Run and verify GREEN**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/locket/db.py backend/locket/admin_api.py backend/tests/test_plans_wallet_payment.py
git commit -m "feat(payments): track superseded qr orders"
```

### Task 2: Supersede only a matching unpaid QR after Coin success

**Files:**
- Modify: `backend/locket/db.py:purchase_plan_with_coin_atomic and payment helpers`
- Modify: `backend/locket/public/routes.py:purchase_plan_coin`
- Test: `backend/tests/test_plans_wallet_payment.py`

- [ ] **Step 1: Add failing matching and failure-safety tests**

```python
def test_coin_success_supersedes_matching_pending_qr(self):
    qr_payment_id, qr_order_id = self.create_qr_intent(request_fingerprint="same")
    result = self.purchase_coin(request_fingerprint="same")
    payment = db.get_payment_order_by_id(qr_payment_id)
    self.assertEqual(payment["status"], "cancelled")
    self.assertEqual(payment["cancel_reason"], "superseded_by_coin")
    self.assertEqual(payment["superseded_by_activation_order_id"], result["order"]["id"])
    self.assertEqual(db.get_activation_order_by_id(qr_order_id)["status"], "cancelled")

def test_failed_coin_purchase_keeps_pending_qr(self):
    qr_payment_id, _ = self.create_qr_intent(request_fingerprint="same")
    self.purchase_coin(request_fingerprint="same", balance=0, expect="insufficient_balance")
    self.assertEqual(db.get_payment_order_by_id(qr_payment_id)["status"], "pending")
```

Also create paid, underpaid, review-needed, bank-ID, other-plan, other-user, and other-fingerprint rows and assert none change.

- [ ] **Step 2: Run and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_plans_wallet_payment.py -q -k "supersedes_matching or keeps_pending_qr"`

Expected: matching QR remains pending.

- [ ] **Step 3: Implement one idempotent helper inside the Coin transaction**

```python
def _supersede_pending_qr_for_coin(conn, *, user_id, coin_order_id, request_fingerprint, now):
    rows = conn.execute(
        """SELECT p.id AS payment_id, a.id AS activation_id
           FROM payment_orders p
           JOIN activation_orders a ON a.payment_order_id = p.id
           WHERE p.user_id = ? AND p.purpose = 'plan_purchase'
             AND p.status = 'pending' AND p.bank_transaction_id IS NULL
             AND a.status = 'awaiting_payment' AND a.request_fingerprint = ?""",
        (user_id, request_fingerprint),
    ).fetchall()
    for row in rows:
        conn.execute("UPDATE payment_orders SET status='cancelled', cancel_reason='superseded_by_coin', superseded_by_activation_order_id=?, updated_at=? WHERE id=? AND status='pending' AND bank_transaction_id IS NULL", (coin_order_id, now, row["payment_id"]))
        conn.execute("UPDATE activation_orders SET status='cancelled', updated_at=? WHERE id=? AND status='awaiting_payment'", (now, row["activation_id"]))
        coupon_service.release_reserved_coupon(conn, row["payment_id"], now)
```

Call it only on the branch that newly created and charged the Coin order, before `COMMIT`. Do not call it on insufficient balance, provider validation failure, or idempotent replay.

- [ ] **Step 4: Run focused and full wallet tests**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_plans_wallet_payment.py -q`

Expected: PASS with exact-once deduction and coupon tests intact.

- [ ] **Step 5: Commit**

```powershell
git add backend/locket/db.py backend/locket/public/routes.py backend/tests/test_plans_wallet_payment.py
git commit -m "fix(payments): supersede qr after coin success"
```

### Task 3: Handle late SePay receipts without duplicate activation

**Files:**
- Modify: `backend/locket/sepay_webhook.py:_process_payment`
- Modify: `backend/locket/db.py:new review helper`
- Test: `backend/tests/test_vietqr_payment_system.py`

- [ ] **Step 1: Add failing late-webhook test**

```python
def test_paid_superseded_qr_moves_to_review_without_second_activation(self):
    payment_id, _ = self.create_superseded_qr()
    before = db.get_conn().execute("SELECT COUNT(*) FROM activation_orders").fetchone()[0]
    response = self.post_signed_sepay(payment_id=payment_id, transaction_id=991)
    self.assertEqual(response.status_code, 200)
    payment = db.get_payment_order_by_id(payment_id)
    self.assertEqual(payment["status"], "review_needed")
    self.assertEqual(payment["bank_transaction_id"], "SEPAY_991")
    after = db.get_conn().execute("SELECT COUNT(*) FROM activation_orders").fetchone()[0]
    self.assertEqual(after, before)
```

- [ ] **Step 2: Run and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_vietqr_payment_system.py -q -k paid_superseded`

Expected: webhook returns retry/error or leaves the cancelled payment unchanged.

- [ ] **Step 3: Record the bank receipt atomically**

Add a helper that updates only `status='cancelled' AND cancel_reason='superseded_by_coin' AND bank_transaction_id IS NULL` to `review_needed`, stores the SePay transaction ID and receipt timestamp, and does not mutate its cancelled activation order. In `_process_payment`, call this before normal confirmation when the exact transfer code/amount matches a superseded row, log a warning, and return the normal SePay acknowledgement.

- [ ] **Step 4: Run SePay suite**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_vietqr_payment_system.py -q`

Expected: PASS, including duplicate webhook idempotency and delayed legitimate QR recovery.

- [ ] **Step 5: Commit**

```powershell
git add backend/locket/db.py backend/locket/sepay_webhook.py backend/tests/test_vietqr_payment_system.py
git commit -m "fix(sepay): review late superseded qr receipts"
```

### Task 4: Stop canceling QR on a tab click

**Files:**
- Modify: `frontend/src/pages/dashboard/ActivationWizard.tsx:payment selector and navigation`
- Modify: `frontend/src/tests/ActivationWizardLunaKey.test.tsx`

- [ ] **Step 1: Add a failing interaction test**

```tsx
it('keeps an active QR when merely switching to Coin', async () => {
  renderWizard([lunakeyPlan]);
  await reachPaymentAndSelectQr();
  await userEvent.click(screen.getByRole('button', { name: /ví coin/i }));
  expect(cancelPayment).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: /xác nhận thanh toán ngay/i })).toBeEnabled();
});
```

- [ ] **Step 2: Run and verify RED**

Run: `cd frontend; npm test -- --run src/tests/ActivationWizardLunaKey.test.tsx -t "keeps an active QR"`

Expected: FAIL because the tab handler calls `closeActiveQrOrder()`.

- [ ] **Step 3: Make tab switching non-destructive**

Change the Coin tab handler to only set `paymentMethod` and clear presentation errors. Keep explicit cancellation when changing plan, coupon, account, leaving the payment workflow, or pressing a visible “Hủy mã QR” action. Coin success relies on the backend supersede transaction.

- [ ] **Step 4: Run test and build**

Run: `cd frontend; npm test -- --run src/tests/ActivationWizardLunaKey.test.tsx; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/pages/dashboard/ActivationWizard.tsx frontend/src/tests/ActivationWizardLunaKey.test.tsx
git commit -m "fix(checkout): preserve qr until coin succeeds"
```

### Task 5: Add Admin audit access without polluting the default list

**Files:**
- Modify: `frontend/src/api/adminEndpoints.ts`
- Modify: `frontend/src/pages/admin/AdminPayments.tsx`
- Create: `frontend/src/tests/AdminPayments.test.tsx`
- Modify: `frontend/src/types/admin.ts`

- [ ] **Step 1: Add failing list-filter test**

Mock the default response without superseded rows and the audit response with a `cancel_reason: 'superseded_by_coin'` row. Assert the default request omits `superseded`, selecting “Đã thay thế bởi Coin” sends `superseded=only`, and the audit row label is “Đã chuyển sang Ví Coin”.

- [ ] **Step 2: Run and verify RED**

Run: `cd frontend; npm test -- --run src/tests/AdminPayments.test.tsx`

Expected: FAIL because the filter/type does not exist.

- [ ] **Step 3: Add typed filter and label**

```ts
type SupersededFilter = '' | 'include' | 'only';
```

Extend `fetchAdminPayments` params and add a compact Admin select. The default remains empty/excluded. Never show confirm/reject controls for `superseded_by_coin`; late receipts become `review_needed` and use the existing review flow.

- [ ] **Step 4: Run test and build**

Run: `cd frontend; npm test -- --run src/tests/AdminPayments.test.tsx; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/api/adminEndpoints.ts frontend/src/pages/admin/AdminPayments.tsx frontend/src/tests/AdminPayments.test.tsx frontend/src/types/admin.ts
git commit -m "feat(admin): audit qr replaced by coin"
```

### Task 6: Full payment verification

- [ ] **Step 1: Run backend payment suites**

Run: `cd backend; ../.venv/Scripts/python.exe run_tests_isolated.py tests/test_plans_wallet_payment.py tests/test_vietqr_payment_system.py tests/test_lunakey_qr_integration.py tests/test_lunakey_races.py`

Expected: all modules PASS; wallet deductions, QR settlement, refund, races, and provider dispatch remain exact-once.

- [ ] **Step 2: Run frontend tests and build**

Run: `cd frontend; npm test -- --run; npm run build`

Expected: PASS.

- [ ] **Step 3: Inspect data safety**

Run: `git diff --check; git status --short; git diff --stat`

Expected: no `DELETE FROM payment_orders`, no API key, `.env`, DB, or build output in the diff.

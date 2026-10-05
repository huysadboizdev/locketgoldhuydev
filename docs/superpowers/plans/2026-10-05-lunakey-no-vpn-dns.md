# LunaKey No VPN DNS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map all four LunaKey No VPN durations correctly and require a truthful DNS-profile walkthrough before purchase while preserving the guide after payment.

**Architecture:** Persist provider category and DNS capability on plans, snapshot both onto orders, and fail closed at purchase boundaries. Reuse one frontend `DnsSetupGuide` component in the prerequisite, completion, and order-history views; mobileconfig access remains authenticated and ticketed.

**Tech Stack:** Flask, SQLite, Python unittest/pytest, React 18, TypeScript, Vitest, Testing Library.

---

## File structure

- `backend/locket/providers/lunakey.py`: provider category allowlist and payload normalization.
- `backend/locket/db.py`: additive schema migration, plan/order capability snapshots, ticket eligibility.
- `backend/locket/public/routes.py`: DNS acknowledgment guards and setup-ticket endpoint.
- `backend/migrate_lunakey_plans.py`: dry-run/apply catalog migration for four stable slugs.
- `backend/tests/test_lunakey_provider.py`: provider and purchase-boundary regression tests.
- `backend/tests/test_lunakey_migration.py`: catalog migration regression tests.
- `frontend/src/components/upgrade/DnsSetupGuide.tsx`: reusable iOS DNS instructions and acknowledgment UI.
- `frontend/src/pages/dashboard/ActivationWizard.tsx`: pending-plan DNS prerequisite and post-payment guide.
- `frontend/src/pages/dashboard/OrdersView.tsx`: order-snapshot DNS guide.
- `frontend/src/types/api.ts`, `frontend/src/api/endpoints.ts`: capability and setup-ticket contracts.
- `frontend/src/tests/DnsSetupGuide.test.tsx`, `frontend/src/tests/ActivationWizardLunaKey.test.tsx`, `frontend/src/tests/OrdersViewLunaKey.test.tsx`: UI behavior.

### Task 1: Accept the four provider categories

**Files:**
- Modify: `backend/locket/providers/lunakey.py:43-69`
- Test: `backend/tests/test_lunakey_provider.py`

- [ ] **Step 1: Add failing category and payload tests**

```python
def test_all_no_vpn_categories_resolve_and_reach_payload(self):
    sent = []
    def transport(method, url, **kwargs):
        sent.append(kwargs["json_body"])
        return FakeResponse(200, {"success": True, "order_code": "LK1"})

    client = lunakey.LunaKeyClient(api_key="dummy", base_url="https://locket.lunakey.net", transport=transport)
    for category in ("1month", "3month", "6month", "yearly"):
        client.activate("demo", category, f"req-{category}")
        self.assertEqual(sent[-1]["category"], category)

def test_unknown_category_fails_before_network(self):
    client = lunakey.LunaKeyClient(api_key="dummy", transport=lambda *a, **k: self.fail("network called"))
    with self.assertRaises(lunakey.LunaKeyConfigError):
        client.activate("demo", "month", "req-invalid")
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_lunakey_provider.py -q -k "all_no_vpn_categories or unknown_category"`

Expected: the four-category test fails because only `yearly` resolves; the invalid-category test passes.

- [ ] **Step 3: Expand the explicit allowlist**

```python
KNOWN_CATEGORIES = ("1month", "3month", "6month", "yearly")
CATEGORY_ALIASES = {category: category for category in KNOWN_CATEGORIES}
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the command from Step 2. Expected: all selected tests pass and no real HTTP request occurs.

- [ ] **Step 5: Commit**

```powershell
git add backend/locket/providers/lunakey.py backend/tests/test_lunakey_provider.py
git commit -m "fix(lunakey): map all no-vpn durations"
```

### Task 2: Persist and snapshot DNS capability

**Files:**
- Modify: `backend/locket/db.py:285-420, 880-920, plan serializers/create/update functions`
- Modify: `backend/locket/admin_api.py:plan payload validation`
- Modify: `frontend/src/types/api.ts:PlanItem, ActivationOrder`
- Modify: `frontend/src/types/admin.ts:AdminPlanItem, AdminActivationOrder`
- Test: `backend/tests/test_plans_wallet_payment.py`

- [ ] **Step 1: Add failing schema and snapshot tests**

```python
def test_dns_requirement_is_returned_and_snapshotted(self):
    plan_id = db.create_plan(
        name="No VPN 1 tháng", slug="gold_1_m", duration_days=30,
        price_vnd=5000, activation_provider="lunakey",
        provider_category="1month", requires_dns_profile=True,
    )
    plan = db.get_plan_by_id(plan_id)
    self.assertTrue(plan["requires_dns_profile"])
    order_id = db.create_activation_order(
        user_id=1, plan_id=plan_id, payment_method="coin", platform="ios",
        locket_username="demo", fulfillment_mode="auto_activation",
    )
    order = db.get_activation_order_by_id(order_id)
    self.assertTrue(order["requires_dns_profile_snapshot"])
```

- [ ] **Step 2: Run test and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_plans_wallet_payment.py -q -k dns_requirement`

Expected: FAIL because the columns/arguments do not exist.

- [ ] **Step 3: Add additive columns and normalize booleans**

Add to schema and `_migrate_lunakey_schema`:

```python
"requires_dns_profile": "INTEGER NOT NULL DEFAULT 0"
"requires_dns_profile_snapshot": "INTEGER NOT NULL DEFAULT 0"
```

When creating an order, obtain the value from the server-loaded plan and insert `1 if plan.get("requires_dns_profile") else 0`; never accept the snapshot from client JSON. Plan serializers return `bool(row["requires_dns_profile"])` and order serializers return `bool(row["requires_dns_profile_snapshot"])`.

- [ ] **Step 4: Add TypeScript fields**

```ts
// PlanItem / AdminPlanItem
requires_dns_profile?: boolean;
// ActivationOrder / AdminActivationOrder
requires_dns_profile_snapshot?: boolean;
```

- [ ] **Step 5: Run focused backend tests and TypeScript build**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_plans_wallet_payment.py -q -k dns_requirement`

Run: `cd frontend; npm run build`

Expected: PASS; TypeScript emits no errors.

- [ ] **Step 6: Commit**

```powershell
git add backend/locket/db.py backend/locket/admin_api.py backend/tests/test_plans_wallet_payment.py frontend/src/types/api.ts frontend/src/types/admin.ts
git commit -m "feat(plans): snapshot dns requirement"
```

### Task 3: Replace the destructive yearly migration

**Files:**
- Modify: `backend/migrate_lunakey_plans.py`
- Modify: `backend/tests/test_lunakey_migration.py`

- [ ] **Step 1: Add a failing four-plan migration test**

```python
EXPECTED = {
    "gold_1_m": ("1month", 30, 5000, 1),
    "gold_3_m": ("3month", 90, 8000, 1),
    "gold_6_m": ("6month", 180, 9000, 2),
    "gold_1_y": ("yearly", 365, 10000, 2),
}

def test_apply_maps_four_no_vpn_plans_and_is_idempotent(self):
    self.run_migration("--apply")
    rows = {r["slug"]: r for r in db.get_conn().execute("SELECT * FROM plans")}
    for slug, (category, days, price, warranty) in EXPECTED.items():
        self.assertEqual((rows[slug]["provider_category"], rows[slug]["duration_days"], rows[slug]["price_vnd"], rows[slug]["warranty_months"]), (category, days, price, warranty))
        self.assertEqual(rows[slug]["requires_dns_profile"], 1)
    self.run_migration("--apply")
    self.assertEqual(db.get_conn().execute("SELECT COUNT(*) FROM plans WHERE slug IN ('gold_1_m','gold_3_m','gold_6_m','gold_1_y')").fetchone()[0], 4)
```

- [ ] **Step 2: Run and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_lunakey_migration.py -q -k four_no_vpn`

Expected: FAIL because the current script maps every row to `yearly/365` and does not create the yearly slug.

- [ ] **Step 3: Implement an explicit catalog table and dry-run/apply upsert**

```python
PLAN_SPECS = (
    {"slug": "gold_1_m", "name": "Locket Gold 1 Tháng", "category": "1month", "days": 30, "price_vnd": 5000, "warranty": 1, "sort": 10},
    {"slug": "gold_3_m", "name": "Locket Gold 3 Tháng", "category": "3month", "days": 90, "price_vnd": 8000, "warranty": 1, "sort": 20},
    {"slug": "gold_6_m", "name": "Locket Gold 6 Tháng", "category": "6month", "days": 180, "price_vnd": 9000, "warranty": 2, "sort": 30},
    {"slug": "gold_1_y", "name": "Locket Gold 1 Năm", "category": "yearly", "days": 365, "price_vnd": 10000, "warranty": 2, "sort": 40},
)
```

For existing stable slugs, update catalog columns only. For missing slugs, call the repository's plan creation helper with `activation_provider="lunakey"`, iOS/auto-activation, `requires_dns_profile=True`, active/in-stock, and warranty policy `shop_calendar_months`. Abort on a conflicting provider for the same slug. Do not update `activation_orders`.

- [ ] **Step 4: Run migration tests twice**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_lunakey_migration.py -q`

Expected: PASS including schema-upgrade, historical snapshot, and idempotency cases.

- [ ] **Step 5: Commit**

```powershell
git add backend/migrate_lunakey_plans.py backend/tests/test_lunakey_migration.py
git commit -m "fix(migration): seed four no-vpn plans"
```

### Task 4: Enforce DNS acknowledgment and issue setup tickets

**Files:**
- Modify: `backend/locket/public/routes.py:mobileconfig routes, purchase_plan_coin, create plan payment route`
- Test: `backend/tests/test_lunakey_provider.py`

- [ ] **Step 1: Add failing purchase and setup-ticket tests**

```python
def test_dns_plan_rejects_purchase_without_ack(self):
    response = self.client.post("/api/orders/coin", json={"plan_id": self.dns_plan_id, "platform": "ios", "username": "demo", "lookup_token": self.lookup_token})
    self.assertEqual(response.status_code, 409)
    self.assertEqual(response.get_json()["error"], "dns_acknowledgement_required")

def test_setup_ticket_requires_eligible_dns_plan(self):
    response = self.client.post("/api/mobileconfig/setup-ticket", json={"plan_id": self.dns_plan_id})
    self.assertEqual(response.status_code, 200)
    self.assertTrue(response.get_json()["download_url"].startswith("/api/mobileconfig?ticket="))
```

- [ ] **Step 2: Run and verify RED**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_lunakey_provider.py -q -k "dns_plan_rejects or setup_ticket"`

Expected: missing acknowledgment currently succeeds or reaches later validation; setup route is 404.

- [ ] **Step 3: Add one shared guard**

```python
def _dns_ack_error(plan, body):
    if plan.get("requires_dns_profile") and body.get("dns_acknowledged") is not True:
        return jsonify({"success": False, "error": "dns_acknowledgement_required", "msg": "Vui lòng hoàn tất hướng dẫn cài DNS trước khi thanh toán."}), 409
    return None
```

Call it for new Coin and QR purchases after idempotent replay lookup but before coupon reservation, payment creation, or wallet deduction.

- [ ] **Step 4: Add authenticated setup-ticket route**

The route loads `plan_id` server-side and rejects inactive, non-iOS, non-DNS plans or a missing artifact. It inserts a 60-second, one-use `mobileconfig` ticket using the existing hash format and returns only the raw ticket/download URL. No provider or NextDNS secret is returned.

- [ ] **Step 5: Permit post-payment DNS orders to create tickets while processing**

For an owned iOS activation order with `requires_dns_profile_snapshot`, accept statuses `paid`, `awaiting_queue`, `queued`, `processing`, and `completed`; keep the old completed-only rule for other plans.

- [ ] **Step 6: Run tests and verify GREEN**

Run: `cd backend; ../.venv/Scripts/python.exe -m pytest tests/test_lunakey_provider.py tests/test_plans_wallet_payment.py -q`

Expected: PASS and no external HTTP calls.

- [ ] **Step 7: Commit**

```powershell
git add backend/locket/public/routes.py backend/tests/test_lunakey_provider.py
git commit -m "feat(dns): gate purchases and issue setup tickets"
```

### Task 5: Build the reusable DNS guide

**Files:**
- Create: `frontend/src/components/upgrade/DnsSetupGuide.tsx`
- Create: `frontend/src/tests/DnsSetupGuide.test.tsx`
- Modify: `frontend/src/api/endpoints.ts`
- Modify: `frontend/src/types/api.ts`

- [ ] **Step 1: Add failing component tests**

```tsx
it('requires download and explicit confirmation in prerequisite mode', async () => {
  const onComplete = vi.fn();
  render(<DnsSetupGuide mode="prerequisite" downloadUrl="/profile" onComplete={onComplete} />);
  expect(screen.getByRole('button', { name: /tiếp tục chọn gói/i })).toBeDisabled();
  await userEvent.click(screen.getByRole('link', { name: /tải cấu hình dns/i }));
  await userEvent.click(screen.getByRole('checkbox', { name: /đã hoàn tất/i }));
  expect(screen.getByRole('button', { name: /tiếp tục chọn gói/i })).toBeEnabled();
});

it('states the icloud safety boundary', () => {
  render(<DnsSetupGuide mode="post_payment" downloadUrl="/profile" />);
  expect(screen.getByText(/không yêu cầu Apple ID/i)).toBeInTheDocument();
  expect(screen.queryByText(/tin cậy chứng chỉ/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run and verify RED**

Run: `cd frontend; npm test -- --run src/tests/DnsSetupGuide.test.tsx`

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Add API adapter and component**

```ts
export async function createMobileconfigSetupTicket(planId: number): Promise<DownloadTicketResponse> {
  return apiClient('/api/mobileconfig/setup-ticket', {
    method: 'POST', body: JSON.stringify({ plan_id: planId }),
  });
}
```

The component renders Safari-only guidance, download/QR area, Settings paths, explicit checkbox, and the safety copy from the design. It never asks for Apple credentials and does not render certificate-trust instructions for the current DNS-only payload.

- [ ] **Step 4: Run component tests and build**

Run: `cd frontend; npm test -- --run src/tests/DnsSetupGuide.test.tsx; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/upgrade/DnsSetupGuide.tsx frontend/src/tests/DnsSetupGuide.test.tsx frontend/src/api/endpoints.ts frontend/src/types/api.ts
git commit -m "feat(ui): add dns setup guide"
```

### Task 6: Gate plan selection and retain the guide after payment

**Files:**
- Modify: `frontend/src/pages/dashboard/ActivationWizard.tsx`
- Modify: `frontend/src/tests/ActivationWizardLunaKey.test.tsx`

- [ ] **Step 1: Replace the old no-DNS expectation with failing flow tests**

Test that selecting a DNS plan opens `dns_setup`, remembers the exact plan, blocks continuation before download/checkbox, sends `dns_acknowledged: true` to both Coin and QR adapters, and displays the guide during LunaKey pending/completed states.

- [ ] **Step 2: Run and verify RED**

Run: `cd frontend; npm test -- --run src/tests/ActivationWizardLunaKey.test.tsx`

Expected: old “no DNS/mobileconfig UI” assertion passes before replacement; new prerequisite assertions fail.

- [ ] **Step 3: Add wizard state and transition**

```ts
type WizardStep = 'plan' | 'dns_setup' | 'platform' | 'username' | 'contact' | 'payment' | 'completed';
const [pendingPlan, setPendingPlan] = useState<PlanItem | null>(null);
const [dnsAcknowledged, setDnsAcknowledged] = useState(false);
```

`handleSelectPlan` sends DNS plans to `dns_setup`; completion sets the selected plan, records a versioned `sessionStorage` acknowledgment, then continues to platform/username. Reset invalidates the in-memory state. Add `dns_acknowledged: dnsAcknowledged` to Coin/QR request bodies.

- [ ] **Step 4: Replace the LunaKey no-DNS completion card**

Keep provider status and warranty text, then render `DnsSetupGuide mode="post_payment"` for `selectedPlan.requires_dns_profile`. Ticket errors are recoverable and never change payment/provider status.

- [ ] **Step 5: Run tests and build**

Run: `cd frontend; npm test -- --run src/tests/ActivationWizardLunaKey.test.tsx src/tests/DnsSetupGuide.test.tsx; npm run build`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/pages/dashboard/ActivationWizard.tsx frontend/src/tests/ActivationWizardLunaKey.test.tsx
git commit -m "feat(wizard): require dns before no-vpn purchase"
```

### Task 7: Show DNS in order history

**Files:**
- Modify: `frontend/src/pages/dashboard/OrdersView.tsx`
- Modify: `frontend/src/tests/OrdersViewLunaKey.test.tsx`

- [ ] **Step 1: Add failing snapshot-driven tests**

For a LunaKey order with `requires_dns_profile_snapshot: true`, assert the detail modal contains the DNS guide and safety copy and never contains “Không cần DNS”. For a LunaKey order with the snapshot false, assert no DNS guide.

- [ ] **Step 2: Run and verify RED**

Run: `cd frontend; npm test -- --run src/tests/OrdersViewLunaKey.test.tsx`

Expected: FAIL because provider identity currently forces “Không cần DNS”.

- [ ] **Step 3: Render by capability snapshot**

Keep the provider-status card independent. Render `DnsSetupGuide mode="post_payment"` whenever `selectedOrder.requires_dns_profile_snapshot` is true, using `createMobileconfigDownloadTicket({ activationOrderId: selectedOrder.id })` for a fresh download URL.

- [ ] **Step 4: Run tests and build**

Run: `cd frontend; npm test -- --run src/tests/OrdersViewLunaKey.test.tsx; npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/pages/dashboard/OrdersView.tsx frontend/src/tests/OrdersViewLunaKey.test.tsx
git commit -m "feat(orders): retain dns guide for no-vpn orders"
```

### Task 8: Full verification

- [ ] **Step 1: Run backend LunaKey/payment suites**

Run: `cd backend; ../.venv/Scripts/python.exe run_tests_isolated.py tests/test_lunakey_provider.py tests/test_lunakey_migration.py tests/test_plans_wallet_payment.py`

Expected: all modules PASS; no real LunaKey, Telegram, or SePay call.

- [ ] **Step 2: Run frontend tests and build**

Run: `cd frontend; npm test -- --run; npm run build`

Expected: all tests PASS and production build completes.

- [ ] **Step 3: Dry-run catalog migration**

Run: `cd backend; ../.venv/Scripts/python.exe migrate_lunakey_plans.py`

Expected: prints four intended mappings and “Dry-run only”; database remains unchanged.

- [ ] **Step 4: Review secrets and diff**

Run: `git diff --check; git status --short; git diff --stat`

Expected: no API key, `.env`, database, build output, or mobileconfig secret is staged.


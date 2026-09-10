# Gold Precheck Cache — Optimized Plan

> **For agentic workers:** Use subagent-driven-development or executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Ensure **100% new user upgrade success** + **long-term Gold retention** via cache. Cache reduces API load — does NOT override RevenueCat subscription.

**Architecture:** Backend cache (in-memory, 5min TTL) + Frontend cache (localStorage, 5min TTL). Fail-closed: timeout/error never cached. Cache invalidated on purchase success.

**Tech Stack:** Python Flask, TypeScript/Vite, SQLite, RevenueCat API

---

## ✅ COMPLETED (already implemented)

| Task | Status | Notes |
|------|--------|-------|
| Backend in-memory cache for `_gold_check` | ✅ Done | `routes.py` — `_GOLD_CACHE`, 300s TTL, skip in TEST mode |
| Frontend localStorage cache for `fetchGoldCheck` | ✅ Done | `endpoints.ts` — 300s TTL, skip on error |
| Block gold-check bypass for manual_contact/apk_download | ✅ Done | `routes.py` — removed `username = ""` lines |
| Defense-in-depth check in `BEGIN IMMEDIATE` | ✅ Done | `db.py` — checks `activation_orders` in transaction |
| Tests: block already-gold, allow new user | ✅ Done | `test_31`, `test_32` in test_plans_wallet_payment.py |

---

## ⬜ REMAINING TASKS (optimization for 100% + long-term retention)

### Task 1: Clear cache on successful purchase

**Files:** `src/pages/dashboard/ActivationWizard.tsx:426-449`, `src/components/upgrade/UpgradePortal.tsx:86-131`

- [ ] Add `clearGoldCheckCache(username)` call after `res.success` in both components
- [ ] Verify frontend test: `src/tests/ClearGoldCache.test.tsx`

### Task 2: Add cache-aware regression tests

**Files:** `backend/tests/test_gold_check.py`, `src/tests/GoldCheckCache.test.tsx`

- [ ] Backend: test cache hit returns cached result
- [ ] Backend: test timeout NOT cached (fail-closed)
- [ ] Frontend: test localStorage cache populated
- [ ] Frontend: test cache TTL expiry triggers new API call

### Task 3: Deploy verification

- [ ] Checklist: restart gunicorn, deploy dist/, verify API response, smoke test new user purchase
- [ ] Document in `docs/gold-cache-deploy-checklist.md`
# QR Forge — full audit summary

This is the complete, cumulative project after a multi-phase security and
completeness audit. Every fix described below is already applied in this
copy of the code. **Nothing in this project has actually been run** — the
sandbox this work was done in has no Django installation and no network
access, so every fix is verified by careful reading, standalone
reimplementation of pure logic where possible, and (where noted) mocked or
hand-signed tests. Run the full test suite and a real deploy checklist
before trusting this in production.

## Before you do anything else
```
pip install -r requirements.txt
python manage.py migrate
python manage.py test
```

## Phase-by-phase summary

### 1. qrapp — ownership/IDOR pilot
QR codes and dynamic links had no `user` field at all — anyone could list,
search, or delete any user's data (`clear()` could wipe the entire table).
Added `user` FK to `QRCode`/`DynamicLink`, scoped every endpoint to
`request.user`, added login requirements, fixed CSRF-adjacent findings.

### 2. accounts + teams
Found `teams`/`accounts` views were already well-built (proper membership
checks throughout). Real bugs found were adjacent: the rate-limit
middleware's login/register/2FA entries were unreachable dead code due to
a path-prefix bug (zero effective brute-force protection); a staff
(non-superuser) dashboard account could grant itself/others `is_staff` and
modify/delete superuser accounts (privilege escalation) — both fixed.

### 3. billing
Headline bug: `upgrade_plan` let any user grant themselves Pro for free —
no payment check at all. Fixed so only free-tier switches apply directly;
paid plans require real Stripe Checkout, and only a signature-verified
webhook ever grants a paid plan. Added `Plan.allows_team`/`allows_api`
enforcement, moved plan seeding to a proper migration instead of
re-defining it inline on every request.

### 4. QR monthly quota (hard block)
`check_qr_limit` existed but was never called. Wired into both `generate`
and `bulk_generate`, atomically (row-locked) to prevent two concurrent
requests from jointly exceeding the limit, with bulk checked against the
whole batch before creating anything (reject all-or-nothing, not
partial).

### 5. api app
Highest-priority finding: SSRF via `WebhookEndpoint.target_url` — server
made real HTTP requests to a fully user-controlled URL with zero
validation. Fixed with resolve→validate→pin-the-connection (closes DNS
rebinding) plus switching to `http.client` (never auto-follows redirects,
closing redirect-based SSRF). Also: API keys were stored in plaintext
*and* the full value was embedded in the page's HTML on every reload (not
just the visible truncated text) — fixed with proper hashing, one-time
reveal at creation only. `Plan.allows_api` enforcement added. `APIKey.team`
confirmed as intentionally-unused dead schema, documented not built out.

### 6. Follow-ups (per your direction, one at a time)
- `api_generate` wired to the same quota check as the session endpoint.
- `teams/team_detail.html` built into a real page (was an 8-line stub;
  now full member/invite/role/audit-log UI reusing the existing API).
- `admin_panel` — confirmed completely empty (no code, not wired in
  anywhere) and removed.
- Real Stripe Checkout implemented (`stripe` SDK, real Checkout Session
  creation, webhook signature verification via the official SDK).

### 7. Project-wide consistency sweep
Found `qrapp/tests.py` had been silently broken since phase 1 (every view
test used an anonymous client against endpoints that have required login
since that phase) — rewritten with proper auth and new IDOR tests. Found
`dashboard/tests.py` had zero coverage despite a real security fix in
phase 2 — added tests for it. Confirmed migrations are consistent across
every app and the `admin_panel` removal left nothing dangling.

### 8. Site-wide page audit
Read every template in the project. Found the contact form faked success
client-side without ever submitting anything — built a real backend
(model, migration, validated endpoint, admin visibility, proper
loading/error states). Found and fixed ~19 `fetch()` call sites across 6
pages with zero error handling (a real network failure would throw an
uncaught exception with no user feedback). Found and fixed a genuinely
broken "Try it" API demo button that sent no `Authorization` header and
tried to scrape a raw API key out of the DOM via a method that stopped
working once keys were hashed. Disabled (not silently left broken) two
"Continue with Google" buttons that went nowhere — real OAuth needs
credentials that don't exist in this environment; flagged for a decision
rather than either faking it or silently deleting a possibly-intentional
UI element.

## Explicitly deferred — needs your decision, not mine
- **Real Google OAuth** — buttons are honestly disabled with a "coming
  soon" label rather than a dead link. Needs a registered Google Cloud
  OAuth app (client ID/secret) from you to build for real.
- **`api_generate`'s interaction with future non-unlimited API-enabled
  plans** — already fixed (see phase 6), just noting it was a real gap.
- The rate-limit middleware's in-memory, non-test-isolated hit counter
  (found during the consistency sweep) — dormant, not currently causing
  failures, flagged rather than fixed since addressing it properly is a
  design decision.

## What's NOT in this zip
`.git`, `__pycache__`, and `staticfiles/` (regenerate with
`collectstatic`) were stripped for a clean deliverable. An orphaned
`0001_initial.py` referencing a `QRHistory` model that doesn't exist
anywhere in the current codebase was found sitting at the project root
(not inside any app, not wired in) and excluded as clutter from an earlier
project iteration.

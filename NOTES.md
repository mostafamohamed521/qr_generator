# billing audit — what changed and what to test

## Files changed
- `billing/models.py` — added `StripeEvent` (webhook idempotency).
- `billing/views.py` — rewritten (see report in chat for the full rationale).
- `billing/admin.py` — registered `StripeEvent`.
- `billing/migrations/0002_stripeevent_seed_plans.py` — new: schema for
  `StripeEvent` + a proper data migration seeding Free/Pro plans
  (`get_or_create`, won't touch existing rows).
- `qr_site/settings.py` — added `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET`
  (env-sourced, empty by default).
- `teams/views.py` — `create_team` now requires `allows_team` on the caller's
  plan.
- `api/views.py` — `create_key` now requires `allows_api` on the caller's
  plan.
- `templates/billing/billing.html` — checked, **no change needed**: it
  already only shows success/reloads on `data.ok === true` and otherwise
  surfaces `data.error` — so it was already safe against the backend now
  returning `ok:false` for a paid-plan request. I made and then reverted an
  edit here once I confirmed that.

## You must do this before deploying
- **Run migrations**: `python manage.py migrate`. Not run in my sandbox — no
  Django, no network.
- **This cannot be tested against real Stripe from here.** The webhook
  signature verification, idempotency, and event handling are implemented
  correctly per Stripe's documented scheme, but I have no way to generate a
  real signed test event in this sandbox. Use the Stripe CLI
  (`stripe trigger checkout.session.completed`, `stripe listen --forward-to
  ...`) against a real `STRIPE_WEBHOOK_SECRET` to verify end-to-end.
- Test that `create_team` and `create_key` return 403 for a Free-plan user
  and succeed for Pro.
- Confirm `upgrade_plan` with `{"plan":"pro"}` now returns `402` with
  `checkout_required: true` instead of silently granting Pro (this was the
  original bug — re-verify it's actually closed).
- Confirm `upgrade_plan` with `{"plan":"free"}` still works (self-downgrade,
  no payment needed).
- Confirm `cancel_plan` still works.

## Explicitly NOT done, per your instructions
- `check_qr_limit` — not wired into `generate`/`bulk_generate`. See the report
  in chat for what it does and the question I need you to answer before I
  touch it.
- `teams/team_detail.html` — untouched.
- `api` app — not otherwise audited (only the two entitlement checks above,
  which you explicitly asked for in this phase).

## Real Stripe checkout is still not implemented
By design, per your instruction not to fake payment behavior. `upgrade_plan`
now correctly refuses to grant a paid plan and explains why, with a clear
comment marking exactly where a real `stripe.checkout.Session.create(...)`
call belongs once `STRIPE_SECRET_KEY` is set. That implementation itself
(actually creating and redirecting to a Checkout Session, and installing the
`stripe` package) is separate, larger work — let me know if you want that
built out next, once this phase is approved.

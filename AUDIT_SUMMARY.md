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

## Session — full re-audit (backend), fresh pass
A second, independent full pass over every app, not assuming the earlier
phases above were the last word. Real findings, this session only:

- **`qr_site`**: rate-limit IP resolution trusted `X-Forwarded-For`
  unconditionally — trivially spoofable, defeated brute-force protection
  entirely unless genuinely behind a stripping reverse proxy. Now gated by
  `DJANGO_TRUST_PROXY_HEADERS`. `SECRET_KEY`/`ALLOWED_HOSTS` now fail loudly
  in production instead of silently running insecure. Added upload size
  caps, `CSRF_TRUSTED_ORIGINS` support, extra security headers. The public
  REST API (`/api/v1/...`) had **no rate limiting at all** — fixed.
- **`qrapp`**: no `max_length` on any form field → a long paste threw an
  unhandled `DataOverflowError` (500). WiFi/vCard builders didn't escape
  `; , : \` — special characters in an SSID/name silently corrupted the
  scanned result. Export filename wasn't sanitized. `DynamicLink`/
  `ScanEvent` were missing from admin entirely.
- **`accounts`**: password reset didn't run `validate_password` (registration
  did) — inconsistent strength rules. Long email could crash registration
  (used as `username`, capped at 150). **`Profile.two_factor_secret` was
  fully visible in default admin** — any staff account could read it and
  generate valid 2FA codes for any user, defeating 2FA. "Resend
  verification" was an unprotected `GET` link (CSRF-able email-flood
  vector).
- **`dashboard`**: QR count was hardcoded to `0` everywhere (list, CSV
  export, "top users" — which was actually just recent signups, not
  activity). Admin deleting a user who owned a team with other members
  would cascade-delete that whole team with no warning (same class of bug
  already guarded against in self-service delete, just missing here).
- **`teams`**: admin exposed the raw invite token (bearer credential for
  joining a team) in the default list view.
- **`billing`**: `cancel_plan` only updated the local DB — the real Stripe
  subscription was never cancelled, so a customer kept being billed after
  the app told them they'd cancelled. Now calls `stripe.Subscription.cancel`.
- **`api`**: `?api_key=` query-string auth (undocumented, log/history/
  referrer-leak risk) removed — header-only now, matching the docs.
  `api_generate` could throw the same unhandled overflow as qrapp; dynamic
  link `target_url` wasn't validated on API update.
- **`core`**: `contact/submit/` had no rate limiting (open spam/SMTP-abuse
  vector). `robots.txt` hardcoded `yoursite.com` instead of the real host.
- **Stray `admin_panel/` app**: empty, unreferenced anywhere, removed.
- **XSS — the significant one**: the shared `esc()` JS helper HTML-escapes
  `< > & "` but not `'`, and several pages built `onclick="fn('...')"` by
  interpolating **user-controlled** text into that single-quoted JS string
  (team name, a user's own email, API key name, dynamic-link label/URL,
  bulk-QR label, history label/content). A value containing `'` broke out
  and ran arbitrary JS. Two instances were genuinely serious rather than
  self-XSS: **`dashboard/users.html` and `dashboard/dashboard.html`
  rendered a user's own email/username this way in the admin's own
  dashboard** — a crafted email at signup (RFC 5321 permits `'` in a
  local-part, so it isn't even a malformed address) would run script in an
  admin's session: full privilege escalation, not a cosmetic bug. Also
  found three plain unescaped `innerHTML` insertions (no quote-breakout
  needed at all) in `analytics.html`, `dynamic.html` (stats modal), and
  `api/docs.html` (new-key card). Fixed every instance — user-controlled
  values are now always passed through `esc()`, and every place that used
  to build an `onclick="..."` string from dynamic data now uses
  `data-*` attributes plus a delegated `addEventListener`, which removes
  the double-escaping trap structurally rather than patching each string.

Not yet done this session, flagged for the next pass: templates/CSS visual
redesign (colors/branding), new feature proposals, and a full dashboard
UI pass — deliberately left for last so they build on a settled backend.

## Session — visual redesign + new features
Backend/security work above was done first and settled before touching
anything visual, so this builds on it rather than needing to be redone.

**Redesign.** The previous theme (purple/teal/orange trio, an infinitely-
animating canvas of blurred floating orbs, heavy glassmorphism blur,
rainbow gradient text on every heading/button, "Space Grotesk" geometric
sans) read as generic AI-generated-SaaS. Replaced with a two-color classic
identity: deep navy ink (`#1b3358`) as primary, muted brass/gold
(`#a9782e`) as a sparing secondary accent, plus one neutral slate for
tertiary UI, on a warm ivory background (dark mode: charcoal-navy bg,
gold becomes primary). Concretely:
- Every `linear-gradient` used for decoration (buttons, logo, headings,
  the auth split-panel, avatars, progress bars, the landing-page hero
  title) was flattened to a solid color — gradient-everything is itself
  one of the strongest "AI-generated" tells, not just the specific hues.
- The animated background canvas (a `requestAnimationFrame` loop running
  forever on every page, purely decorative) was removed and replaced with
  a static CSS-only vignette — calmer, and zero ongoing CPU/battery cost.
- Heading font changed from Space Grotesk to Fraunces (serif) across
  every template (~60 occurrences) for an editorial/classic feel; body
  text stays on Inter, Arabic stays on Cairo. Normalized stray
  `font-weight:800/900` down to 700 to match the weights actually loaded
  and avoid synthetic-bold rendering.
- Chart/categorical colors (analytics + admin dashboard breakdowns) and
  the password-strength meter were re-toned from neon (purple/cyan/lime)
  to the same muted palette family instead of just leaving them as leftover
  bright hex codes.
- Every hardcoded literal color (hex and `rgba(r,g,b,...)` — CSS variables
  don't cover inline `style="..."` attributes, which this codebase uses
  heavily) was swept and remapped project-wide, not just the central
  stylesheet's `:root` block.

**New features.**
- **Favorite/star a QR code** — toggle from the history list, plus a
  "favorites only" filter. `QRCode.is_favorite` (migration `0006`),
  `POST /app/api/favorite/<id>/`, exposed on the REST API too.
- **Duplicate a QR code** — one click clones an existing code's content/
  style into a new independent record. `POST /app/api/duplicate/<id>/`,
  correctly goes through the same monthly-quota check as a fresh generate
  (a duplicate still counts against the limit — it's a real new QR, not a
  reference to the old one).
- Both are covered by tests (ownership checks — can't favorite/duplicate
  someone else's QR; quota enforcement on duplicate; filter correctness).

Ideas considered but not built this session (would need more product
direction before implementing): QR expiration dates for dynamic links,
bulk "download all as ZIP", per-team shared QR libraries.

## Session — page-by-page content review
Went through every one of the 30 templates individually, matching each to
its view/URL first (all 30 map 1:1 to a real route via `render()` — none
orphaned, none missing). No page needed removing structurally; the real
problems were content honesty, not page count:

- **`core/landing.html`**: a "50K+ QR codes generated / 99.9% uptime"
  stats strip and three testimonials with fabricated names, quotes, and
  job titles ("Mariam K. — Marketing Lead", etc.) presented as real
  customers. This isn't a style nitpick — it's fake social proof on a
  product with (as of this session) zero real users, which is a genuine
  liability once live, not just unpolished copy. Removed rather than
  reworded; there's no honest version of an invented quote. Left a
  comment in the template explaining why, for whoever swaps in real ones
  later.
- **`core/about.html`**: same issue — "12K+ Active users", "40+ Countries
  served", hardcoded "Founded: 2024" (which goes stale the moment it
  ships). Replaced with true, verifiable facts about the product itself
  (8 QR types, 2 languages, open REST API) instead of invented usage
  numbers.
- **`core/pricing.html`**: had a leftover internal note — *"Full billing &
  checkout (Stripe) is built in Sprint 10."* — live on the public pricing
  page. Beyond being an obvious dev artifact, it was also just wrong:
  Stripe billing is fully built (see billing section above). Removed.
  Also "Start free trial" on the Pro plan button was misleading — there's
  no trial in the billing code, clicking it goes straight to a real Stripe
  charge. Changed to "Upgrade to Pro".
- **`core/faq.html`** (view, not template): one answer referred to "Pro
  and Team plans" as if two separate paid tiers existed — only Free and
  Pro exist; Pro just includes team features. Fixed the wording.
- **`bulk.html`**: two buttons each had `style="..."` written twice on the
  same element — HTML silently keeps only the first and drops the second,
  so their padding/font-size never actually applied. Merged into one
  attribute.

Everything else — FAQ answers, the contact form, billing's empty-invoices
state — checked out as accurate against what the code actually does.

## Session — stale build artifact + content that felt too thin
Two follow-up issues from feedback that the redesign "didn't show" and the
site "felt empty" after the content-honesty pass above:

- **Root cause of "colors didn't change": a stale `staticfiles/` folder
  (5MB, dated before this project's redesign) was still present in the
  delivered zip**, despite this doc's own earlier claim that it had been
  stripped. `staticfiles/css/style.css` in it still had the old purple
  theme and "Space Grotesk" untouched — if served instead of the real
  `static/` source (e.g. a production-style setup per DEPLOY.md's nginx
  config, which points `/static/` at this exact folder), every color
  change in this document would be invisible. Deleted outright — it's a
  `collectstatic` build artifact (already in `.gitignore`), not something
  that should ship pre-built and stale. Regenerate it with
  `python manage.py collectstatic` right before deploying, not before.
- **Landing/about pages felt sparse after removing the fabricated stats
  and testimonials** — that removal was correct, but nothing substantive
  replaced what was cut, and the pages ended up thinner than they should
  be. Added back real content instead: a "Dynamic QR codes" feature card
  (this existed in the product already, just wasn't listed), a genuine
  "Built with security in mind" section on the landing page (2FA, rate
  limiting, HMAC-signed webhooks — all verified true, not aspirational),
  and a "What we believe" section on the about page. One claim in that
  first draft — "export everything" — turned out to be inaccurate on a
  second check: only QR-code CSV export exists, there's no full
  account-data export. Caught before shipping and narrowed to what's
  actually true (QR export + full account deletion, both real).

## Session — asked directly "is anything still missing", checked properly
Two things a purely code-level review wouldn't surface, since they're
neither Python nor CSS:

- **The PWA/favicon icons (`icon-192.png`, `icon-512.png`) were still the
  old purple logo** — baked raster PNGs, untouched by any CSS change
  because they're images, not styles. Used as the favicon, apple-touch-
  icon, and PWA home-screen icon everywhere in `base.html`/
  `base_public.html`/`manifest.json`, so the browser tab and any
  "installed" icon would keep showing the old brand indefinitely.
  Regenerated both at their original sizes with the new navy palette,
  reproducing the same grid-mark glyph the in-app `<svg>` logo already
  uses (just recolored), so the two stay visually consistent.
- **The Arabic translation catalog (`django.po`/`.mo`) was stale** — every
  new English string added this session (landing page's new security
  section, about page's new section, etc.) had no Arabic entry, so an
  Arabic-language visitor would see those specific lines fall back to
  English mid-page. Also found 4 pre-existing gaps unrelated to this
  session's edits ("Continue with Google", a contact-form error string).
  Added real Arabic text for all of it — not placeholder — and,
  since this environment has no `django-admin compilemessages` available
  (no Django installed), wrote a small standalone script implementing the
  GNU MO binary format directly and used it to recompile `django.mo`.
  Verified both old and newly-added strings resolve correctly by loading
  the compiled catalog with Python's own `gettext` module, and confirmed
  by re-scanning every template that zero `{% trans %}` strings are now
  missing from the catalog.

## Session — language toggle bug, nav clutter, dashboard emoji
- **Switching back to English didn't work.** The language-toggle form sent
  `next={{ request.path }}` — the current URL *including* its `/ar/`
  prefix — for Django's `set_language` view to translate via its
  built-in `translate_url()`. That depends on `resolve()` and `reverse()`
  both succeeding for the exact current path; if that ever fails for any
  reason, `translate_url()` silently returns the input unchanged, so the
  redirect lands back on the same `/ar/...` URL no matter which language
  button was pressed. This project has no Django installed in this
  environment to step through and confirm exactly where that broke, so
  rather than guess at the precise failure point, the fix removes the
  dependency on `translate_url()` entirely: a new context processor
  (`qr_site/context_processors.py`) computes the target URL with a plain
  string strip/prepend of the `/ar/` prefix — trivial and unambiguous
  since only one of the two languages is ever prefixed
  (`prefix_default_language=False`) — and both `base.html` and
  `base_public.html` now submit that instead of the raw path.
- **Nav bar was overcrowded** (11+ items in one row once signed in, worse
  for staff). Moved API and Billing out of the primary nav into a new
  slim `<footer>` at the bottom of every authenticated page (the app
  shell had no footer before at all), alongside FAQ and Contact. The
  per-page "active" highlighting for those two (`{% block nav_api %}`,
  `{% block nav_billing %}`) still works unchanged since the footer links
  reuse the same block names.
- **Dashboard used raw color emoji as icons** (👥📥👤📊🏆⚡🔢) while every
  other page in the app uses the same clean stroke-SVG icon set —
  inconsistent, and emoji render completely differently across
  Windows/Mac/Android so they never actually looked intentional. Replaced
  every one in `dashboard.html`/`users.html` with SVGs matching the
  existing icon style. Also did the same for two full-color emoji on
  account pages (✅ email-verified, 🔐 2FA) that stood out the same way.
  A handful of plain monochrome symbols (✓ ✕ ⚠) elsewhere were left as-is
  — those render as simple glyphs following the surrounding text color,
  not full-color pictures, so they don't have the same inconsistency
  problem.
- Also fixed: the dashboard's "up" trend indicator was colored gold
  (`--accent-2`) instead of green — technically fine, but green/red for
  up/down is such a universal convention that deviating from it reads as
  a mistake rather than a design choice. Changed to the same muted sage
  green already used for this purpose in the analytics charts.

Not done this session, flagged rather than fixed: `scanner.html` still
uses colored emoji for detected-QR-type icons (📶👤📝💬📞✉📍🔗), and
`teams/invite_accepted.html` has one celebratory 🎉. Left alone since
they weren't what was reported broken/ugly this round — happy to convert
those to SVGs too on request.

## Session — mobile nav was completely non-functional site-wide
Asked to fix mobile responsiveness. What was actually found goes well
beyond sizing:

- **`base.html` (every authenticated page — Generator, Analytics, Teams,
  Dashboard, all of it) had no hamburger button and no JS to open the nav
  drawer at all.** The CSS for `.mobile-menu-btn` and the `.nav-links.open`
  slide-in state both existed and were fully styled, but the actual
  `<button>` element was never added to the template, and there was no
  click handler anywhere. Below 760px wide, the only thing visible in the
  header was the logo — every nav link, the profile menu, log out, theme
  toggle, and language switch were all on a drawer with literally no way
  to open it.
- **`base_public.html` (landing, pricing, about, FAQ, contact, login,
  register) had the button and the JS handler, but the button itself was
  nested *inside* `#nav-links` — the very drawer it's supposed to open.**
  Since that drawer is `position:fixed` + translated fully off-screen
  when closed, its own toggle button was off-screen along with it: no way
  to ever click it to open the menu in the first place.
  Net effect either way: **mobile nav didn't work anywhere on the site**,
  not on any one page. Fixed by moving the theme toggle and menu button
  in both templates out of `#nav-links` into a new always-visible
  `.nav-controls` sibling group, and adding the missing button + handler
  to `base.html`.
- Implemented the requested mobile layout on top of that fix: menu icon
  + theme toggle grouped together on the right, logo on the left — done
  with a plain DOM order (logo first) plus `flex-direction: row-reverse`
  scoped to `html[dir="rtl"]` at the mobile breakpoint only, since a
  literal RTL flex row would otherwise put the first DOM element (the
  logo) on the right and reverse the requested layout; LTR needed no
  change since normal document order already puts logo-left/controls-right.
- Two more found in the process: nav link labels in `base.html` were bare
  text (not wrapped in `<span>`), so the existing tablet rule meant to
  hide labels and show icon-only between 760–900px (`.nav-link span {
  display:none }`) silently matched nothing and never took effect —
  wrapped every label to match `base_public.html`'s already-correct
  pattern. And `base_public.html`'s own Google Fonts `<link>` was still
  requesting "Space+Grotesk" (URL-encoded space, so the earlier
  find-and-replace across templates never matched the URL-encoded form)
  — the entire marketing site's headings had silently never actually
  loaded Fraunces despite every CSS rule already saying to use it.
  Fixed to match `base.html`'s font link.
- Also added defensive small-screen wrapping to the history search/filter
  toolbar (search box, type filter, and favorites toggle could crowd on
  very narrow phones with no fallback) — everything else checked
  (dashboard grids, the users table) already had working responsive
  rules in place.

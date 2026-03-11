# Zenvi — Change Log

All notable changes across `zenvi-website` and `zenvi-core`.

---

## 2026-03-11 — Phase 1: Token-Gated Download Page

### zenvi-website
- **`supabase/migrations/20260311000000_waitlist_access_tokens.sql`**
  - Added `access_token UUID` (auto-generated per row) and `status TEXT` (`pending`|`invited`) to `waitlist` table
  - Added `validate_waitlist_token(UUID)` Postgres RPC — callable by anon, never exposes full table
- **`src/pages/Download.tsx`** *(new)*
  - Route: `/download?token=<uuid>`
  - Validates invite token via `validate_waitlist_token` RPC
  - Auto-detects macOS / Windows / Linux from `navigator.userAgent`
  - Primary download card for detected OS + secondary cards for others
  - `RELEASE_ARTIFACTS` constant at top — update GitHub org/repo when CI/CD is ready
  - Framer Motion animations matching Zenvi design system
- **`src/App.tsx`** — added `/download` route
- **`src/integrations/supabase/types.ts`** — added new `waitlist` columns + `validate_waitlist_token` function type

### Action required
```bash
cd zenvi-website && supabase db push   # applies migration
```

---

## 2026-03-11 — Phase 2: Auth System (Cursor-style OAuth polling)

### Architecture
Desktop app opens browser → user signs in on website → website stores JWT in a temporary `desktop_auth_sessions` row → app polls every 2 s → auto-closes dialog on success.

### zenvi-website
- **`supabase/migrations/20260311000001_desktop_auth_sessions.sql`** *(new)*
  - `desktop_auth_sessions` table (state UUID, tokens, 10-min TTL, single-use)
  - `complete_desktop_auth_session(state, access_token, refresh_token)` — authenticated only
  - `poll_desktop_auth_session(state)` — anon callable, marks session used on first read
- **`src/pages/Login.tsx`** *(new)* — `/login?state=<uuid>` (desktop) or `/login?next=<path>` (web redirect)
- **`src/pages/Signup.tsx`** *(new)* — `/signup`, handles email-confirm step
- **`src/pages/AuthSuccess.tsx`** *(new)* — `/auth/success`, shown after desktop auth, 5-s auto-close countdown
- **`src/App.tsx`** — added `/login`, `/signup`, `/auth/success` routes
- **`src/integrations/supabase/types.ts`** — added `complete_desktop_auth_session` + `poll_desktop_auth_session` function types

### zenvi-core
- **`src/classes/auth_manager.py`** *(new)*
  - Singleton `AuthManager.instance()`
  - Session persisted to `~/.openshot_qt/zenvi_auth.json`
  - `start_auth_flow()` → opens browser at `/login?state=<uuid>`
  - `poll_for_session(state, on_success, on_timeout)` → daemon thread, polls Supabase RPC
  - `is_authenticated()`, `get_access_token()`, `clear_session()`
  - `get_subscription_tier()` stub (implemented in Phase 3)
  - **TODO**: replace `SUPABASE_ANON_KEY` placeholder with value from `.env`
- **`src/windows/login_window.py`** *(new)*
  - Minimal dark QDialog, 400×300
  - Opens browser immediately on show, polls in `QThread`
  - Emits `auth_completed(dict)` on success, `auth_cancelled()` on dismiss
  - Auto-closes on successful auth

### Action required
```bash
cd zenvi-website && supabase db push   # applies migration
```

---

## 2026-03-11 — Phase 3: Stripe Subscriptions

### Architecture
Pricing CTA → `/checkout?plan=<tier>` → auth check → Edge Function creates Stripe Checkout Session → Stripe redirects to `/checkout/success` → webhook fires → `subscriptions` table updated → desktop app reads tier via `get_user_subscription()` RPC.

### zenvi-website
- **`supabase/migrations/20260311000002_profiles_subscriptions.sql`** *(new)*
  - `profiles` table (mirrors `auth.users`, adds `stripe_customer_id`)
  - `subscriptions` table (`user_id`, `tier`, `status`, Stripe IDs, `current_period_end`)
  - Auto-creates profile on user sign-up via `handle_new_user` trigger
  - `get_user_subscription()` RPC — authenticated, returns current active tier
- **`supabase/functions/create-checkout-session/index.ts`** *(new)*
  - Edge Function: creates or reuses Stripe customer, creates Checkout Session
  - Env vars needed: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_CREATOR`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_STUDIO`
- **`supabase/functions/stripe-webhook/index.ts`** *(new)*
  - Edge Function: handles `checkout.session.completed`, `customer.subscription.updated/deleted`
  - Writes to `subscriptions` table using service role
  - Env vars needed: `STRIPE_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`
- **`src/pages/Checkout.tsx`** *(new)* — `/checkout?plan=<tier>`, auth-gated, shows plan summary + invokes Edge Function
- **`src/pages/CheckoutSuccess.tsx`** *(new)* — `/checkout/success`, post-payment confirmation
- **`src/components/landing/Pricing.tsx`** — CTA buttons now route to `/checkout?plan=<tier>` instead of opening waitlist modal
- **`src/pages/Index.tsx`** — removed `onOpenWaitlist` prop from `<Pricing />`
- **`src/pages/Login.tsx`** — added `?next=<path>` redirect-after-login support
- **`src/pages/Signup.tsx`** — added `?next=<path>` redirect-after-signup support
- **`src/App.tsx`** — added `/checkout` and `/checkout/success` routes
- **`src/integrations/supabase/types.ts`** — added `profiles`, `subscriptions` table types + `get_user_subscription` function type

### zenvi-core
- **`src/classes/auth_manager.py`** — implemented `get_subscription_tier()` using `get_user_subscription` RPC

### Action required
```bash
# 1. Apply DB migration
cd zenvi-website && supabase db push

# 2. Set Stripe env vars in Supabase dashboard → Settings → Edge Functions
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PRICE_CREATOR=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_STUDIO=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# 3. Deploy Edge Functions
supabase functions deploy create-checkout-session
supabase functions deploy stripe-webhook

# 4. Register webhook in Stripe dashboard → point to:
#    https://fmeawyasfffvyoactenu.supabase.co/functions/v1/stripe-webhook
#    Events: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted
```

---

## Upcoming — Phase 4: API Usage Monitoring

- Per-user API spend tracking (OpenAI, Anthropic, Runware)
- Supabase `api_usage` table with per-call cost records
- Desktop app reports usage after each AI call
- Website dashboard shows spend vs. tier limit
- Tier enforcement: block/throttle when limit hit

---

## 2026-03-11 — Phase 4: API Usage Monitoring

### Architecture
- Desktop app records every AI call to a local JSON buffer (usage_buffer.json) — zero latency on the hot path
- Buffer flushes to Supabase every 5 min, after 20 records, or on app quit
- Cost computed server-side from api_pricing table — client cannot inflate/deflate costs
- tier_limits table drives budget enforcement — update limits without a code deploy
- Dashboard at /dashboard shows real-time spend, per-provider breakdown, 6-month history

### zenvi-website
- supabase/migrations/20260311000003_api_usage.sql (new)
  - api_pricing table seeded with Mar 2026 OpenAI/Anthropic/Google/Runware prices
  - tier_limits table (none=$2, creator=$10, pro=$25, studio=$60)
  - api_usage table with indexed user+month lookups
  - calculate_api_cost() pure stable function
  - batch_record_api_usage(records JSONB) batched insert, SECURITY DEFINER
  - get_monthly_totals(), get_usage_summary(), get_usage_history(), check_usage_allowed()
- src/pages/Dashboard.tsx (new) — /dashboard
  - Auth-gated; redirects to /login?next=/dashboard if unauthenticated
  - Spend card with animated progress bar (green → yellow → red at 70/90%)
  - Per-provider breakdown with proportional bars
  - 6-month history bar chart (CSS-based, no extra library)
  - Upgrade alert at ≥70% and ≥90% of limit
- src/App.tsx — added /dashboard route
- src/integrations/supabase/types.ts — added all Phase 4 function types

### zenvi-core
- src/classes/usage_tracker.py (new)
  - Singleton UsageTracker.instance()
  - record() — thread-safe, non-blocking, buffers locally
  - flush() — batch POST to batch_record_api_usage RPC
  - check_allowed() — calls check_usage_allowed RPC, fails open on network errors
  - Buffer restored from disk on startup (survives crashes)
- src/classes/ai_usage_callback.py (new)
  - ZenviUsageCallback(BaseCallbackHandler) — parses OpenAI + Anthropic token formats
- src/classes/ai_llm_registry.py — get_model() injects ZenviUsageCallback via with_config()

### Action required
  cd zenvi-website && supabase db push


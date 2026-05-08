# SurfAI – AI Surfing Video Coach (v1.1 – Memberships + Stripe)

## Vision
AI-powered surf coach mobile app: surfers upload a clip and get instant
frame-by-frame technique feedback — score, mistakes, corrections, drills.

## Stack
- Expo Router (React Native) + TypeScript
- FastAPI + MongoDB (Motor)
- AI: Gemini 2.5 Pro via `emergentintegrations` (Emergent Universal LLM key)
- Auth: Emergent-managed Google OAuth → Bearer token in AsyncStorage
- Payments: Stripe Checkout via `emergentintegrations.payments.stripe.checkout`

## Membership tiers
| Plan  | Price       | Features                                                                                        |
|-------|-------------|------------------------------------------------------------------------------------------------|
| Free  | $0          | 1 AI video analysis / day, standard depth, history                                             |
| Coach | $120 / month| Unlimited analyses, **deeper** AI breakdown, public coach profile, inbox for student clips, comments |

Daily quota is enforced in `POST /api/analyses` (returns 402 to free users
who exceed limit).

## Screens
- `/` Login
- `/auth-callback`
- `(tabs)/index` Sessions dashboard
- `(tabs)/upload` Pick / record / analyse
- `(tabs)/profile` User card, tier badge, quota, coach actions, logout
- `/analysis/[id]` AI breakdown + Share-with-coach + comments thread
- `/paywall` Compare Free vs Coach, start Stripe Checkout
- `/payment-success` Polls `/api/payments/status/{id}` and confirms upgrade
- `/payment-cancel`
- `/coaches` Browse/search public coaches (also used as "pick a coach to share with")
- `/coach/[id]` Public coach profile
- `/coach-edit` Coach-only: edit bio/specialty/location/public toggle
- `/coach-inbox` Coach-only: clips students shared with them

## Backend API additions (v1.1)
| Method | Path | Notes |
|--------|------|-------|
| GET    | /api/plans | public list of tiers |
| GET    | /api/analyses/quota | tier + remaining/used_today |
| POST   | /api/payments/checkout | { plan_id, origin_url } → { url, session_id } |
| GET    | /api/payments/status/{session_id} | polls Stripe + applies subscription idempotently |
| POST   | /api/webhook/stripe | Stripe webhook |
| GET    | /api/coaches | list of public coaches |
| GET    | /api/coaches/{user_id} | public coach profile |
| PUT    | /api/coach/profile | bio, specialty, location, public (coach-only) |
| GET    | /api/coach/inbox | analyses shared with this coach (coach-only) |
| POST   | /api/analyses/{id}/share | { coach_user_id } |
| GET    | /api/analyses/{id}/comments | thread |
| POST   | /api/analyses/{id}/comments | { text } |

## Stripe flow (mobile-aware)
1. User taps "Upgrade to Coach" on `/paywall`
2. Frontend → `POST /api/payments/checkout` with `origin_url = window.location.origin` (web) or backend URL (native)
3. Backend defines amount **server-side** ($120 USD), creates Stripe session,
   inserts pending row in `payment_transactions`, returns URL
4. Frontend redirects to Stripe (web: `window.location.href`, native: `WebBrowser.openAuthSessionAsync`)
5. Stripe → `/payment-success?session_id=...`
6. Polling endpoint hits `get_checkout_status`, when `paid` it idempotently
   sets `tier=coach`, `subscription_expires_at = now + 30d`
7. Webhook `/api/webhook/stripe` reapplies in case redirect is lost

## Smart Business Enhancement
The Coach plan is structured as a marketplace-style **two-sided product**:
free surfers create demand by sharing clips, paid coaches monetise via the
public directory + inbox + comments. This drives **both** subscription
revenue AND retention (free users return because they're awaiting coach
feedback).

## Backlog (next iterations)
- Push notifications when a coach replies
- Stripe customer portal (cancel / update card)
- Pose-tracking overlay on video timeline
- Side-by-side session compare
- Search/filter coaches by location & specialty

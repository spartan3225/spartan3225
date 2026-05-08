# SurfCoach23 – AI Surfing Video Coach (v1.3)

## Vision
Mobile-first AI surf coach. Surfers upload clips → Gemini 2.5 Pro delivers
world-tour-grade technique analysis, modelled on the methodologies of
Martin Dunn, Andy King, Carlos Burle, Brad Gerlach and the WSL judging
criteria, referencing pros: Ramzi Boukhiam, Italo Ferreira, Gabriel
Medina, Filipe Toledo, Kelly Slater.

## Brand
- App name: **SurfCoach23**
- Brand mark: cyan dot + `SURFCOACH · 23` wordmark
- Login hero: dramatic surfing action photography (Ramzi Boukhiam
  inspired)
- Theme: dark performance-pro (cyan #00E5FF on near-black)

## Tiers (3 plans)
| Plan  | Price       | Daily quota | Notes |
|-------|-------------|-------------|-------|
| Free  | $0          | 1 / day     | Standard depth |
| Plus  | $9.99 / mo  | 3 / day     | More analyses, browse coach directory |
| Coach | $120 / mo   | unlimited   | Pro-tour deeper breakdown, public coach profile, inbox, comments |

Daily quota is enforced in `POST /api/analyses` (HTTP 402 on overage).
Pricing & limits are server-defined — never trusted from frontend.

## Screens
- `/` Login with Ramzi-inspired hero + Continue with Google
- `/auth-callback`
- `(tabs)/index` Sessions dashboard + **Pro Inspirations** carousel
  (Ramzi · Italo · Medina · Toledo · Slater)
- `(tabs)/upload` Pick / record / analyse
- `(tabs)/profile` Tier badge, quota card, coach actions, manage plan
- `/analysis/[id]` AI breakdown + share-with-coach + comments
- `/paywall` Free + Plus + Coach cards, two upgrade buttons
- `/payment-success` `/payment-cancel`
- `/coaches` Public directory with search/specialty/location filters
- `/coach/[id]` Public coach profile
- `/coach-edit` Coach-only profile editor
- `/coach-inbox` Coach-only shared-clips list
- `/manage-plan` Coach-only cancel/resume/extend renewal

## Backend API
| Method | Path | |
|--------|------|---|
| GET    | /api/health | |
| POST   | /api/auth/session | |
| GET    | /api/auth/me | |
| POST   | /api/auth/logout | |
| PUT    | /api/users/push-token | |
| GET    | /api/plans | 3 plans |
| GET    | /api/analyses/quota | tier-aware |
| POST   | /api/analyses | tier-aware enforcement |
| GET    | /api/analyses | |
| GET    | /api/analyses/{id} | |
| GET    | /api/analyses/{id}/video?token=... | |
| POST   | /api/analyses/{id}/share | |
| GET/POST | /api/analyses/{id}/comments | + push notification |
| POST   | /api/payments/checkout | plan_id ∈ {plus, coach} |
| GET    | /api/payments/status/{sid} | applies tier=plan_id |
| POST   | /api/payments/cancel-renewal | |
| POST   | /api/payments/resume-renewal | |
| POST   | /api/webhook/stripe | |
| GET    | /api/coaches?q=&location=&specialty= | filtered directory |
| GET    | /api/coaches/{user_id} | |
| PUT    | /api/coach/profile | |
| GET    | /api/coach/inbox | |

## AI Prompt
Base prompt fuses Martin Dunn / Andy King / Carlos Burle / Brad Gerlach
plus WSL judging criteria. Coach-tier prompt extra requires citing
specific pros (Toledo / Medina / Italo / John John / Slater / Ramzi)
in tips and applying judging-criteria scoring in the summary. Verified
in test runs that Gemini 2.5 Pro outputs include these references.

## Smart business engine
- 3-tier funnel (Free → Plus at $9.99 → Coach at $120) with hard daily
  caps drives upgrades without alienating Free users.
- Coach Plan creates a **two-sided marketplace**: free/Plus surfers
  share clips, paid Coaches monetise via the public directory + inbox +
  comments.
- Push notifications close the feedback loop the moment a coach
  replies, reinforcing perceived Coach-plan value.

## Test sessions
- `demo_token_active` → free user `demo@surfai.test`
- `demo_coach_token` → coach `demo.coach@surfai.test` (public profile)

## Pricing Tiers (updated)
- Free: $0 — 1 video LIFETIME (not per day)
- Beginner: $5/mo — 1 video/day
- Plus: $12/mo — 3 videos/day (was $9.99)
- Intermediate: $20/mo — 6 videos/day
- Advanced: $35/mo — 10 videos/day
- Pro: $60/mo — 15 videos/day
- Coach Elite: $120/mo — unlimited + coach directory

Stripe still in TEST mode. Users still able to upgrade via Stripe Checkout (uses inline `price_data` so no manual Stripe Product/Price IDs are needed).

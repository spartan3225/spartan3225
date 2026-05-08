# SurfAI – AI Surfing Video Coach (v1.2)

## Vision
Mobile-first AI coach: surfers upload clips → Gemini 2.5 Pro analyses
movement, mistakes, corrections, drills. Coaches monetise their expertise.

## Stack
Expo Router · TypeScript · FastAPI · MongoDB · Gemini 2.5 Pro
(emergentintegrations) · Stripe Checkout · Emergent Google OAuth ·
Expo Push Notifications.

## Tiers
- **Free** $0 — 1 AI analysis per day
- **Coach** $120/month — unlimited, deeper AI breakdown, public coach
  profile, inbox of student-shared clips, comments thread

## Features delivered
### v1.0
- Login (Emergent Google), session token in AsyncStorage / localStorage
- Dashboard, upload (gallery + camera), AI analysis with Gemini 2.5 Pro
- Analysis detail with score, mistakes (severity + timestamps), corrections, tips, drills
- Profile + stats

### v1.1 (memberships)
- Free vs Coach plans, daily quota enforcement (HTTP 402)
- Stripe Checkout (server-defined amounts), `payment_transactions`, webhook
- Coach profile editor, public coach directory, coach inbox
- Share-with-coach + comments thread

### v1.2 (this release)
- **Push notifications** — when a comment is added, the other party gets a
  push via Expo (`/api/users/push-token` saves token; comments trigger
  `_send_push_notification`)
- **Manage Subscription screen** — coaches can cancel renewal (keeps
  access until expiry), resume renewal, or extend by another month
  (re-uses Stripe Checkout)
- **Coach directory filters** — `q`, `location`, `specialty` query params
  with case-insensitive regex matching, filter UI on `/coaches` screen

## Backend API (full surface)
| Method | Path | Notes |
|--------|------|-------|
| GET    | /api/health | liveness |
| POST   | /api/auth/session | exchange Emergent session_id |
| GET    | /api/auth/me | current user |
| POST   | /api/auth/logout | revoke session |
| PUT    | /api/users/push-token | save / clear Expo push token |
| GET    | /api/plans | tiers |
| GET    | /api/analyses/quota | tier + remaining/used_today |
| POST   | /api/analyses | upload + analyse (free 1/day → 402) |
| GET    | /api/analyses | list user's analyses |
| GET    | /api/analyses/{id} | full analysis |
| GET    | /api/analyses/{id}/video?token=... | stream original |
| POST   | /api/analyses/{id}/share | share with a coach |
| GET    | /api/analyses/{id}/comments | thread |
| POST   | /api/analyses/{id}/comments | add comment + push |
| POST   | /api/payments/checkout | new Stripe Checkout session |
| GET    | /api/payments/status/{sid} | poll status, idempotently apply |
| POST   | /api/payments/cancel-renewal | flag cancel_at_period_end |
| POST   | /api/payments/resume-renewal | clear flag |
| POST   | /api/webhook/stripe | webhook receiver |
| GET    | /api/coaches?q&location&specialty | filtered directory |
| GET    | /api/coaches/{user_id} | public coach profile |
| PUT    | /api/coach/profile | edit (coach-only) |
| GET    | /api/coach/inbox | shared clips (coach-only) |

## Smart Business Enhancement
**Two-sided marketplace**: free surfers fuel demand by sharing clips,
paid coaches monetise via the directory + inbox + comments. Push
notifications **close the loop** the moment a coach replies — driving
return-visits and reinforcing the perceived value of paying $120/month.

## Test sessions (in mongo `test_database`)
- `demo_token_active` → free user `demo@surfai.test`
- `demo_coach_token` → public coach `demo.coach@surfai.test`

## Backlog
- Stripe webhook → auto-flip tier (currently auto-flip via polling is
  blocked by emergentintegrations StripeObject metadata bug)
- Pose-tracking overlay synced with mistake timestamps
- Side-by-side session compare
- Coach earnings dashboard
- iOS / Android native push delivery testing on physical devices

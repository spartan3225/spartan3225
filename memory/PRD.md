# SurfAI – AI Surfing Video Coach

## Vision
Mobile app that lets surfers upload or record short surf clips and get an
instant, deep AI technique analysis – mistakes, corrections, drills and a
score – powered by Gemini 3 / 2.5 Pro multimodal video understanding.

## Stack
- Expo Router (React Native, file-based routes) + TypeScript
- FastAPI (Python) backend with MongoDB (Motor)
- AI: Gemini 2.5 Pro via `emergentintegrations` LlmChat (Emergent Universal Key)
- Auth: Emergent-managed Google OAuth (Bearer token in AsyncStorage)

## Screens
- `/` – Login (Continue with Google) – dark Performance-Pro theme
- `/auth-callback` – exchanges `session_id` from URL hash → backend → token
- `/(tabs)/index` – Sessions dashboard (stats grid + list of past analyses)
- `/(tabs)/upload` – Pick from gallery / record a new clip → analyse
- `/(tabs)/profile` – User card + Bento performance stats + logout
- `/analysis/[id]` – Full breakdown: video player, score, strengths, mistakes
  (with severity, timestamps, details), corrections, tips, drills

## Backend API
| Method | Path | Purpose |
|--------|------|---------|
| GET    | /api/health | liveness |
| POST   | /api/auth/session | exchange Emergent session_id |
| GET    | /api/auth/me | current user |
| POST   | /api/auth/logout | revoke session |
| GET    | /api/analyses | list analyses for user |
| POST   | /api/analyses | upload + analyse video (multipart `file`) |
| GET    | /api/analyses/{id} | full analysis JSON |
| GET    | /api/analyses/{id}/video?token=... | stream original video |

## AI Prompt Output Schema
```
{ title, score (0-100), overall_rating, summary,
  strengths[], mistakes[{title, detail, severity, timestamp}],
  corrections[], tips[], drills[] }
```

## Storage
- Uploaded videos saved on backend disk under `backend/uploads/videos/{user_id}/{analysis_id}.{ext}`
- All metadata in Mongo (`users`, `user_sessions`, `analyses`)
- All MongoDB queries use `{"_id": 0}` projection

## Smart Business Enhancement
"Surf Score Streak" – the dashboard surfaces *Avg* and *Best* scores so
surfers can track progression session-after-session, building a returning
habit and a natural sharing moment when a personal best is hit.

## Future / Backlog
- Frame-by-frame timeline overlay synced with mistake timestamps
- Pose-tracking visualisation
- Compare two sessions side-by-side
- Push notifications on new personal best
- Pro plan paywall (Stripe) for unlimited analyses

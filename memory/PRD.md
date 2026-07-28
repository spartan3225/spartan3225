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

## LemonSqueezy LIVE Mode Migration (June 2026)
- Store approved by LemonSqueezy. Store currency USD, contact email surfcoach23@gmail.com.
- Old email coach1othman@gmail.com replaced with surfcoach23@gmail.com in index.tsx, terms.tsx, privacy.tsx, refund.tsx.
- Local backend/.env updated to LIVE: API key (live), TEST_MODE=false, variants LEARN=1922965, ADVANCED=1923062, PRO=1923852, webhook secret=surf2026webhook.
- Verified: live API key valid, live checkout creation returns 201 (test_mode=false), /api/plans returns $15/$25/$35 USD.
- PENDING USER ACTIONS: fix LEARN product price $16 -> $15 in LS dashboard; rename ELITE -> PRO (optional); create LIVE webhook (callback = live site + /api/webhook/lemonsqueezy, secret surf2026webhook); update deployed Secrets (API key, TEST MODE=false, 3 variant IDs) and Re-publish.

## Web serving fix (June 2026)
- DISCOVERY: Emergent mobile deployments do NOT serve the Expo web frontend at the .emergent.host domain (only backend). Official support confirmed.
- FIX: backend now serves the Expo web export. `npx expo export --platform web --output-dir /app/backend/static_web`; server.py catch-all GET route (after api_router) serves static files with SPA fallback. /api/* unaffected.
- api.ts: on web BACKEND_URL = window.location.origin (native still uses EXPO_PUBLIC_BACKEND_URL).
- LS_PLANS in routers/lemonsqueezy.py fixed from SAR 50/80/110 to USD 15/25/35 (payment_transactions records).
- IMPORTANT: after any frontend change, RE-EXPORT the web build to /app/backend/static_web before re-publishing, or the deployed website will be stale.
- Tested by testing_agent iteration_8: all pass (backend static serving, live checkout creation, email rebrand).

## Multi-replica upload & video storage fix (June 2026)
- Deployed app runs 2 replicas -> local pod disk is NOT shared. Symptoms: "Upload incomplete 8/9 chunks" (chunks split across pods).
- FIX: chunks stored in MongoDB db.upload_chunks (upsert, TTL 24h index); finalize assembles from Mongo; videos persisted to GridFS bucket 'videos' (filename=analysis_id) in background task; GET /analyses/{id}/video falls back to GridFS streaming when local file missing.
- ffmpeg conversion runs in background task (-threads 1, 600s timeout) — HTTP responses <1s. Gemini fallback model updated to gemini-2.5-flash.
- Verified: testing_agent iteration_11 (11/11 pass incl. GridFS byte-identical streaming fallback, idempotent chunk retry, TTL index).
- NOTE: deployed pod is 0.05 vCPU / 128MB RAM — user advised to upgrade Resources for reliable AI video processing.

## Security audit + hardening (June 2026)
- security_audit_agent: CONDITIONAL PASS. No critical/high issues (payments unforgeable, BOLA checks OK, no secret leakage, no traversal/injection).
- Fixed: SEC-001 quota race (post-insert guard w/ rollback -> 402), SEC-002 upload caps (8MB/chunk 413, <=100 chunks, 300MB total 413 in finalize+legacy), SEC-003 video ?token= now checks session expiry.
- Verified: testing_agent iteration_12 (16/16 pass, incl. 3-way concurrency race test).
- Deferred (P3, optional): CORS allowlist, rate limiting, generic checkout error body, subscription_expired demotion by sub id.

## Store-readiness fixes (June 2026)
- Removed legacy push-notification code entirely (frontend push.ts, expo-notifications/expo-device pkgs, backend exp.host send, /users/push-token endpoint, expo_push_token field). Comments unaffected.
- Added Apple-required account deletion: DELETE /api/auth/account (wipes user, sessions, analyses, comments by author_id or user_id, chunks, GridFS + local videos) + 'Delete account' 2-tap confirm button in profile tab.
- Verified: testing_agent iteration_13 (9/9 backend + frontend E2E delete flow); comment-author deletion bug fixed and pytest re-run green.
- Web export regenerated at /app/backend/static_web (needs user Re-publish).
- Apple Developer Program APPROVED (valid to Jul 27, 2027). Google Play Console signup completed, identity verification pending.
- OPEN QUESTION: some videos still fail AI analysis on prod after resource upgrade - need failing examples from user (suspect very long/large clips).

## Auth expansion + Apple IAP compliance (June 2026)
- Added email/password auth (register/login, argon2 via pwdlib, links to existing Google accounts by email) and Sign in with Apple (POST /api/auth/apple, JWKS RS256, APPLE_AUDIENCES env, apple_sub linking). All issue standard user_sessions tokens.
- Landing page: Continue with Google + Apple button (iOS native only) + Continue with Email form (login/register toggle).
- Apple IAP compliance (guideline 3.1.1): paywall purchase buttons render only on web; native shows "managed on the web" note (Netflix model per 3.1.3(b)). Web checkout unchanged.
- app.json: ios.usesAppleSignIn=true; expo-apple-authentication installed. backend/.env: APPLE_AUDIENCES.
- Verified: testing_agent iteration_14 (9/9 backend + full frontend E2E). QA account: qa.tester@surfcoach23.com / TestPass123!
- User must: Re-publish, then generate a NEW iOS build (both App Store blockers now resolved).

## Privacy policy upgrade for App Store (June 2026)
- privacy.tsx rewritten to be Apple-submission-complete: covers Google/Apple/email sign-in data, argon2 password hashing, no-tracking/no-IDFA statement, all processors (LemonSqueezy MoR, Gemini, Claude, MongoDB Atlas), in-app account deletion clause, GDPR/CCPA rights, retention incl. backups, intl transfers. Last updated: June 2026.
- Web export regenerated; verified rendering via screenshot. Live URL after user re-publish: https://wave-motion-ai.emergent.host/privacy

## Support page for App Store (June 2026)
- New /app/frontend/app/support.tsx: contact email card (mailto), common questions (upload, login, billing/refunds, account deletion), what to include when emailing, legal links. Footer 'Support' link added on landing page.
- Support URL for App Store Connect (after re-publish): https://wave-motion-ai.emergent.host/support
- Verified via screenshot on preview. Web export regenerated.

## iPad 13" App Store screenshots (June 2026)
- Generated 5 screenshots at exactly 2048x2732 (Apple 13" iPad requirement): home/sessions, analysis (with real surf video frame injected as poster), corrections/drills, upload screen, landing hero.
- Stored in /app/frontend/public/store-assets/ (auto-included in every expo web export -> served at /store-assets/ on preview and, after re-publish, on the live domain).
- Demo analysis seeded locally: ana_ipadshot001 for user_demo_12345 (status ready, real 5MB surf mp4 copied to their upload dir) - reusable for future marketing shots.

## Phase 1 Premium Upgrade — "Most advanced AI surf coach" (July 2026)
User requested full premium transformation (Apple/Tesla/WHOOP feel) WITHOUT breaking existing features. Phased plan agreed: P1 UI redesign + advanced AI Review (DONE), P2 skeleton tracking + overlay drawing, P3 deep Progress/Train, P4 pro comparison mode (Yago Dora — user has no licensed footage, build ready, footage later). User confirmed server resources upgraded.
- New 5-tab nav: Home / AI Review / Progress / Train / Profile (upload hidden at (tabs)/upload, all old routes preserved). Glass tab bar (BlurView on iOS) + haptics.
- Backend AI schema extended (backwards compatible optional fields on analyses): `scores` (14 categories: surf_flow, take_off, bottom_turn, top_turn, compression, recovery, rail_control, speed_generation, power, timing, balance, style, body_position, wave_reading — each {key,value,note}), `main_mistake` {title,why,cause,performance_lost,fix,timestamp}, `key_moments` [{timestamp,label,type good|bad|neutral}]. Corrections now exactly top-5. Sanitizers `_sanitize_scores/_sanitize_key_moments` in server.py.
- Multi-language (en/es/pt/fr/ru/ar): `/app/frontend/src/i18n.tsx` (I18nProvider + AsyncStorage), language picker chips in Profile; PUT /api/users/preferences {language} stores `preferred_language` on user; AI prompts append language instruction so Gemini+Claude reply in user's language.
- Redesigned analysis/[id].tsx: custom video controls (play/pause, speed 1x/0.5x/0.25x, frame-step ±1/30s), clickable Key Moments chips seek video, overall ScoreRing, 14 sub-score ring grid, strengths card, Main Mistake card, top-5 numbered corrections; comments/share/polling/failed-banner preserved.
- New shared components: src/components/ScoreRing.tsx (SVG), GlassCard.tsx, Skeleton.tsx; src/haptics.ts; src/trainLibrary.ts (10 drills, 5 categories, i18n'd, mapped to score categories for personalization).
- Progress tab: headline ring + delta pill, SVG trend chart (last 10), skill evolution bars w/ deltas vs previous analysis, AI summary. Train tab: personalized plan (weakest 3 skills → matched drills + AI drills from last analysis), filterable drill grid.
- Seeded demo analysis with full new schema: `ana_demoupgrade01` (user_demo_12345). Old `ana_ipadshot001` kept as backwards-compat fixture.
- Verified: testing_agent iteration_18 (17/17 backend + full frontend E2E incl. language switch, old-schema render, video controls). Web export regenerated to /app/backend/static_web (user must Re-publish for live site).
- NOTE: new analyses must be run to see the new scores/key_moments (old ones show legacy layout).

## Multi-video add-on + Train tutorials + Friend coupon (July 2026)
- FRIEND COUPON: created live via LS API — code **SURFFRIEND100** (100% off, forever, max 1 redemption). Share with friend at checkout.
- TRAIN VIDEO TUTORIALS: 6 curated YouTube embeds (TUTORIALS in src/trainLibrary.ts), horizontal cards in Train tab, modal player via src/components/YouTubeEmbed.tsx (iframe on web, react-native-webview on native).
- MULTI-VIDEO PAID ADD-ON (one-time payment per multi-analysis, user's choice):
  - Backend: users.multi_credits; LS one-time product plan_id "multi" → env LEMONSQUEEZY_VARIANT_MULTI (EMPTY — WAITING FOR USER to create the product in LemonSqueezy dashboard and give variant ID + price; checkout returns 400 until then). Webhook order_created grants +1 credit idempotently (db.applied_orders by LS order id).
  - POST /api/analyses/finalize-multi: 2-3 chunk-uploaded clips → atomic credit consume (402 if none, refund on assembly/AI failure), ONE combined analysis (video_count, video_paths, is_multi), does NOT touch daily quota. Combined Gemini prompt (extra_files param on analyse_video_with_gemini; timestamps refer to clip 1). GridFS per clip as {analysis_id}_{i}. Video endpoint supports ?index=0|1|2 (clamped). Pose runs on clip 1 only. Shared _apply_ai_result() used by single+multi runners.
  - Frontend: upload.tsx Single/Multi toggle, credits pill, add/remove up to 3 clips, buy button (web/Android; iOS shows 'purchase on website' note — Apple Netflix model), api.uploadChunksForFile + finalizeMultiUpload. Analysis page clip selector chips (skeleton overlay only on clip 0).
  - E2E validated with REAL AI run: ana_cf496d925cac4b (2 clips, ready, score 63, 14 scores). testing_agent iteration_20: 15/15 backend + full frontend green. Orphan chunks on 402 auto-expire via existing 24h TTL index (non-issue).
- Google Play: still BLOCKED on Google identity verification (user confirmed still waiting).
- PENDING FROM USER: LemonSqueezy multi product variant ID (+ chosen price) → put in backend/.env LEMONSQUEEZY_VARIANT_MULTI and restart.

## Phases 2-4 + iPhone 6.9" screenshots (July 2026)
- iPhone 6.9" App Store screenshots: 5 shots at exactly 1320x2868 in /app/frontend/public/store-assets/ (iphone69-01..05 + iphone69-screenshots.zip). Also copied to /app/backend/static_web/store-assets/ — downloadable at /store-assets/iphone69-screenshots.zip.
- PHASE 2 Skeleton tracking: /app/backend/pose_tracker.py — MediaPipe EfficientDet-Lite0 person detection (model at /app/backend/models_ai/efficientdet_lite0.tflite, needed because surfers are tiny in wide footage) + MediaPipe Pose on expanded crop, 8fps sampling, temporal bbox tracking, 300s timeout, runs via asyncio.to_thread AFTER AI result saved in _run_analysis_in_background. Stores in db.pose_data collection (separate from analyses; ~45KB/clip) + pose_status field. Endpoint GET /api/analyses/{id}/pose. mediapipe==0.10.18 installed (protobuf pinned 4.25.9 — emergentintegrations verified still working). NOTE: local ffmpeg binary missing in dev pod; use imageio_ffmpeg bundled exe for CLI work; cv2.VideoCapture works fine for pose.
- Frontend Phase 2: PoseOverlay.tsx (SVG bones/joints/CG/motion-trail/velocity-arrow/knee+back angle labels), skeleton toggle on analysis video (snaps playhead into tracked range when enabled, contentFit switches to 'contain' for coordinate accuracy), MetricChart.tsx heat-colored Speed/Compression graphs from pose metrics.
- PHASE 3: Progress tab adds RadarChart (skill radar, 6 axes) + streaks row (current/longest/best wave). Review tab adds score-band filters (all/80+/50-79/<50) + Recent↔Best sort toggle.
- PHASE 4: /compare/[id] Pro Comparison screen — pro selector (Yago Dora active; Medina/JJF/Italo 'coming soon'), split-screen You-vs-Pro (pro footage placeholder — USER HAS NO LICENSED FOOTAGE, benchmarks in src/proBenchmarks.ts are static reference data by design, modular for adding footage/pose later), You-vs-Pro radar + per-category bars + ghost overlay placeholder. Entry: 'Compare vs Pro' button on analysis page.
- Demo pose data seeded for ana_demoupgrade01 + ana_ipadshot001 (frames 1.2s-13.5s).
- Verified: testing_agent iteration_19 (13/13 backend + 31/31 frontend, zero regressions). Web export regenerated. User must Re-publish.
- Remaining backlog: Train video tutorials (needs video content), AI drawing on mistakes beyond angle overlays, wave/board analysis, multi-video upload premium add-on, friend coupon, Google Play publishing (blocked on Google identity verification).

## Stuck-analysis + logout fixes (June 2026)
- Analysis page now polls every 5s while processing; auto-updates to ready/failed; failed banner with 'quota not used' + UPLOAD AGAIN button; score pill only when ready.
- Backend: lazy stale watchdog on GET /analyses/{id} (processing >20min -> failed on read, replica-safe); AI pipeline hard timeout 900s.
- Logout fixed: '/' route ambiguity (app/index vs (tabs)/index) - goToLanding() uses window.location.href on web, dismissAll+replace native; also used for delete-account. logout() clears token first.
- Verified: iteration_16 (7/7 backend + polling/failed E2E) and iteration_17 (logout E2E). Optional future cleanup: move landing to explicit route.
- Apple login on website: intentionally absent (iOS native only); web has Google + email.

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
  - Backend: users.multi_credits; LS one-time product plan_id "multi" → env LEMONSQUEEZY_VARIANT_MULTI=1975057 (LIVE product "Multi-Video Analysis (3 clips)", $9.99, product id 1263238, test_mode=False — WIRED & VERIFIED June 2026; checkout returns live URL). Webhook order_created grants +1 credit idempotently (db.applied_orders by LS order id). Fixed KeyError: checkout txn insert now falls back to LS_ADDONS for non-subscription plans.
  - POST /api/analyses/finalize-multi: 2-3 chunk-uploaded clips → atomic credit consume (402 if none, refund on assembly/AI failure), ONE combined analysis (video_count, video_paths, is_multi), does NOT touch daily quota. Combined Gemini prompt (extra_files param on analyse_video_with_gemini; timestamps refer to clip 1). GridFS per clip as {analysis_id}_{i}. Video endpoint supports ?index=0|1|2 (clamped). Pose runs on clip 1 only. Shared _apply_ai_result() used by single+multi runners.
  - Frontend: upload.tsx Single/Multi toggle, credits pill, add/remove up to 3 clips, buy button (web/Android; iOS shows 'purchase on website' note — Apple Netflix model), api.uploadChunksForFile + finalizeMultiUpload. Analysis page clip selector chips (skeleton overlay only on clip 0).
  - E2E validated with REAL AI run: ana_cf496d925cac4b (2 clips, ready, score 63, 14 scores). testing_agent iteration_20: 15/15 backend + full frontend green. Orphan chunks on 402 auto-expire via existing 24h TTL index (non-issue).
- Google Play: still BLOCKED on Google identity verification (user confirmed still waiting).
- DONE: LemonSqueezy multi product wired (variant 1975057, $9.99 LIVE). Checkout endpoint verified returning live hosted checkout URL.
- DONE (June 2026): Friend account pre-seeded — abdelazizmaoulaainine1@gmail.com created as PRO, active, expires ~2026-10-31 (90 days). Auth merges by email, so tier applies on first Google login. NOTE: seeded in this environment's DB; if production uses a separate DB, re-run the seed there.

## iOS readiness fixes (Aug 2026)
- Ran expo-appstore-readiness-review skill. Fixed the blocker + warnings:
  - ios_purchase_note (all 6 langs) neutralized: "Multi-video analysis is not available in this version." (was steering to website — Apple 3.1.1)
  - paywall.tsx native note neutralized (removed "on the web" wording)
  - Startup task in server.py upgrades qa.tester@surfcoach23.com from free→pro (idempotent) so Apple reviewer never hits quota wall — applies to PROD on next deploy
- Remaining warnings (accepted/manual): SIWA token revocation on account deletion not implemented; "Coming soon" labels in Compare screen; App Store Connect privacy labels/review notes are manual
- Gave user URLs for App Store Connect: Marketing https://surfcoach23.com, Privacy https://wave-motion-ai.emergent.host/privacy (custom-domain forwarding drops paths — don't use surfcoach23.com/privacy), Support /support
- Web export regenerated → static_web. User must Publish + new builds.

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

## KAI rebrand + reliability overhaul (June 2026 — session 2)
- HOME REDESIGN (app/(tabs)/index.tsx full rewrite): premium "KAI" design matching user screenshots — KAI logo + "THE AI SURF COACH" tagline, bell icon, AI-generated Kai coach hero image (frontend/assets/kai-coach.png, made via Gemini nano banana), greeting "Hey {name} 🤙" + "Ready for the next wave?", Kai message card (dynamic: start/improving/steady) + KAI SCORE ring (avg of ready scores /100), stats row (Sessions / Kai Score /10 / Improvement=latest-oldest), ANALYZE SESSION gradient CTA -> upload, recent sessions HORIZONTAL scroll (play thumb + score pill + spot title + date), TECHNIQUE bars (take_off/bottom_turn/top_turn/rail_control/timing from latest full analysis.scores) -> Details=/progress, ACHIEVEMENTS badges (First Wave/Consistency/Pop-up Master(take_off>80)/Pro Level(best>85)) -> /progress, rotating motivational quote.
- REBRAND: tab "AI Review" -> "Kai Review" (en). New i18n keys home_tagline/home_ready/kai_score/analyze_session(_sub)/technique/details/achievements/unknown_spot/kai_msg_*/ach_*/quote_* in all 6 langs.
- RELIABILITY (CRITICAL fixes, server.py):
  - PERSISTENCE-FIRST: _store_video_in_gridfs() now called SYNCHRONOUSLY in _finalize_and_start_analysis AND finalize_multi_upload BEFORE the background AI task. Video permanently in GridFS the instant upload completes -> can NEVER disappear (verified: streams 200 even after deleting local file / simulated pod restart). _store_video_in_gridfs hardened: retry-once + verify + returns bool.
  - Gemini retry-with-backoff (3 attempts, 2/3/5s) inside per-model loop for transient 429/5xx/timeout/overloaded -> fixes "works on 2nd/3rd try".
  - ffmpeg resolver: _resolve_ffmpeg() prefers system ffmpeg, falls back to bundled imageio-ffmpeg binary (system ffmpeg absent in env) -> iPhone .MOV/HEVC conversion never silently breaks. imageio-ffmpeg==0.6.0 in requirements.
  - POSE now runs in a dedicated single-worker ProcessPoolExecutor (_get_pose_pool/_pose_worker/_reset_pose_pool), NOT a thread. MediaPipe/OpenCV hold the GIL; running in-process stalled the event loop and made concurrent video streaming slow/502 (flagged iter21). Process isolation keeps API responsive. Retry-once rebuilds pool on worker crash. Pose failure -> pose_status=failed, never blocks status=ready.
  - Frontend api.ts: single-shot POST /analyses now uses postFormWithRetry; finalizeChunkedUpload retries 3x on 5xx/429.
- PRO REFERENCE LIBRARY (legal): src/proBenchmarks.ts relabeled from named pros (Yago Dora/Medina/JJF/Italo) to GENERIC archetypes (Power Surfing/Progressive-Air/Flow & Style/Technical Precision) — NO named-athlete name/likeness (avoids publicity-rights issue). Compare screen uses t(pro.name) via i18n keys pro_ref_*. footage=null until user supplies a commercially-licensed elite-surfer clip (drop into `footage` + set available:true). Main agent CANNOT purchase licenses on user's behalf.
- Verified: testing_agent iteration_21 (6/6 backend incl. persistence-first immediate stream, chunked+single upload->ready, LS multi checkout; frontend KAI home + tabs + compare generic names). Pose process-pool fix added AFTER iter21 (its only flagged issue) and verified pose runs isolated + analysis still reaches ready.
- NOTE: streaming during the ~2min active AI phase can still be briefly slow on the single dev worker; instant once ready (the replay requirement). Acceptable — user sees processing banner, not replaying yet.
- PENDING: user to redeploy for changes to reach production; static_web re-export regenerated.

## Pro Reference clips — REAL footage + skeleton (June 2026, session 2 cont.)
- Sourced 4 REAL surf clips from Pexels (Free-to-use / commercial license, no named-athlete likeness). Downloaded via https://www.pexels.com/download/video/{id}/, transcoded to 720p ~15s H.264 (bundled imageio-ffmpeg), stored in /app/backend/static_assets/pro/small_{id}.mp4. Clip ids: 8775726, 4927323, 4929633, 14435086. Verified MediaPipe detects the surfer (69-120 pose frames each) -> precomputed pose JSON stored as pose_{id}.json.
- Backend: PRO_CLIP_IDS + endpoints GET /api/pro/{clipId}/video (FileResponse) and GET /api/pro/{clipId}/pose (JSON). No auth (public reference assets).
- proBenchmarks.ts: 6 maneuvers (bottom_turn/top_turn/snap/cutback/roundhouse/floater) each -> a clipId (reused across the 4 clips). available:true. i18n keys maneuver_* + ref_footage_note (EN + es/pt/ru/ar; fr falls back to EN).
- Compare screen (/compare/[id]): default proId="bottom_turn"; reference side now PLAYS the real clip (proPlayer) with live PoseOverlay skeleton synced via a 100ms currentTime ticker; radar+bars compare user vs pro. api.ts: getProVideoUrl(clipId), getProPose(clipId). VERIFIED via screenshot: maneuver chips + reference video + cyan skeleton overlay + joint angle render correctly.
- NOTE for user: these are generic royalty-free surfing clips assigned per maneuver (free stock does NOT isolate a named maneuver). For exact maneuver-isolated / named-pro clips, user must buy licensed footage (Pond5/Shutterstock label maneuvers) and swap the mp4+pose in static_assets/pro + register id in PRO_CLIP_IDS. Named pros (JJF/Medina/Yago/Italo) still need personal likeness licenses — not done.
- static_web re-exported + copied (compare + home changes live on served website). Redeploy needed for production.

## Login page redesign (session 2 cont.) — SurfCoach23 brand, KAI-style visuals
- User attached a target login mockup (Aloha greeting + glass email/password card + hero surfer-at-dusk + 3 feature icons + Register). Requested: build THIS design but branding stays "SurfCoach23" (NOT Kai), no "Kai" word on login. Home page (KAI dashboard) LEFT UNCHANGED per user.
- app/index.tsx hero fully redesigned: ImageBackground assets/surf-login.png (generated via nano banana, cinematic surfer at dusk, generic - no character name/shirt), LinearGradient overlay, brand "SURF[COACH cyan]23" + "THE AI SURF COACH", "Aloha 🤙" + "Ready for the next wave?" (cyan italic), glassmorphic card: Email + Password (eye show/hide) + "Forgot password?" (Alert -> email support, NO backend reset endpoint exists) + gradient "Continue" (=onEmailSubmit) + OR + Google + Apple(iOS), feature row (AI Analysis/Real Progress/Private & Safe), Register/Login toggle (isRegister). Marketing sections (how it works/pricing[web]/FAQ/contact/footer) kept below for web/legal. Footer brand -> "KAI · THE AI SURF COACH" earlier -- NOTE: inconsistent (login=SurfCoach23, home+footer=KAI). Ask user if they want unified brand.
- Verified via screenshot: matches target closely.

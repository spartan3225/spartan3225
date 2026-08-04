#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
user_problem_statement: |
  SurfCoach23 / KAI — High-priority reliability + redesign update:
  (1) Home screen redesign to premium "KAI" design (hero coach image, greeting,
      Kai message + KAI SCORE ring, stats row, ANALYZE SESSION CTA, recent
      sessions horizontal scroll, TECHNIQUE bars, ACHIEVEMENTS badges, quote).
  (2) CRITICAL: video upload + AI analysis must be reliable on first attempt.
  (3) CRITICAL: analysis persistence — uploaded video must NEVER disappear;
      user can reopen past analyses and replay video permanently.
  (4) Skeleton tracking reliability (retry, no random failures).
  (5) Pro Reference library (legal generic archetypes, no named pros).

backend:
  - task: "Persistence-first: store uploaded video to GridFS synchronously at finalize (single + multi) before any AI/conversion"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: true
        -agent: "main"
        -comment: |
          Added await _store_video_in_gridfs() call in _finalize_and_start_analysis
          and in finalize_multi_upload BEFORE asyncio.create_task. Verified via
          curl+DB: GridFS entry exists immediately at status=processing; video
          streams (200) even AFTER deleting the local file (simulated pod restart).
  - task: "Gemini analysis retry-with-backoff on transient errors (429/5xx/timeout)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: true
        -agent: "main"
        -comment: "3-attempt exponential backoff inside per-model loop in analyse_video_with_gemini. E2E upload produced status=ready."
  - task: "ffmpeg resolver fallback to bundled imageio-ffmpeg (iPhone .MOV conversion never breaks)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: true
        -agent: "main"
        -comment: "System ffmpeg missing in this env; _resolve_ffmpeg() falls back to imageio_ffmpeg binary. Verified .mov->mp4 conversion works with bundled binary."
  - task: "Pose extraction retry-once + never blocks ready status"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
        -working: true
        -agent: "main"
        -comment: "Retry loop added; pose failure sets pose_status=failed without affecting analysis 'ready'."
  - task: "LemonSqueezy multi-video checkout wired (variant 1975057, $9.99) + KeyError fix"
    implemented: true
    working: true
    file: "/app/backend/routers/lemonsqueezy.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "checkout returns live LS URL for plan_id=multi; txn insert falls back to LS_ADDONS."

frontend:
  - task: "Home screen KAI redesign (hero, message+score ring, stats, CTA, recent clips, technique bars, achievements, quote)"
    implemented: true
    working: "NA"
    file: "/app/frontend/app/(tabs)/index.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Full rewrite. Smoke-tested on web (empty state) — renders correctly with hero image, greeting, ring, stats, CTA, tabs (Home/Kai Review/Progress/Train/Profile). Needs test WITH real sessions to verify technique bars/achievements/recent clips + navigation."
  - task: "Upload client retry on single-shot POST /analyses and /analyses/finalize"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/api.ts"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "postFormWithRetry now wraps single-shot uploads; finalize retries 3x on 5xx/429."
  - task: "Pro Reference library relabel (compare screen uses t(pro.name))"
    implemented: true
    working: "NA"
    file: "/app/frontend/src/proBenchmarks.ts, /app/frontend/app/compare/[id].tsx"
    stuck_count: 0
    priority: "low"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Generic archetypes (Power/Progressive/Flow/Technical); names resolved via i18n."

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus:
    - "Persistence-first GridFS store (single + multi)"
    - "Upload + AI analysis reliability first-attempt (single-shot + chunked)"
    - "Reopen past analysis and replay video (video streams from GridFS)"
    - "Home screen KAI redesign renders with real session data + navigation"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
      NEW ROUND (post iter21): (a) Emergent Google auth hardened per playbook:
      SecureStore token on native w/ AsyncStorage migration (web still uses
      localStorage via AsyncStorage - NO web behavior change expected),
      maybeCompleteAuthSession, Android dismiss+listener+getInitialURL fallbacks,
      duplicate session_id guard, cold-start deep link, auth-callback cleans URL
      after success, backend session indexes (unique token + TTL). (b) logout()
      now fire-and-forget (verified). (c) Save Video button (download-outline icon,
      testID save-video-btn) added to analysis video controls - web triggers <a download>.
      (d) upload size guard 200MB + tip5. Please verify on WEB: 1) email register+login
      via /api/auth/register and /api/auth/login work E2E from the new login UI
      (email-input/password-input/email-submit-btn testIDs), 2) localStorage token
      session still works (set session_token=demo_coach_token -> /(tabs) loads),
      3) open a ready analysis -> save-video-btn present and clickable, 4) single
      MP4 upload E2E still reaches ready, 5) logout-btn returns to login screen.
      Do NOT delete user_sessions broadly; demo tokens were re-seeded.
    -agent: "main"
    -message: |
      Please test BACKEND reliability first (highest priority):
      1) Upload a small MP4 via POST /api/analyses (multipart) AND via chunked
         flow (/api/uploads/chunk + /api/analyses/finalize). Both should return
         200 and eventually status=ready.
      2) Immediately after upload (while processing), GET
         /api/analyses/{id}/video?token=... should already return 200 (video was
         stored to GridFS synchronously at finalize).
      3) Persistence: confirm the video still streams after processing completes
         (reopen scenario). GridFS is the source of truth.
      Then test FRONTEND: new Home screen (/(tabs)) renders hero+greeting+KAI
      SCORE ring+stats+CTA; tapping ANALYZE SESSION -> upload; recent session
      cards navigate to /analysis/{id}; technique bars + achievements show.
      AUTH for web testing: set localStorage 'session_token' = a valid session.
      Test accounts (see /app/memory/test_credentials.md): demo_token_active
      (free, may be quota-capped), demo_coach_token (coach tier). For upload
      tests that need quota, use demo_coach_token. Backend base for curl:
      https://wave-motion-ai.preview.emergentagent.com/api

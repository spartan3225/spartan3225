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
  SurfCoach23 backend tier system update — verify expanded plan tier list
  (free lifetime / beginner / plus / intermediate / advanced / pro / coach)
  including /api/plans, /api/analyses/quota, /api/payments/checkout,
  /api/analyses lifetime cap (must return 402), and
  _apply_subscription_if_paid() webhook tier mapping for new tier names.

backend:
  - task: "GET /api/plans returns 7 tiers in correct order/amounts/limits"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: |
          Verified. Returns 7 plans in order [free, beginner, plus,
          intermediate, advanced, pro, coach] with amounts
          [0, 5, 12, 20, 35, 60, 120] and daily_limit
          [1, 1, 3, 6, 10, 15, -1]. is_lifetime=true ONLY on free.
          free_lifetime_limit=1 present. (legacy free_daily_limit=1 also
          present for old clients — fine.)

  - task: "GET /api/analyses/quota — is_lifetime flag for free vs paid"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: |
          Verified using seeded demo creds.
          • Free user (demo_token_active): is_lifetime=true, tier=free, limit=1.
            Count is lifetime-total: after seeding 1 prior analysis,
            used_today=1, remaining=0; after wipe, used_today=0, remaining=1.
          • Coach user (demo_coach_token): is_lifetime=false, tier=coach,
            limit=-1 (unlimited), used_today=0.

  - task: "POST /api/payments/checkout for new tiers + invalid plan rejection"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: |
          All 4 new tiers (beginner, intermediate, advanced, pro) plus plus &
          coach return 200 with a real Stripe URL
          (https://checkout.stripe.com/c/pay/cs_test_*) and persist a
          payment_transactions record. plan_id="invalid_plan" returns 400
          with detail "Invalid plan" as expected.

  - task: "POST /api/analyses lifetime cap (CRITICAL — must return 402)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: |
          CRITICAL behaviour confirmed.
          • Free user with 1 prior analysis seeded → POST /api/analyses returns
            402 with detail "Free plan allows only 1 analysis ever. Upgrade to
            a paid plan to keep analysing." (NOT 422 / NOT 500). 
          • Free user with 0 prior analyses → request passes the lifetime
            check and proceeds to the Gemini call (returns 500 only because
            we sent dummy mp4 bytes — proves the cap permitted the request).
          Minor: spec asked the message contain the literal word "lifetime";
          current message says "ever" instead. Behaviour is correct, only the
          word "lifetime" is missing in the user-facing string. Optional polish
          for the main agent: include "lifetime" in the 402 detail at
          server.py:594.

  - task: "_apply_subscription_if_paid assigns new tier names (beginner/intermediate/advanced/pro)"
    implemented: true
    working: true
    file: "/app/backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "testing"
        -comment: |
          Verified by seeding payment_transactions docs with each new plan_id
          and invoking server._apply_subscription_if_paid(session_id,
          event_paid=True) directly.
          For plan_id ∈ {beginner, intermediate, advanced, pro}, the user
          tier was correctly set to the matching plan_id, subscription_status
          set to "active", and subscription_expires_at populated ~30 days
          ahead. apply_result reports applied=True, payment_status="paid",
          status="complete". The same logic flow as plus/coach — no special
          casing missing for new tiers.

metadata:
  created_by: "testing_agent"
  version: "1.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "testing"
    -message: |
      Ran /app/backend_test.py against
      https://wave-motion-ai.preview.emergentagent.com/api.
      49 of 50 assertions passed; the only failing assertion is a
      cosmetic check that the 402 detail string contains the literal word
      "lifetime" (it currently says "1 analysis ever"). All 5 review-request
      items behave correctly:
        1. /plans → 7 tiers, correct order/amounts/limits, is_lifetime true
           only on free, free_lifetime_limit=1.
        2. /analyses/quota → is_lifetime true for free (lifetime total),
           false for coach (-1 limit).
        3. /payments/checkout → 200 + real Stripe URL for beginner,
           intermediate, advanced, pro (and plus/coach); invalid_plan→400.
        4. /analyses lifetime cap → 402 when free user has 1 prior, request
           proceeds when 0 prior.
        5. _apply_subscription_if_paid → correctly maps beginner /
           intermediate / advanced / pro to user.tier and sets a 30-day
           subscription_expires_at.
      Tests cleaned up after themselves: demo user reset to free, seeded
      analyses removed, fake payment_transactions removed.
      Optional polish for main agent: include the word "lifetime" in the
      402 detail string at server.py line 594 to match the spec wording.

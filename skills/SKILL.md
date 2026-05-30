# SKILL INDEX — Othman Safi (Safi23) Trading Bot

# For: XAUUSD LRS Strategy | Version: 1.0 | Date: May 2026

# Usage: Load this index at the start of every session to know which skill to apply

-----

## WHAT ARE SKILLS?

Skills are pre-loaded knowledge files that Claude applies automatically during
trading analysis, bot development, and strategy sessions. They encode rules,
psychology frameworks, and expert principles so Claude never has to re-derive
them from scratch.

Always load the relevant skill before beginning any session task.

-----

## SKILL REGISTRY

| Skill File                  | Purpose                                         | Load When                                              |
|-----------------------------|-------------------------------------------------|--------------------------------------------------------|
| `SKILL_Trading_Masters.md`  | 7 trading masters + 10 commandments framework   | Every trading session, analysis, or bot logic question |

-----

## SESSION START PROTOCOL

Before every session, Claude will:

1. Confirm which skill(s) are loaded
2. Check the Gold Macro Checklist (DXY, rates, geopolitics)
3. Review the day's trade limit (max 3 trades, $50 daily loss cap)
4. Apply the relevant master's principles to any request

-----

## CORE RULES (Never Overridden)

- **SL:** $35 fixed — never removed, never moved against the trade
- **Lot size:** 0.1 fixed — never increased after a loss or win
- **Max trades/day:** 3
- **Daily loss limit:** $50 — session ends if hit
- **Minimum confidence:** 90% before entry
- **Hedge activation:** only after +$100 profit, never before

-----

## SKILL LOADING INSTRUCTIONS

To activate a skill, paste or reference its file at the start of your session.

**Example prompt:**
> "Load SKILL_Trading_Masters.md — I want to review today's XAUUSD setup."

Claude will confirm the skill is active and apply its frameworks throughout
the session.

-----

## VERSION HISTORY

| Version | Date     | Notes                        |
|---------|----------|------------------------------|
| 1.0     | May 2026 | Initial index created        |

# Lingo: a Duolingo-style language-learning app

A layered monolith with a **FastAPI** backend and a **Next.js** frontend, using **SQLite** for storage.
Lingo's branding is original. Its design takes inspiration from Duolingo.

| Part | Stack |
| --- | --- |
| `backend/` | Python 3.11+, FastAPI, SQLAlchemy 2 (sync), Pydantic v2, pydantic-settings, SQLite |
| `frontend/` | Next.js 16 (App Router), TypeScript, Tailwind CSS v4, TanStack Query |

```
routers (thin) → services (rules, one transaction per use case) → SQLAlchemy models → SQLite
```

## Status

- [x] **M0: scaffold.** Both apps boot, CORS is configured, `GET /api/v1/health` works, and the home page calls it.
- [x] **M1: database and models.** 12 tables with constraints, indexes and schema tests.
- [x] **M2: seed data.** One Spanish course (3 units, 9 skills, 22 lessons, 117 exercises), a default learner, and 9 leaderboard bots.
- [x] **M3: learning path.** Pure unlocking rules, plus `GET /path`.
- [x] **M4: lesson engine.** Sessions, one exercise at a time, server-side grading for 5 exercise types, hearts, and idempotent completion.
- [x] **M5: gamification.** XP, calendar-day streaks, daily goal, achievements, leaderboard, and `GET /me`.
- [x] **M6: hearts and polish.** Lazy heart regeneration, mock gem refill, optimistic locking, and API docs.
- [x] **M7: frontend architecture.** API client, TanStack Query hooks, layout, responsive design, and mock auth integration.
- [x] **M8: lesson player.** Full exercise engine supporting all 5 types (multiple choice, word bank, matching pairs, fill-in-blank, type answer), immediate feedback, heart deduction, and session recovery.
- [x] **M9: gamification & profile.** Total XP, calendar-day streaks, daily goal progress, achievement cards & badges, emerald league leaderboard, and heart refill modal.
- [x] **M10: visual/UX polish.** Responsive layouts, Duolingo-style 3D buttons, bouncy nodes, sound/feedback states, mobile bottom navigation bar.
- [x] **M11: QA & testing.** 312 backend tests, frontend typecheck, ESLint, Next.js production build, comprehensive black-box walkthrough with zero console or network errors.

## Current Status & Implemented Features

1. **Learning Path / Skill Tree (`/`)**: Visual learning path featuring locked, available, and completed skills across 3 units. Interactive skill popover with progress indicators, lessons list, and unit banners.
2. **Lesson Player (`/lesson/[id]`)**: Full interactive lesson flow for all 5 backend exercise types:
   - Multiple Choice (image emoji support, option selection, keyboard shortcuts)
   - Word Bank / Translation (tap tiles to form sentences, return tiles to pool)
   - Matching Pairs (pair matching with locked states)
   - Fill in the Blank (inline sentence fill with option pills)
   - Type the Answer (accent special characters toolbar, single-submission Enter key support)
3. **Real-time Feedback & Hearts**: Immediate feedback sheets (correct green / incorrect red with correct answer explanation), authoritative server-side heart deduction (5 to 0), and out-of-hearts modal.
4. **Session Recovery**: Mid-lesson refreshes automatically restore progress to the active exercise without losing state.
5. **Gamification & Rewards**:
   - Lesson completion screen awarding +10 XP, streak extensions, daily goal progress, and unlocked achievement banners.
   - Leaderboard (`/leaderboard`) ranking learners in Emerald League with current user highlighted.
   - Profile (`/profile`) showcasing streak, total XP, lesson & skill counts, daily goal, and 15 achievement tiers.
6. **Heart Refill & Regeneration**: Real-time 30-minute countdown timer, gem refill modal (350 gems), full-hearts protection no-op, and insufficient-gems validation.
7. **Responsive Design**: Full desktop sidebar layout and mobile-optimized viewport (390px) with bottom navigation bar.

## Run locally

Prerequisites: Python 3.11+, Node.js 20.9+.

```bash
# Terminal 1: backend on http://localhost:8000
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.db.seed                 # create tables + demo data (no-op if already seeded)
uvicorn app.main:app --reload --port 8000

# Terminal 2: frontend on http://localhost:3000
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

- **Reset the demo:** run `python -m app.db.seed --reset`. `--today YYYY-MM-DD` pins the reference day; the same day always gives an identical database.
- **After a model change** (there are no migrations), delete `backend/lingo.db*` and seed again.
- **Quick heart demo:** `HEART_REGEN_MINUTES=1 uvicorn app.main:app --port 8000` regenerates one heart per minute.
- **Interactive API docs:** http://localhost:8000/api/v1/docs

**Demo state after seeding** (learner `learner`, "Alex", Asia/Kolkata):
- 80 XP, a 6-day streak (last active yesterday), 0/20 daily XP, 5/5 hearts, 600 gems.
- 7 of 22 lessons done: Greetings and Introductions complete, Basic Words half done, everything else locked.
- 4 of 15 achievements unlocked. #9 of 10 on the leaderboard.
- Completing lesson 8 gives +10 XP, streak 7, "7-Day Streak" (and "Sharpshooter" if perfect), and rank #8.

## Quality checks

```bash
cd backend && source .venv/bin/activate
ruff check . && ruff format --check . && pytest
cd ../frontend && npm run typecheck && npm run lint && npm run build
```

## Configuration

| Variable | Where | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | `backend/.env` | `sqlite:///<backend>/lingo.db` | SQLAlchemy URL |
| `CORS_ORIGINS` | `backend/.env` | `http://localhost:3000,http://127.0.0.1:3000` | Browser origins allowed |
| `HEART_REGEN_MINUTES` | `backend/.env` | `30` | Minutes per regenerated heart |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | `http://localhost:8000/api/v1` | API base URL (inlined at build) |

---

## API reference

**Base URL** `/api/v1`, JSON in and out.

**Authentication is mocked.** Every request acts as the seeded learner `learner`; only `api/deps.get_current_user` would change for real auth. If the database hasn't been seeded, every learner endpoint returns `503 LEARNER_NOT_FOUND`.

**Errors** always look like `{"error": {"code", "message", "details"}}`. Clients branch on `code`, never on `message`.

| Status | Codes |
| --- | --- |
| 403 | `LESSON_LOCKED` |
| 404 | `LESSON_NOT_FOUND`, `SESSION_NOT_FOUND` (also returned for other learners' sessions), `COURSE_NOT_FOUND`, `NO_ACTIVE_COURSE` |
| 409 | `NO_HEARTS`, `SESSION_NOT_ACTIVE`, `EXERCISE_NOT_CURRENT`, `DUPLICATE_SUBMISSION`, `INSUFFICIENT_GEMS` |
| 422 | `VALIDATION_ERROR` (malformed body, unknown fields), `INVALID_ANSWER` (not a legal move; not graded, no heart lost) |
| 500 / 503 | `INTERNAL_ERROR` / `LEARNER_NOT_FOUND` |

**`Hearts` object**, identical in every response that carries hearts. The values are *effective*: regeneration is already applied.

```json
{"current": 3, "max": 5, "regenerating": true, "seconds_until_next": 900, "refill_cost_gems": 350}
```

### Endpoints

| Method and path | Purpose | Request | Response (key fields) | Errors |
| --- | --- | --- | --- | --- |
| `GET /health` | Liveness | – | `status`, `service`, `version`, `time` | – |
| `GET /path` | Home screen: the whole course with derived states | – | `course`, `progress{completed,total,percent}`, `current_skill_id`, `current_lesson_id`, `units[]{id, position, title, color, state, progress, completed_skills, total_skills, skills[]{id, position, title, icon, state, progress, next_lesson_id, is_current, lessons[]{id, position, title, state}}}` | 404 `NO_ACTIVE_COURSE` |
| `POST /lessons/{lesson_id}/start` | Start a lesson, or resume the active session for it. Starting a different lesson abandons the old session. | – | `session_id`, `mode`, `lesson{id,title,skill_id,skill_title}`, `progress{status,total,answered,correct,incorrect}`, `hearts`, `current_exercise`, `resumed`, `abandoned_session_id` | 404 `LESSON_NOT_FOUND`, 403 `LESSON_LOCKED`, 409 `NO_HEARTS` (`details.hearts` has the countdown) |
| `GET /sessions/{id}` | Session state, e.g. to resume after a refresh | – | Same as start, without `resumed`/`abandoned_session_id`. `current_exercise` is null once ended. | 404 `SESSION_NOT_FOUND` |
| `GET /sessions/{id}/current` | The current exercise only | – | `id`, `type`, `position` (1-based), `prompt`, `payload` (**never the solution**) | 404, 409 `SESSION_NOT_ACTIVE` |
| `POST /sessions/{id}/answer` | Grade the current exercise on the server | `{"exercise_id", "answer": {"type", ...}}`, see answer shapes below | `exercise_id`, `correct`, `correct_answer` (display text), `note`, `explanation`, `replayed`, `hearts`, `progress`, `failure_reason` (`"out_of_hearts"`/null), `rewards` (only on the completing answer: `xp_awarded`, `xp_total`, `first_completion`, `streak{before,after,longest,extended}`, `daily_goal{goal_xp,today_xp,completed,just_completed}`, `new_achievements[]`) | 404, 409 `SESSION_NOT_ACTIVE` / `NO_HEARTS` / `EXERCISE_NOT_CURRENT` / `DUPLICATE_SUBMISSION`, 422 `INVALID_ANSWER` / `VALIDATION_ERROR` |
| `POST /sessions/{id}/abandon` | Quit a lesson (repeating it is harmless) | – | Session state | 404, 409 if already completed or failed |
| `GET /me` | Header and profile summary | – | `username`, `display_name`, `avatar_color`, `today` (local date), `xp_total`, `streak{current,longest,extended_today,last_active_date}`, `hearts`, `gems`, `daily_goal{goal_xp,today_xp,completed}`, `stats{lessons_completed,total_lessons,skills_completed,total_skills,perfect_lessons}`, `achievements[]{code,title,description,icon,tier,unlocked,unlocked_at,current,target}` | – |
| `GET /leaderboard` | Everyone ranked by total XP (read-only) | – | `entries[]{rank,username,display_name,avatar_color,xp,is_current_user}`, `current_user_rank` | – |
| `POST /hearts/refill` | Mock refill: full hearts for 350 gems. A free no-op when already full. | – | `refilled`, `gems_spent`, `gems`, `hearts` | 409 `INSUFFICIENT_GEMS` |

**Answer shapes.** The `type` field must match the exercise's type, and unknown fields are rejected.

| Exercise type | `answer` |
| --- | --- |
| `multiple_choice` | `{"type":"multiple_choice","option_id":"b"}` |
| `word_bank` | `{"type":"word_bank","tile_ids":["t3","t1"]}` (in the order the learner placed them) |
| `matching_pairs` | `{"type":"matching_pairs","pairs":[["l1","r2"], ...]}` (every item used exactly once) |
| `fill_blank` | `{"type":"fill_blank","text":"bebo"}` (tapped option's text, or typed) |
| `type_answer` | `{"type":"type_answer","text":"Buenos días"}` |

---

## Rules

**Learning path (`services/path_rules.py`, pure).**
- The path is one linear sequence: units in order, then skills in order within each unit.
- A skill is **completed** when all of its lessons are completed. It's **unlocked** if it's the first skill, the previous skill is completed, or the learner has already started it.
- An unlocked skill is **in_progress** if some lessons are done, otherwise **available**. Everything else is **locked**.
- Lessons are completed, available (their skill is unlocked) or locked.
- Percentages round down.
- Nothing about progress is stored except `lesson_completions`.

**Lesson lifecycle (`services/lesson_service.py`).**
- `start → ACTIVE → COMPLETED` (last exercise answered with hearts left), `→ FAILED` (a wrong answer took the last heart), or `→ ABANDONED` (quit, or started another lesson).
- The learner can have at most one active session (enforced by a partial unique index).
- Exercises are fixed when the session starts. Each is answered once (`UNIQUE(session_id, exercise_id)`), so the current exercise is `exercise_ids[number of answers]`; the client never chooses it.
- Resending an identical answer replays the stored result. A different answer for an already-graded exercise returns 409.
- Each answer is **one transaction**: grade → answer row → session → hearts → completion → XP → streak → achievements.

**Grading (`services/grading.py`, pure).**
- **Multiple choice:** option id match.
- **Word bank:** exact word order; case is ignored.
- **Matching pairs:** the set of pairs must match, and all items must be used.
- **Fill in the blank and type the answer:** ignore case, extra whitespace and punctuation `.,!?¿¡;:` and quotes. An accent-only difference is accepted with a note. There's no other fuzzy matching.

**XP (`xp_service.py`).**
- **10 XP** for the first successful completion of a lesson. 0 for replays and failures.
- Each award writes one `xp_events` row and adds to `users.xp_total` in the same transaction.
- `UNIQUE(xp_events.session_id)` means a session can never award twice.

**Streak (`streaks.py`, pure).**
- Counts consecutive **local calendar days** (learner's timezone) with an XP-earning completion.
- Same day: unchanged. Next day: +1. Any missed day: resets to 1. Longest = the maximum reached.
- The displayed streak shows 0 once a whole day has been missed (worked out when read; nothing is written on reads).

**Daily goal.** Today's XP is the sum of `xp_events` on the learner's local date. The goal is `users.daily_goal_xp` (default 20). It's never stored.

**Hearts (`hearts.py`, the single heart service).**
- Max 5. A wrong answer costs 1, and hearts never go below 0. At 0 effective hearts, starting a lesson or answering returns `NO_HEARTS`.
- **Regeneration:** +1 heart per `HEART_REGEN_MINUTES` (default 30), counted from `hearts_updated_at` (the start of the current interval). Several hearts can regenerate at once, up to max.
- **Leftover time is kept:** the timer advances by whole intervals, so 3 hearts at 12:00 means 4 at 12:45, with 15 minutes to the next.
- **Losing a heart** from full starts the timer. Losing one while regenerating keeps the timer running.
- **Reads compute; writes save.** GETs compute effective hearts without writing. Writes (answering, refilling) first save the regenerated state, then apply their change, in the same transaction.
- **Refill** costs 350 gems, is a no-op when full, and returns 409 `INSUFFICIENT_GEMS` if the learner can't afford it.
- **Concurrency:** `users.version` is an optimistic lock, so a write based on stale data fails and is retried once from fresh state.

**Achievements (`achievement_service.py`).**
- Rules are rows: *metric ≥ threshold*. Metrics: `total_xp`, `streak`, `lessons_completed`, `perfect_lessons`, `skills_completed`.
- Checked after XP and streak in the completion transaction. The (user, achievement) primary key makes a duplicate unlock impossible.
- Required ones: First Lesson = `scholar_1`, 100 XP = `sage_1`, 3-Day Streak = `wildfire_1`, 7-Day Streak = `wildfire_2`.
- Gem rewards are listed but not paid out.

**Leaderboard.** `ORDER BY xp_total DESC, id ASC`, served by an index. Ranks are positions.

---

## Database schema (SQLite, 12 tables)

| Table | Purpose | Key constraints |
| --- | --- | --- |
| `courses` → `units` → `skills` → `lessons` → `exercises` | Course content, shared by all learners | `UNIQUE(parent_id, order_index)` at each level; ON DELETE CASCADE down the tree |
| `exercises` | `type` + `payload` (browser-safe JSON) + `solution` (server-only JSON) | CHECK on type; both JSON columns must be objects |
| `users` | Learner, stored counters (`hearts`, `hearts_updated_at`, `gems`, `xp_total`, `streak_count`, `longest_streak`, `last_streak_date`, `daily_goal_xp`), `timezone`, `version` | CHECKs (hearts 0–5, non-negative counters, goal ∈ {10,20,30,50}); leaderboard index |
| `lesson_sessions` | One lesson attempt: `mode`, `status`, `exercise_ids`, `mistakes_count`, `xp_awarded`, `result` | Partial UNIQUE (one active per user); mode/target and status/ended_at CHECKs |
| `session_answers` | Graded answers | `UNIQUE(session_id, exercise_id)` |
| `lesson_completions` | **The** progress fact (everything else is derived) | `UNIQUE(user_id, lesson_id)` |
| `xp_events` | XP ledger (`amount`, `source`, `local_date`) | `UNIQUE(session_id)`, amount > 0 |
| `achievements`, `user_achievements` | Catalog + unlocks | `UNIQUE(code)`, `UNIQUE(metric, tier)`, composite PK |

- Learner rows RESTRICT deletion of content they reference, and cascade when their user is deleted.
- Every foreign key column is indexed.
- Timestamps are stored in UTC and returned timezone-aware.

## Repository layout

```
backend/app/
  main.py                    app factory: CORS, error handlers, routers
  core/                      config (env), constants, clock (utc_now, local_date), errors
  db/                        base, UTCDateTime type, engine + pragmas, init_db, seed/ (JSON data + loader)
  models/                    content, user, progress, gamification, enums
  schemas/                   exercises (payload/solution), path, lesson, gamification
  services/                  path_rules, path_service, grading, lesson_service, hearts,
                             xp_service, streaks, achievement_service, progression_service,
                             profile_service, leaderboard_service
  api/deps.py, api/routers/  health, path, lessons, sessions, me, leaderboard, hearts
backend/tests/               one test module per service/API area (pytest)
frontend/src/
  app/                       layout, providers, globals.css, pages (path, lesson, leaderboard, profile)
  components/
    common/                  icons, error and loading states
    hearts/                  hearts display, out-of-hearts and refill modals
    layout/                  app shell, sidebar, top nav, bottom nav
    lesson/                  header, feedback sheet, completion screen, 5 exercise renderers
    path/                    learning path, unit sections, interactive skill nodes
  lib/                       API client, TypeScript schema types, TanStack Query hooks, config
```

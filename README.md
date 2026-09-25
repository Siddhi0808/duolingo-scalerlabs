# Lingo: a Duolingo-style language-learning app

Lingo is a full-stack clone of the Duolingo web app. A learner follows a Spanish learning path, completes lessons made of five interactive exercise types, earns XP, keeps a daily streak, loses and refills hearts, and climbs a leaderboard. All progress is stored per learner in SQLite.

**Hosted demo:** _not deployed yet — add the URL here once it is live (see [Deployment](#deployment))._

## Tech stack

| Part | Stack |
| --- | --- |
| `frontend/` | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, TanStack Query |
| `backend/` | Python 3.11+, FastAPI, SQLAlchemy 2 (sync), Pydantic v2, pydantic-settings |
| Database | SQLite (WAL mode, foreign keys enforced) |
| Tests / tooling | pytest (312 tests), ruff, ESLint, `tsc` |

## Features

- **Learning path:** 3 units, 9 skills and 22 lessons with locked, available, in-progress and completed states, progress rings, a START/CONTINUE marker and a skill popover.
- **Top bar:** streak, total XP, gems and hearts (with the regeneration countdown).
- **Lesson player:** multiple choice, word bank (translate by tapping words), matching pairs, fill in the blank and type the answer. Immediate correct/incorrect feedback bar with sounds and animation, a lesson progress bar, hearts, and a quit confirmation.
- **Hearts:** a wrong answer costs one heart; losing the last one fails the lesson. Hearts regenerate over time, or can be refilled with (mock) gems.
- **Rewards:** XP on first completion, calendar-day streaks, a daily XP goal, 15 achievements, and a lesson-complete celebration screen.
- **Leaderboard** of the learner and 9 seeded rivals, a **profile** with stats and achievements, and a **settings** screen (placeholders).
- **Toasts** for completed lessons and heart refills; modals for out-of-hearts, refill, quitting and achievement details.
- **Resilience:** refreshing mid-lesson resumes the same exercise; locked or missing lessons and an unreachable backend have friendly screens.
- **Responsive:** desktop sidebar layout and a mobile layout with a bottom navigation bar.

## Architecture

```
Browser (Next.js, client components)
   │  fetch JSON  (lib/api/client.ts, TanStack Query hooks)
   ▼
FastAPI  /api/v1
   routers (thin)  →  services (game rules, one transaction per use case)  →  SQLAlchemy models  →  SQLite
```

- **The server is the source of truth.** The browser never grades answers, chooses the next exercise, or computes XP, streaks or hearts. It renders what the API returns and invalidates cached queries after changes.
- **Pure rule modules** (`path_rules`, `grading`, `streaks`, and the heart maths in `hearts`) take plain values and return plain values, so they are unit-tested without a database.
- **Derived, not stored:** skill and unit states, daily XP and the displayed streak are computed on read. The only progress fact is `lesson_completions`.
- **Consistency:** every answer is one transaction (grade → answer row → hearts → completion → XP → streak → achievements). Unique constraints make repeated submissions and duplicate XP impossible, and an optimistic lock (`users.version`) protects hearts and gems against concurrent writes.

### Frontend structure

```
frontend/src/
  app/                  routes: / (path), /lesson/[id], /leaderboard, /profile, /settings
                        layout.tsx, providers.tsx (TanStack Query + toasts), globals.css (design tokens)
  components/
    common/             icons, error state, toast provider
    hearts/             heart refill modal
    layout/             app shell, sidebar, top bar, bottom nav
    lesson/             lesson header, feedback sheet, completion screen, modals, 5 exercise renderers
    path/               unit banner, skill node with popover, loading skeleton
    widgets/            daily goal and course stats cards
  lib/
    api/                typed API client, response types, TanStack Query hooks
    audio.ts            Web Audio sound effects (no audio files)
    config.ts           API base URL
```

### Backend structure

```
backend/app/
  main.py               app factory: CORS, error handlers, routers
  core/                 settings (env), game constants, clock (UTC and local dates), error types
  db/                   declarative base, UTC datetime type, engine + SQLite pragmas, init_db
    seed/               seed loader, exercise builder, data/*.json (course, achievements, learners)
  models/               content, user, progress, gamification, enums
  schemas/              Pydantic request/response models, exercise payload/solution shapes
  services/             path_rules, path_service, lesson_service, grading, hearts, xp_service,
                        streaks, progression_service, achievement_service, profile_service,
                        leaderboard_service
  api/deps.py           per-request DB session and the mocked current user
  api/routers/          health, path, lessons, sessions, me, leaderboard, hearts
backend/start.sh        production entry point: seed if empty, then uvicorn on $PORT
backend/tests/          pytest suite, one module per service or API area
```

## Setup (local)

Prerequisites: Python 3.11+ and Node.js 20.9+.

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

Interactive API docs: http://localhost:8000/api/v1/docs

### Environment variables

| Variable | Where | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | `backend/.env` | `sqlite:///<backend>/lingo.db` | SQLAlchemy URL. Use an absolute path (4 slashes) in production. |
| `CORS_ORIGINS` | `backend/.env` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins allowed to call the API |
| `HEART_REGEN_MINUTES` | `backend/.env` | `30` | Minutes per regenerated heart (use a small value for demos) |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | `http://localhost:8000/api/v1` | API base URL. Inlined at build time, so rebuild after changing it. |

`backend/.env.example` and `frontend/.env.example` list the same variables.

### Seed data

`python -m app.db.seed` creates the tables and loads, from `backend/app/db/seed/data/`:

- one Spanish course: 3 units, 9 skills, 22 lessons, 117 exercises covering all five types;
- 15 achievements;
- the sample learner **Alex** (`learner`) and 9 leaderboard rivals.

Commands:

- `python -m app.db.seed` does nothing if the course already exists.
- `python -m app.db.seed --reset` deletes everything and seeds again.
- `--today YYYY-MM-DD` pins the reference day; the same day always produces an identical database.
- There are no migrations: after a model change, delete `backend/lingo.db*` and seed again.

**Demo state after seeding** (dates are relative to the seed day, in Asia/Kolkata):

- 80 XP, a 6-day streak (last active yesterday), 0/20 daily XP, 5/5 hearts, 1500 gems (four 350-gem refills).
- 7 of 22 lessons done: Greetings and Introductions complete, Basic Words half done, everything after it locked.
- 4 of 15 achievements unlocked, #9 of 10 on the leaderboard.
- Completing lesson 8 (Basic Words → Animals and things) gives +10 XP, streak 7, the "Wildfire" 7-day achievement and rank #8.

## Running tests

```bash
cd backend && source .venv/bin/activate
pytest                                   # 312 tests: rules, services, API, schema, seed
ruff check . && ruff format --check .

cd ../frontend
npm run typecheck && npm run lint && npm run build
```

## Assumptions

- **One learner, one course.** The app always acts as the seeded learner and has one Spanish course (from English), as the assignment allows.
- **XP:** 10 XP for the first successful completion of a lesson. Replaying a completed lesson is allowed for practice but earns 0 XP and does not extend the streak, so XP can't be farmed.
- **Streak:** counts consecutive calendar days in the learner's timezone (Asia/Kolkata for the sample learner) with at least one XP-earning lesson. The rules are pure functions over dates, so day changes are tested without waiting (`--today` pins the seed day).
- **Hearts:** 5 maximum; 1 heart regenerates every 30 minutes (configurable); a refill costs 350 gems. A lesson fails when a wrong answer takes the last heart.
- **Grading:** typed answers ignore case, punctuation and extra spaces, and accept a missing accent with a note. Matching pairs is graded as a whole exercise, like other exercises.
- **Daily goal:** 20 XP per day for the sample learner.
- **Leaderboard:** all-time XP across all seeded users (the "league" styling is cosmetic).

## Mock authentication

There is no login. `api/deps.get_current_user` returns the seeded learner (`DEFAULT_USERNAME`, default `learner`) for every request. Every service takes the user as a parameter, so real authentication would only replace that one dependency. If the database has not been seeded, learner endpoints return `503 LEARNER_NOT_FOUND`.

## Mocked or placeholder features

| Feature | Status |
| --- | --- |
| Authentication | Mocked (single sample learner) |
| Gems | Mocked currency; only spent on heart refills; no purchases |
| Settings | Placeholder screen showing real profile/course values; controls are marked "Coming soon" |
| Audio | Synthesised sound effects for correct, incorrect and complete; no speech or pronunciation exercises |
| Friends / social | Not implemented; the leaderboard uses seeded rivals |
| Multiple languages | One seeded course (Spanish) |
| Achievement gem rewards | Listed in the catalog but not paid out |
| Practice mode | Present in the schema and seed history, not exposed in the UI |

## Deployment

**Status: not deployed yet.**

The app is two services. SQLite needs a disk that survives restarts, so the backend runs as a **single instance with a persistent disk**, and the frontend is a static-first Next.js app.

| Part | Host | Why |
| --- | --- | --- |
| Backend (FastAPI + SQLite) | **Render web service (paid instance) with a persistent disk** | Disk contents survive restarts and redeploys; free instances have no persistent disk |
| Frontend (Next.js) | **Vercel** (Hobby) | Native Next.js hosting; only needs one environment variable |

Any host with a persistent volume works the same way (e.g. Railway with a volume): run `backend/start.sh` with `DATABASE_URL` pointing at the volume.

### Backend (Render)

1. **New → Web Service**, connect the GitHub repository.
2. Settings:
   - Root Directory: `backend`
   - Runtime: Python
   - Build Command: `pip install .`
   - Start Command: `sh start.sh`
   - Instance type: any paid type (required for a disk)
   - Health Check Path: `/api/v1/health`
3. **Disk:** add a disk with mount path `/var/data` (1 GB is plenty).
4. **Environment variables:**

   | Name | Value |
   | --- | --- |
   | `PYTHON_VERSION` | `3.13.5` (the tested version; Render's default is newer) |
   | `DATABASE_URL` | `sqlite:////var/data/lingo.db` (four slashes: absolute path on the disk) |
   | `CORS_ORIGINS` | your Vercel URL, e.g. `https://lingo.vercel.app` |
   | `HEART_REGEN_MINUTES` | optional; e.g. `5` so evaluators regain hearts quickly |

5. Deploy, then open `https://<backend>.onrender.com/api/v1/health` (should return `"status":"ok"`) and `/api/v1/path`.

`start.sh` runs `python -m app.db.seed` and then `uvicorn` on `$PORT`. The seed creates the tables and demo data on the first start (the disk is only mounted at runtime, so it can't happen during the build) and does nothing on later starts, so learner progress is kept across restarts and redeploys. Keep the service at **one instance**: SQLite has a single writer, and Render doesn't allow scaling a service that has a disk.

`DATABASE_URL` must be set: without it the database file is created next to the installed package, outside the disk, and is lost on every deploy.

### Frontend (Vercel)

1. **Add New → Project**, import the repository.
2. Root Directory: `frontend` (framework preset: Next.js; the default build command `npm run build` is correct).
3. Environment variable: `NEXT_PUBLIC_API_URL=https://<backend>.onrender.com/api/v1`, set **before** deploying. It is inlined at build time, so redeploy after changing it. A Vercel build without it fails on purpose instead of producing a site that calls `localhost`.
4. Deploy, then copy the production URL into the backend's `CORS_ORIGINS` (a trailing slash is ignored) and let the backend redeploy.

Only the production URL is allowed by CORS. Vercel preview URLs will show "Can't connect" unless you add them to `CORS_ORIGINS` (comma-separated).

### Before an evaluation

Reset the demo so the sample learner's streak is current ("last active yesterday"). In the Render service's **Shell** tab:

```bash
python -m app.db.seed --reset
```

### Post-deployment smoke test

1. `GET /api/v1/health` returns `ok`; the site loads the path with streak 6, XP 80, gems 1500 and 5 hearts.
2. Complete lesson 8 (Basic Words → Animals and things): +10 XP, streak 7, "Wildfire" achievement, a toast on the path.
3. Answer wrong until hearts run out; refill from the modal (gems −350).
4. Refresh in the middle of a lesson: it resumes at the same exercise.
5. Check profile, leaderboard (#8) and settings.
6. **Persistence:** in Render, choose **Manual Deploy → Deploy latest commit** (or restart). After it comes back, XP, streak and gems must be unchanged.

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
- Examples: First Lesson = `scholar_1`, 100 XP = `sage_1`, 3-Day Streak = `wildfire_1`, 7-Day Streak = `wildfire_2`.
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


## Known limitations

- **SQLite** allows one writer at a time. That is fine for one learner, but it is not built for many concurrent users.
- **No migrations:** the schema is created from the models; changing a model means reseeding.
- **Seed dates are relative to the seed day.** A database seeded several days ago shows the sample learner's streak as 0 (correctly, because days were missed). Reseed before a demo.
- **Matching pairs** is graded as one exercise, so if any pair is wrong, every pair is shown in red.
- **Replays earn 0 XP** by design (see Assumptions).
- **Settings are read-only** placeholders, and the learner's timezone is fixed per user in the seed.
- **No frontend automated tests;** the frontend is checked with TypeScript, ESLint, a production build and manual browser testing.

## AI usage

As the assignment allows, AI coding assistants were used heavily during development: for scaffolding, writing and refactoring code, writing tests, and reviewing the UI and code. Every change was reviewed, run and tested by the author, and the design decisions documented above (schema, transaction boundaries, derived state, idempotency, heart regeneration) are the author's to explain.

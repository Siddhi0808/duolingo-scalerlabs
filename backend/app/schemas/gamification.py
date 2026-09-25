"""Response schemas for rewards (lesson completion), GET /me and GET /leaderboard.

No internal database ids are exposed except where the UI needs a stable key: users
are keyed by `username`, achievements by `code`.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --------------------------------------------------------------------------- shared


class StreakInfo(_Out):
    current: int  # 0 once a whole local day has been missed (derived on read)
    longest: int
    extended_today: bool  # true once today's streak day is earned
    last_active_date: date | None  # learner's local calendar date


class DailyGoal(_Out):
    goal_xp: int
    today_xp: int  # sum of today's XP events (learner's local date); never capped
    completed: bool  # today_xp >= goal_xp


class AchievementBadge(_Out):
    code: str
    title: str
    description: str
    icon: str
    tier: int


# --------------------------------------------------------------------------- completion


class StreakChange(_Out):
    before: int
    after: int
    longest: int
    extended: bool  # this completion added a new streak day


class DailyGoalChange(DailyGoal):
    just_completed: bool  # this completion crossed the goal


class CompletionRewards(_Out):
    """Everything a successful lesson completion earned, for the celebration screens."""

    first_completion: bool
    xp_awarded: int  # 10 for a first completion, 0 for a replay
    xp_total: int
    streak: StreakChange
    daily_goal: DailyGoalChange
    new_achievements: list[AchievementBadge]


# --------------------------------------------------------------------------- /me


class AchievementProgress(AchievementBadge):
    unlocked: bool
    unlocked_at: datetime | None
    current: int  # learner's current value for the metric
    target: int  # threshold


class HeartInfo(_Out):
    """Effective hearts at the time of the response (regeneration already applied)."""

    current: int
    max: int
    regenerating: bool  # true while below max
    seconds_until_next: int | None  # countdown to the next heart; null when full
    refill_cost_gems: int


class HeartRefillResponse(_Out):
    refilled: bool  # false when hearts were already full (no-op, nothing charged)
    gems_spent: int
    gems: int  # balance after the refill
    hearts: HeartInfo


class LessonStats(_Out):
    lessons_completed: int
    total_lessons: int
    skills_completed: int
    total_skills: int
    perfect_lessons: int  # lessons whose best attempt had no mistakes


class MeResponse(_Out):
    username: str
    display_name: str
    avatar_color: str
    today: date  # the learner's local date that "today" refers to
    xp_total: int
    streak: StreakInfo
    hearts: HeartInfo
    gems: int
    daily_goal: DailyGoal
    stats: LessonStats
    achievements: list[AchievementProgress]


# --------------------------------------------------------------------------- leaderboard


class LeaderboardEntry(_Out):
    rank: int
    username: str
    display_name: str
    avatar_color: str
    xp: int
    is_current_user: bool


class LeaderboardResponse(_Out):
    entries: list[LeaderboardEntry]
    current_user_rank: int | None

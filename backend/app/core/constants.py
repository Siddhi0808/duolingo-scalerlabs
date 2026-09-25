"""Game-rule constants in one place, so every number is tunable and explainable.

M1 only uses the values the schema needs (defaults and CHECK bounds). XP amounts,
regeneration interval and gem prices are added with the services that use them.
"""

MAX_HEARTS = 5
STARTING_GEMS = 500
DEFAULT_DAILY_GOAL_XP = 20
DAILY_GOAL_OPTIONS = (10, 20, 30, 50)  # Casual, Regular, Serious, Intense
DEFAULT_TIMEZONE = "Asia/Kolkata"

# XP: every first successful completion of a lesson earns exactly this much.
# Replaying an already-completed lesson earns nothing (and so does not extend streaks).
LESSON_XP = 10

# Hearts: refill to full for this many (mock) gems. Regeneration interval is a setting
# (HEART_REGEN_MINUTES) so demos can shorten it.
HEART_REFILL_GEM_COST = 350

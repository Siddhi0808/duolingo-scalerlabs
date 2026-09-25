/**
 * Strict TypeScript types matching the FastAPI backend schemas.
 * No types or fields are invented; they match backend Pydantic models.
 */

export type NodeState = "locked" | "available" | "in_progress" | "completed";
export type LessonState = "locked" | "available" | "completed";
export type ExerciseType =
  | "multiple_choice"
  | "word_bank"
  | "matching_pairs"
  | "fill_blank"
  | "type_answer";
export type SessionStatus = "active" | "completed" | "failed" | "abandoned";
export type SessionMode = "lesson" | "practice";

export interface Progress {
  completed: number;
  total: number;
  percent: number;
}

export interface LessonNode {
  id: number;
  position: number;
  title: string;
  state: LessonState;
}

export interface SkillNode {
  id: number;
  position: number;
  title: string;
  description: string;
  icon: string;
  state: NodeState;
  progress: Progress;
  next_lesson_id: number | null;
  is_current: boolean;
  lessons: LessonNode[];
}

export interface UnitNode {
  id: number;
  position: number;
  title: string;
  description: string;
  color: string;
  state: NodeState;
  progress: Progress;
  completed_skills: number;
  total_skills: number;
  skills: SkillNode[];
}

export interface CourseInfo {
  id: number;
  slug: string;
  title: string;
  learning_language: string;
  from_language: string;
}

export interface PathResponse {
  course: CourseInfo;
  progress: Progress;
  current_skill_id: number | null;
  current_lesson_id: number | null;
  units: UnitNode[];
}

// --------------------------------------------------------------------------- Exercise Payloads

export interface Choice {
  id: string;
  text: string;
  image?: string | null;
}

export interface Tile {
  id: string;
  text: string;
}

export interface MultipleChoicePayload {
  options: Choice[];
}

export interface WordBankPayload {
  source_text: string;
  tiles: Tile[];
}

export interface MatchingPairsPayload {
  left: Tile[];
  right: Tile[];
}

export interface FillBlankPayload {
  before: string;
  after: string;
  options: Choice[];
  hint?: string | null;
}

export interface TypeAnswerPayload {
  source_text: string;
  answer_language: "es" | "en";
}

export type ExercisePayload =
  | MultipleChoicePayload
  | WordBankPayload
  | MatchingPairsPayload
  | FillBlankPayload
  | TypeAnswerPayload;

interface PublicExerciseBase {
  id: number;
  position: number;
  prompt: string;
}

export type PublicExercise =
  | (PublicExerciseBase & { type: "multiple_choice"; payload: MultipleChoicePayload })
  | (PublicExerciseBase & { type: "word_bank"; payload: WordBankPayload })
  | (PublicExerciseBase & { type: "matching_pairs"; payload: MatchingPairsPayload })
  | (PublicExerciseBase & { type: "fill_blank"; payload: FillBlankPayload })
  | (PublicExerciseBase & { type: "type_answer"; payload: TypeAnswerPayload });

// --------------------------------------------------------------------------- Exercise Answers

export interface MultipleChoiceAnswer {
  type: "multiple_choice";
  option_id: string;
}

export interface WordBankAnswer {
  type: "word_bank";
  tile_ids: string[];
}

export interface MatchingPairsAnswer {
  type: "matching_pairs";
  pairs: [string, string][];
}

export interface FillBlankAnswer {
  type: "fill_blank";
  text: string;
}

export interface TypeAnswerAnswer {
  type: "type_answer";
  text: string;
}

export type Answer =
  | MultipleChoiceAnswer
  | WordBankAnswer
  | MatchingPairsAnswer
  | FillBlankAnswer
  | TypeAnswerAnswer;

export interface AnswerRequest {
  exercise_id: number;
  answer: Answer;
}

// --------------------------------------------------------------------------- /me & Gamification

export interface StreakInfo {
  current: number;
  longest: number;
  extended_today: boolean;
  last_active_date: string | null;
}

export interface DailyGoal {
  goal_xp: number;
  today_xp: number;
  completed: boolean;
}

export interface AchievementBadge {
  code: string;
  title: string;
  description: string;
  icon: string;
  tier: number;
}

export interface AchievementProgress extends AchievementBadge {
  unlocked: boolean;
  unlocked_at: string | null;
  current: number;
  target: number;
}

export interface HeartInfo {
  current: number;
  max: number;
  regenerating: boolean;
  seconds_until_next: number | null;
  refill_cost_gems: number;
}

export interface LessonStats {
  lessons_completed: number;
  total_lessons: number;
  skills_completed: number;
  total_skills: number;
  perfect_lessons: number;
}

export interface MeResponse {
  username: string;
  display_name: string;
  avatar_color: string;
  today: string;
  xp_total: number;
  streak: StreakInfo;
  hearts: HeartInfo;
  gems: number;
  daily_goal: DailyGoal;
  stats: LessonStats;
  achievements: AchievementProgress[];
}

// --------------------------------------------------------------------------- Lesson Engine & Sessions

export interface LessonRef {
  id: number;
  title: string;
  skill_id: number;
  skill_title: string;
}

export interface SessionProgress {
  status: SessionStatus;
  total: number;
  answered: number;
  correct: number;
  incorrect: number;
}

export interface SessionState {
  session_id: string;
  mode: SessionMode;
  lesson: LessonRef | null;
  progress: SessionProgress;
  hearts: HeartInfo;
  current_exercise: PublicExercise | null;
}

export interface StartSessionResponse extends SessionState {
  resumed: boolean;
  abandoned_session_id: string | null;
}

export interface StreakChange {
  before: number;
  after: number;
  longest: number;
  extended: boolean;
}

export interface DailyGoalChange extends DailyGoal {
  just_completed: boolean;
}

export interface CompletionRewards {
  first_completion: boolean;
  xp_awarded: number;
  xp_total: number;
  streak: StreakChange;
  daily_goal: DailyGoalChange;
  new_achievements: AchievementBadge[];
}

export interface AnswerResult {
  exercise_id: number;
  correct: boolean;
  correct_answer: string;
  note: string | null;
  explanation: string | null;
  replayed: boolean;
  hearts: HeartInfo;
  progress: SessionProgress;
  failure_reason: "out_of_hearts" | null;
  rewards: CompletionRewards | null;
}

export interface HeartRefillResponse {
  refilled: boolean;
  gems_spent: number;
  gems: number;
  hearts: HeartInfo;
}

// --------------------------------------------------------------------------- Leaderboard

export interface LeaderboardEntry {
  rank: number;
  username: string;
  display_name: string;
  avatar_color: string;
  xp: number;
  is_current_user: boolean;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  current_user_rank: number | null;
}

// --------------------------------------------------------------------------- Errors

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}

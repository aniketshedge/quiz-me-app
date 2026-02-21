export type ResolveStatus = "ok" | "blocked" | "no_match" | "ambiguous" | "error";

export interface TopicCandidate {
  title: string;
  page_id: number;
  url: string;
  summary: string;
  image_url?: string | null;
  image_caption?: string | null;
}

export interface ResolveTopicResponse {
  status: ResolveStatus;
  message?: string;
  primary_candidate?: TopicCandidate;
  alternatives?: TopicCandidate[];
}

export interface QuizSource {
  wikipedia_title: string;
  wikipedia_url: string;
  page_id: number;
  extract_used: string;
  image_url?: string | null;
  image_caption?: string | null;
}

export interface OptionModel {
  id: string;
  text: string;
}

interface QuestionBase {
  id: string;
  type: "mcq_single" | "mcq_multi" | "short_text";
  stem: string;
  explanation: string;
}

export interface MCQSingleQuestion extends QuestionBase {
  type: "mcq_single";
  options: OptionModel[];
  correct_option_ids: string[];
  distractor_feedback: Record<string, string>;
}

export interface MCQMultiQuestion extends QuestionBase {
  type: "mcq_multi";
  options: OptionModel[];
  correct_option_ids: string[];
  distractor_feedback: Record<string, string>;
}

export interface ShortTextQuestion extends QuestionBase {
  type: "short_text";
  expected_answers: string[];
  grading_context: string;
}

export type QuestionModel = MCQSingleQuestion | MCQMultiQuestion | ShortTextQuestion;

export interface QuizModel {
  quiz_id: string;
  topic: string;
  source: QuizSource;
  questions: QuestionModel[];
}

export interface CreateQuizResponse {
  session_id: string;
  quiz: QuizModel;
  source: QuizSource;
  provider?: string;
}

export interface AnswerSubmissionResponse {
  status: "accepted" | "locked" | "invalid" | "error";
  attempts_used: number;
  attempts_remaining: number;
  is_correct: boolean;
  locked: boolean;
  feedback: string;
}

export interface AnswerState {
  question_id: string;
  attempts_used: number;
  attempts_remaining: number;
  is_correct: boolean;
  locked: boolean;
  selected_option_ids?: string[];
  short_answer?: string;
  feedback?: string;
}

export interface SessionStateResponse {
  session_id: string;
  score: number;
  total_questions: number;
  current_index: number;
  answers: Record<string, AnswerState>;
  quiz: QuizModel;
}

export interface HealthResponse {
  status: "ok" | "error";
  mock_mode?: boolean;
}

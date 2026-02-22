import { defineStore } from "pinia";
import { isAxiosError } from "axios";
import {
  createQuiz,
  fetchHealth,
  fetchState,
  resolveTopic,
  resetSession,
  submitAnswer
} from "../services/api";
import type {
  AnswerSubmissionResponse,
  QuestionModel,
  SessionStateResponse,
  TopicCandidate
} from "../types";

type AppStep = "topic" | "confirm" | "quiz" | "score";
const SESSION_STORAGE_KEY = "quiz-me-session-v1";

interface PopupState {
  visible: boolean;
  title: string;
  message: string;
}

interface QuizState {
  step: AppStep;
  topicInput: string;
  selectedTopic: string;
  resolving: boolean;
  loadingQuiz: boolean;
  checkingAnswer: boolean;
  mockMode: boolean;
  sessionId: string;
  provider: string;
  currentIndex: number;
  state: SessionStateResponse | null;
  primaryCandidate: TopicCandidate | null;
  alternatives: TopicCandidate[];
  selectedCandidate: TopicCandidate | null;
  rateLimitNotice: string;
  popup: PopupState;
}

function defaultPopup(): PopupState {
  return {
    visible: false,
    title: "",
    message: ""
  };
}

function extractRequestErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) {
    return fallback;
  }

  const responseData = error.response?.data as { message?: string; details?: string } | undefined;
  if (typeof responseData?.message === "string" && responseData.message.trim()) {
    return responseData.message.trim();
  }
  if (typeof responseData?.details === "string" && responseData.details.trim()) {
    return responseData.details.trim();
  }
  if (error.response?.status) {
    return `Request failed with status ${error.response.status}.`;
  }
  if (error.code === "ECONNABORTED") {
    return "Request timed out while reaching the API.";
  }
  return error.message || fallback;
}

interface PersistedSessionState {
  sessionId: string;
  currentIndex: number;
  step: "quiz" | "score";
  selectedTopic: string;
  provider: string;
}

export const useQuizStore = defineStore("quiz", {
  state: (): QuizState => ({
    step: "topic",
    topicInput: "",
    selectedTopic: "",
    resolving: false,
    loadingQuiz: false,
    checkingAnswer: false,
    mockMode: false,
    sessionId: "",
    provider: "",
    currentIndex: 0,
    state: null,
    primaryCandidate: null,
    alternatives: [],
    selectedCandidate: null,
    rateLimitNotice: "",
    popup: defaultPopup()
  }),
  getters: {
    quiz(state): SessionStateResponse["quiz"] | null {
      return state.state?.quiz || null;
    },
    currentQuestion(state): QuestionModel | null {
      if (!state.state?.quiz?.questions?.length) {
        return null;
      }
      return state.state.quiz.questions[state.currentIndex] || null;
    },
    score(state): number {
      return state.state?.score || 0;
    },
    totalQuestions(state): number {
      return state.state?.total_questions || 15;
    },
    allLocked(state): boolean {
      if (!state.state) {
        return false;
      }
      return Object.values(state.state.answers).every((answer) => answer.locked);
    }
  },
  actions: {
    persistSessionState() {
      if (typeof window === "undefined") {
        return;
      }

      if (!this.sessionId || !this.state) {
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
        return;
      }

      const payload: PersistedSessionState = {
        sessionId: this.sessionId,
        currentIndex: this.currentIndex,
        step: this.step === "score" ? "score" : "quiz",
        selectedTopic: this.selectedTopic,
        provider: this.provider
      };
      window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(payload));
    },

    clearPersistedSessionState() {
      if (typeof window === "undefined") {
        return;
      }
      window.localStorage.removeItem(SESSION_STORAGE_KEY);
    },

    async restoreSessionFromStorage() {
      if (typeof window === "undefined") {
        return;
      }

      const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (!raw) {
        return;
      }

      let saved: PersistedSessionState | null = null;
      try {
        saved = JSON.parse(raw) as PersistedSessionState;
      } catch (_error) {
        this.clearPersistedSessionState();
        return;
      }

      if (!saved?.sessionId) {
        this.clearPersistedSessionState();
        return;
      }

      this.sessionId = saved.sessionId;
      this.selectedTopic = saved.selectedTopic || "";
      this.provider = saved.provider || "";

      try {
        const state = await fetchState(saved.sessionId);
        this.state = state;
        const total = state.total_questions || 15;
        this.currentIndex = Math.min(
          Math.max(0, saved.currentIndex || 0),
          Math.max(0, total - 1)
        );
        if (this.allLocked || saved.step === "score") {
          this.step = "score";
        } else {
          this.step = "quiz";
        }
        this.persistSessionState();
      } catch (_error) {
        this.sessionId = "";
        this.provider = "";
        this.currentIndex = 0;
        this.state = null;
        this.clearPersistedSessionState();
      }
    },

    showPopup(title: string, message: string) {
      this.popup = {
        visible: true,
        title,
        message
      };
    },
    closePopup() {
      this.popup = defaultPopup();
    },

    setRateLimitNotice(message?: string) {
      const text = (message || "").trim();
      this.rateLimitNotice =
        text || "Rate limit reached. Please try again later. The app may switch to sample data mode.";
    },

    async initialize() {
      try {
        const health = await fetchHealth();
        this.mockMode = Boolean(health.mock_mode);
      } catch (_error) {
        this.mockMode = false;
      }
      await this.restoreSessionFromStorage();
    },

    async resolveTopic() {
      const topic = this.topicInput.trim();
      if (!topic) {
        this.showPopup("Topic required", "Enter a topic to begin.");
        return;
      }

      this.resolving = true;
      this.selectedCandidate = null;
      this.primaryCandidate = null;
      this.alternatives = [];

      try {
        const data = await resolveTopic(topic);
        this.selectedTopic = topic;

        if (data.status === "blocked") {
          this.showPopup(
            "Try another topic",
            data.message || "This topic cannot be used right now."
          );
          this.step = "topic";
          return;
        }

        if (data.status === "no_match") {
          this.showPopup(
            "No matching article",
            data.message || "Could not find a matching Wikipedia article."
          );
          this.step = "topic";
          return;
        }

        if (data.status === "error") {
          this.showPopup(
            "Lookup failed",
            data.message || "Something went wrong. Try another topic."
          );
          this.step = "topic";
          return;
        }

        this.primaryCandidate = data.primary_candidate || null;
        this.alternatives = data.alternatives || [];
        this.selectedCandidate = this.primaryCandidate;
        this.step = "confirm";

        if (data.status === "ambiguous") {
          this.showPopup(
            "Topic is ambiguous",
            data.message || "Pick a specific article from alternatives."
          );
        }
      } catch (error) {
        this.showPopup(
          "Lookup failed",
          extractRequestErrorMessage(error, "Could not resolve topic. Try again.")
        );
      } finally {
        this.resolving = false;
      }
    },

    pickCandidate(candidate: TopicCandidate) {
      this.selectedCandidate = candidate;
    },

    async usePrimaryArticle() {
      if (!this.primaryCandidate) {
        this.showPopup("Select article", "No primary article is available.");
        return;
      }
      this.selectedCandidate = this.primaryCandidate;
      await this.createQuiz();
    },

    async createQuiz() {
      if (!this.selectedCandidate) {
        this.showPopup("Select article", "Choose an article to generate quiz.");
        return;
      }

      this.loadingQuiz = true;
      try {
        const response = await createQuiz(this.selectedTopic, this.selectedCandidate.page_id);
        this.sessionId = response.session_id;
        this.provider = response.provider || "unknown";
        await this.syncState();
        this.step = "quiz";
        this.persistSessionState();
      } catch (error) {
        if (isAxiosError(error) && error.response?.status === 429) {
          this.setRateLimitNotice(
            extractRequestErrorMessage(
              error,
              "Rate limit reached for quiz creation. Please try again later."
            )
          );
        }
        this.showPopup(
          "Quiz generation failed",
          extractRequestErrorMessage(error, "Could not generate quiz after retries. Try another topic.")
        );
      } finally {
        this.loadingQuiz = false;
      }
    },

    async syncState(options?: { preserveIndex?: boolean }) {
      if (!this.sessionId) {
        return;
      }
      const state = await fetchState(this.sessionId);
      this.state = state;
      const total = state.total_questions || 15;
      if (options?.preserveIndex) {
        this.currentIndex = Math.min(this.currentIndex, Math.max(0, total - 1));
      } else {
        this.currentIndex = Math.min(state.current_index, Math.max(0, total - 1));
      }
      if (this.allLocked) {
        this.step = "score";
      }
      this.persistSessionState();
    },

    async submitCurrentAnswer(payload: {
      selected_option_ids?: string[];
      short_answer?: string;
    }): Promise<AnswerSubmissionResponse | null> {
      const question = this.currentQuestion;
      if (!question || !this.sessionId) {
        return null;
      }

      this.checkingAnswer = true;
      try {
        const result: AnswerSubmissionResponse = await submitAnswer(this.sessionId, {
          question_id: question.id,
          ...payload
        });
        await this.syncState({ preserveIndex: true });

        if (result.status === "invalid") {
          this.showPopup("Invalid response", result.feedback);
          return result;
        }

        if (result.status === "locked") {
          this.showPopup("Question locked", result.feedback);
          return result;
        }
        return result;
      } catch (_error) {
        this.showPopup("Check failed", "Unable to check answer at the moment.");
        return null;
      } finally {
        this.checkingAnswer = false;
      }
    },

    async nextFromQuiz(payload: { selected_option_ids?: string[]; short_answer?: string }) {
      const question = this.currentQuestion;
      if (!question) {
        return;
      }

      const total = this.state?.total_questions || 15;
      const advance = () => {
        if (this.currentIndex >= total - 1) {
          this.step = "score";
          this.persistSessionState();
          return;
        }
        this.currentIndex = Math.min(total - 1, this.currentIndex + 1);
        this.persistSessionState();
      };

      const answer = this.state?.answers?.[question.id];
      if (answer?.locked) {
        advance();
        return;
      }

      const hasPriorCheckedFeedback = Boolean(answer?.feedback) && (answer?.attempts_used || 0) > 0;
      if (hasPriorCheckedFeedback) {
        advance();
        return;
      }

      const hasDraftInput =
        question.type === "short_text"
          ? Boolean(payload.short_answer && payload.short_answer.trim().length > 0)
          : Boolean(payload.selected_option_ids && payload.selected_option_ids.length > 0);

      if (!hasDraftInput) {
        advance();
        return;
      }

      const result = await this.submitCurrentAnswer(
        question.type === "short_text"
          ? { short_answer: (payload.short_answer || "").trim() }
          : { selected_option_ids: payload.selected_option_ids || [] }
      );
      if (!result) {
        return;
      }

      if (result.status === "accepted" && result.is_correct) {
        advance();
      }
    },

    prevQuestion() {
      this.currentIndex = Math.max(0, this.currentIndex - 1);
      this.persistSessionState();
    },

    nextQuestion() {
      const total = this.state?.total_questions || 15;
      if (this.currentIndex >= total - 1) {
        this.step = "score";
        this.persistSessionState();
        return;
      }
      this.currentIndex = Math.min(total - 1, this.currentIndex + 1);
      this.persistSessionState();
    },

    async restart() {
      if (this.sessionId) {
        try {
          await resetSession(this.sessionId);
        } catch (_error) {
          // Non-blocking for session-only experience.
        }
      }

      this.step = "topic";
      this.topicInput = "";
      this.selectedTopic = "";
      this.resolving = false;
      this.loadingQuiz = false;
      this.checkingAnswer = false;
      // Keep mock-mode banner state from runtime health check.
      this.sessionId = "";
      this.provider = "";
      this.currentIndex = 0;
      this.state = null;
      this.primaryCandidate = null;
      this.alternatives = [];
      this.selectedCandidate = null;
      this.popup = defaultPopup();
      this.clearPersistedSessionState();
    }
  }
});

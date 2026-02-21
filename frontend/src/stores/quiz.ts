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
    correctCount(state): number {
      return state.state?.correct_count || 0;
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

    async initialize() {
      try {
        const health = await fetchHealth();
        this.mockMode = Boolean(health.mock_mode);
      } catch (_error) {
        this.mockMode = false;
      }
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
      } catch (error) {
        this.showPopup(
          "Quiz generation failed",
          extractRequestErrorMessage(error, "Could not generate quiz after retries. Try another topic.")
        );
      } finally {
        this.loadingQuiz = false;
      }
    },

    async syncState() {
      if (!this.sessionId) {
        return;
      }
      const state = await fetchState(this.sessionId);
      this.state = state;
      this.currentIndex = state.current_index;
      if (this.allLocked) {
        this.step = "score";
      }
    },

    async submitCurrentAnswer(payload: { selected_option_ids?: string[]; short_answer?: string }) {
      const question = this.currentQuestion;
      if (!question || !this.sessionId) {
        return;
      }

      this.checkingAnswer = true;
      try {
        const result: AnswerSubmissionResponse = await submitAnswer(this.sessionId, {
          question_id: question.id,
          ...payload
        });
        await this.syncState();

        if (result.status === "invalid") {
          this.showPopup("Invalid response", result.feedback);
          return;
        }

        if (result.status === "locked") {
          this.showPopup("Question locked", result.feedback);
          return;
        }
      } catch (_error) {
        this.showPopup("Check failed", "Unable to check answer at the moment.");
      } finally {
        this.checkingAnswer = false;
      }
    },

    prevQuestion() {
      this.currentIndex = Math.max(0, this.currentIndex - 1);
    },

    nextQuestion() {
      const total = this.state?.total_questions || 15;
      this.currentIndex = Math.min(total - 1, this.currentIndex + 1);
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
    }
  }
});

import axios from "axios";
import type {
  AnswerSubmissionResponse,
  CreateQuizResponse,
  ResolveTopicResponse,
  SessionStateResponse
} from "../types";

function trimSlashes(value: string): string {
  return value.replace(/\/+$/, "").replace(/^\/+/, "");
}

function buildApiBase(): string {
  const basePath = import.meta.env.VITE_APP_BASE_PATH || "";
  const normalized = trimSlashes(basePath);
  return normalized ? `/${normalized}/api` : "/api";
}

const client = axios.create({
  baseURL: buildApiBase(),
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS || 15000)
});

export async function resolveTopic(topic: string): Promise<ResolveTopicResponse> {
  const { data } = await client.post<ResolveTopicResponse>("/topic/resolve", { topic });
  return data;
}

export async function createQuiz(topic: string, selected_page_id: number): Promise<CreateQuizResponse> {
  const { data } = await client.post<CreateQuizResponse>("/quiz/create", {
    topic,
    selected_page_id
  });
  return data;
}

export async function submitAnswer(
  sessionId: string,
  payload: { question_id: string; selected_option_ids?: string[]; short_answer?: string }
): Promise<AnswerSubmissionResponse> {
  const { data } = await client.post<AnswerSubmissionResponse>(`/quiz/${sessionId}/answer`, payload);
  return data;
}

export async function fetchState(sessionId: string): Promise<SessionStateResponse> {
  const { data } = await client.get<SessionStateResponse>(`/quiz/${sessionId}/state`);
  return data;
}

export async function resetSession(sessionId: string): Promise<void> {
  await client.post(`/quiz/${sessionId}/reset`);
}

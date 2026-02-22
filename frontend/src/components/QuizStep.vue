<template>
  <div class="quiz-stage" v-if="quiz && question">
    <h2 class="quiz-stage-title">{{ quizTitle }}</h2>
    <section class="quiz-shell">
      <header class="quiz-header">
        <p class="eyebrow">Question {{ currentIndex + 1 }} of {{ totalQuestions }}</p>
        <h3 class="question-stem">{{ question.stem }}</h3>
      </header>

      <transition mode="out-in" @enter="onEnter" @leave="onLeave">
        <article :key="question.id" class="question-card">
          <div v-if="question.type === 'mcq_single' || question.type === 'mcq_multi'" class="options">
            <label
              v-for="(option, optionIndex) in question.options"
              :key="option.id"
              class="option-item"
              :class="{
                locked: answerState?.locked,
                selected: isSelected(option.id)
              }"
            >
              <input
                class="option-input"
                :type="question.type === 'mcq_single' ? 'radio' : 'checkbox'"
                :name="question.id"
                :value="option.id"
                :checked="isSelected(option.id)"
                :disabled="answerState?.locked"
                @change="toggleOption(option.id, question.type === 'mcq_single')"
              />
              <span class="option-marker" aria-hidden="true">{{ optionLetter(optionIndex) }}</span>
              <span class="option-card">
                <span class="option-text">{{ option.text }}</span>
              </span>
            </label>
          </div>

          <div v-else class="short-answer-wrap">
            <input
              class="text-input"
              type="text"
              maxlength="120"
              :disabled="answerState?.locked"
              v-model="shortAnswer"
              placeholder="Type a short answer (1-5 words)"
            />
          </div>

          <div class="meta-row">
            <span>Attempts: {{ answerState?.attempts_used || 0 }} / 3</span>
            <span v-if="answerState?.locked">Locked</span>
          </div>

          <p v-if="answerState?.feedback" class="feedback" :class="{ correct: answerState?.is_correct }">
            {{ answerState?.feedback }}
          </p>
        </article>
      </transition>

      <footer class="actions">
        <button type="button" class="btn" :disabled="currentIndex === 0" @click="$emit('prev')">Back</button>
        <button type="button" class="btn btn-primary" :disabled="!canCheck" @click="checkAnswer">
          {{ checkingAnswer ? "Checking..." : "Check" }}
        </button>
        <button type="button" class="btn" :disabled="currentIndex >= totalQuestions - 1" @click="$emit('next')">
          Next
        </button>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { gsap } from "gsap";
import type { AnswerState, QuestionModel, QuizModel } from "../types";

const props = defineProps<{
  quiz: QuizModel | null;
  answers: Record<string, AnswerState>;
  currentIndex: number;
  totalQuestions: number;
  checkingAnswer: boolean;
}>();

const emit = defineEmits<{
  (event: "prev"): void;
  (event: "next"): void;
  (event: "check", payload: { selected_option_ids?: string[]; short_answer?: string }): void;
}>();

const selectedOptionIds = ref<string[]>([]);
const shortAnswer = ref("");

const question = computed<QuestionModel | null>(() => {
  if (!props.quiz) {
    return null;
  }
  return props.quiz.questions[props.currentIndex] || null;
});

const answerState = computed<AnswerState | null>(() => {
  const current = question.value;
  if (!current) {
    return null;
  }
  return props.answers[current.id] || null;
});

const quizTitle = computed(() => {
  const rawTitle = props.quiz?.source?.wikipedia_title || props.quiz?.topic || "Quiz";
  const formatted = rawTitle
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
  return `${formatted} Quiz`;
});

watch(
  () => question.value?.id,
  () => {
    const state = answerState.value;
    selectedOptionIds.value = state?.selected_option_ids ? [...state.selected_option_ids] : [];
    shortAnswer.value = state?.short_answer || "";
  },
  { immediate: true }
);

const canCheck = computed(() => {
  if (!question.value || props.checkingAnswer || answerState.value?.locked) {
    return false;
  }
  if (question.value.type === "short_text") {
    return shortAnswer.value.trim().length > 0;
  }
  return selectedOptionIds.value.length > 0;
});

function isSelected(optionId: string): boolean {
  return selectedOptionIds.value.includes(optionId);
}

function optionLetter(index: number): string {
  return String.fromCharCode(65 + index);
}

function toggleOption(optionId: string, single: boolean): void {
  if (answerState.value?.locked) {
    return;
  }
  if (single) {
    selectedOptionIds.value = [optionId];
    return;
  }

  const set = new Set(selectedOptionIds.value);
  if (set.has(optionId)) {
    set.delete(optionId);
  } else {
    set.add(optionId);
  }
  selectedOptionIds.value = Array.from(set);
}

function checkAnswer(): void {
  if (!question.value) {
    return;
  }
  if (question.value.type === "short_text") {
    emit("check", { short_answer: shortAnswer.value.trim() });
    return;
  }
  emit("check", { selected_option_ids: selectedOptionIds.value });
}

function onEnter(el: Element, done: () => void): void {
  gsap.fromTo(
    el,
    { opacity: 0, x: 24 },
    { opacity: 1, x: 0, duration: 0.28, ease: "power2.out", onComplete: done }
  );
}

function onLeave(el: Element, done: () => void): void {
  gsap.to(el, {
    opacity: 0,
    x: -24,
    duration: 0.2,
    ease: "power1.in",
    onComplete: done
  });
}
</script>

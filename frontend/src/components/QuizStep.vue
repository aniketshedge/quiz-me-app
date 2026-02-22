<template>
  <section class="quiz-shell quiz-stage" v-if="quiz && question">
      <div class="panel-toolbar panel-toolbar-quiz">
        <h2 class="quiz-stage-title">{{ quizTitle }}</h2>
        <slot name="top-right" />
      </div>
      <header class="quiz-header">
        <p class="eyebrow">Question {{ currentIndex + 1 }} of {{ totalQuestions }}</p>
        <AnimatePresence mode="wait">
          <motion.h3
            :key="`stem-${question.id}`"
            class="question-stem"
            :initial="stemInitial"
            :animate="stemAnimate"
            :exit="stemExit"
            :transition="stemTransition"
          >
            {{ question.stem }}
          </motion.h3>
        </AnimatePresence>
      </header>

      <AnimatePresence mode="wait">
        <motion.article
          :key="question.id"
          class="question-card"
          layout
          :initial="cardInitial"
          :animate="cardAnimate"
          :exit="cardExit"
          :transition="cardTransition"
        >
          <div v-if="question.type === 'mcq_single' || question.type === 'mcq_multi'" class="options">
            <motion.label
              v-for="(option, optionIndex) in question.options"
              :key="option.id"
              class="option-item"
              :class="{
                locked: answerState?.locked,
                selected: isSelected(option.id)
              }"
              :initial="optionInitial"
              :animate="optionAnimate"
              :transition="optionTransition(optionIndex)"
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
            </motion.label>
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

          <AnimatePresence>
            <motion.p
              v-if="answerState?.feedback"
              :key="`fb-${question.id}-${answerState?.attempts_used}-${answerState?.is_correct ? 'c' : 'i'}`"
              class="feedback"
              :class="{ correct: answerState?.is_correct }"
              layout
              :initial="feedbackInitial"
              :animate="feedbackAnimate"
              :exit="feedbackExit"
              :transition="feedbackTransition"
            >
              {{ answerState?.feedback }}
            </motion.p>
          </AnimatePresence>
        </motion.article>
      </AnimatePresence>

      <footer class="actions">
        <button type="button" class="btn" :disabled="currentIndex === 0" @click="$emit('prev')">Back</button>
        <button type="button" class="btn btn-primary" :disabled="!canCheck" @click="checkAnswer">
          {{ checkingAnswer ? "Checking..." : "Check" }}
        </button>
        <button type="button" class="btn" :disabled="checkingAnswer" @click="$emit('next')">
          {{ isLastQuestion ? "Finish" : "Next" }}
        </button>
      </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { AnimatePresence, motion, useReducedMotion } from "motion-v";
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
const direction = ref(1);
const prefersReducedMotion = useReducedMotion();
const reducedMotion = computed(() => Boolean(prefersReducedMotion.value));

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

watch(
  () => props.currentIndex,
  (next, prev) => {
    if (typeof prev !== "number") {
      return;
    }
    direction.value = next >= prev ? 1 : -1;
  }
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

const isLastQuestion = computed(() => props.currentIndex >= props.totalQuestions - 1);

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

const cardInitial = computed(() =>
  reducedMotion.value
    ? { opacity: 0 }
    : { opacity: 0, x: direction.value > 0 ? 32 : -32, scale: 0.995 }
);
const cardAnimate = computed(() => ({ opacity: 1, x: 0, scale: 1 }));
const cardExit = computed(() =>
  reducedMotion.value
    ? { opacity: 0 }
    : { opacity: 0, x: direction.value > 0 ? -24 : 24, scale: 0.995 }
);
const cardTransition = computed(() =>
  reducedMotion.value
    ? { duration: 0.14 }
    : { duration: 0.28, ease: "easeOut" }
);

const stemInitial = computed(() =>
  reducedMotion.value ? { opacity: 0 } : { opacity: 0, x: direction.value > 0 ? 14 : -14 }
);
const stemAnimate = { opacity: 1, x: 0 };
const stemExit = computed(() =>
  reducedMotion.value ? { opacity: 0 } : { opacity: 0, x: direction.value > 0 ? -16 : 16 }
);
const stemTransition = computed(() =>
  reducedMotion.value
    ? { duration: 0.12 }
    : { duration: 0.2, ease: "easeOut" }
);

const optionInitial = computed(() => (reducedMotion.value ? { opacity: 0 } : { opacity: 0, y: 10 }));
const optionAnimate = { opacity: 1, y: 0 };
function optionTransition(index: number): { duration: number; delay: number; ease?: string } {
  if (reducedMotion.value) {
    return { duration: 0.12, delay: 0 };
  }
  return {
    duration: 0.22,
    delay: 0.04 * index,
    ease: "easeOut"
  };
}

const feedbackInitial = computed(() => (reducedMotion.value ? { opacity: 0 } : { opacity: 0, y: 6 }));
const feedbackAnimate = { opacity: 1, y: 0 };
const feedbackExit = computed(() => (reducedMotion.value ? { opacity: 0 } : { opacity: 0, y: -4 }));
const feedbackTransition = computed(() =>
  reducedMotion.value
    ? { duration: 0.12 }
    : { duration: 0.2, ease: "easeOut" }
);
</script>

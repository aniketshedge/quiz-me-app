<template>
  <main class="app-shell">
    <div class="ambient ambient-a"></div>
    <div class="ambient ambient-b"></div>

    <transition mode="out-in" name="step-fade">
      <TopicStep
        v-if="store.step === 'topic'"
        :model-value="store.topicInput"
        :resolving="store.resolving"
        @update:model-value="store.topicInput = $event"
        @submit="store.resolveTopic"
      />

      <ArticleConfirmStep
        v-else-if="store.step === 'confirm'"
        :primary="store.primaryCandidate"
        :alternatives="store.alternatives"
        :selected="store.selectedCandidate"
        :loading="store.loadingQuiz"
        @select="store.pickCandidate"
        @back="store.restart"
        @create="store.createQuiz"
      />

      <QuizStep
        v-else-if="store.step === 'quiz'"
        :quiz="store.quiz"
        :answers="store.state?.answers || {}"
        :current-index="store.currentIndex"
        :correct-count="store.correctCount"
        :total-questions="store.totalQuestions"
        :checking-answer="store.checkingAnswer"
        @prev="store.prevQuestion"
        @next="store.nextQuestion"
        @check="store.submitCurrentAnswer"
      />

      <ScoreStep
        v-else
        :score="store.score"
        :total="store.totalQuestions"
        @restart="store.restart"
      />
    </transition>

    <p v-if="store.provider && store.step === 'quiz'" class="provider-note">
      Generation provider: {{ store.provider }}
    </p>

    <PopupModal
      :visible="store.popup.visible"
      :title="store.popup.title"
      :message="store.popup.message"
      @close="store.closePopup"
    />
  </main>
</template>

<script setup lang="ts">
import { useQuizStore } from "./stores/quiz";
import TopicStep from "./components/TopicStep.vue";
import ArticleConfirmStep from "./components/ArticleConfirmStep.vue";
import QuizStep from "./components/QuizStep.vue";
import ScoreStep from "./components/ScoreStep.vue";
import PopupModal from "./components/PopupModal.vue";

const store = useQuizStore();
</script>

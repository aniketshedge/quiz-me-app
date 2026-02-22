<template>
  <main class="app-shell">
    <AppBackground />

    <div class="app-content">
      <transition mode="out-in" name="step-fade">
        <TopicStep
          v-if="store.step === 'topic'"
          :model-value="store.topicInput"
          :resolving="store.resolving"
          :mock-mode="store.mockMode"
          :rate-limit-notice="store.rateLimitNotice"
          @update:model-value="store.topicInput = $event"
          @submit="store.resolveTopic"
        >
          <template #top-right>
            <ThemeToggle :is-night="isNight" @toggle="toggleTheme" />
          </template>
        </TopicStep>

        <ArticleConfirmStep
          v-else-if="store.step === 'confirm'"
          :primary="store.primaryCandidate"
          :alternatives="store.alternatives"
          :selected="store.selectedCandidate"
          :loading="store.loadingQuiz"
          @select="store.pickCandidate"
          @use-primary="store.usePrimaryArticle"
          @back="store.restart"
          @create="store.createQuiz"
        >
          <template #top-right>
            <ThemeToggle :is-night="isNight" @toggle="toggleTheme" />
          </template>
        </ArticleConfirmStep>

        <QuizStep
          v-else-if="store.step === 'quiz'"
          :quiz="store.quiz"
          :answers="store.state?.answers || {}"
          :current-index="store.currentIndex"
          :total-questions="store.totalQuestions"
          :checking-answer="store.checkingAnswer"
          @prev="store.prevQuestion"
          @next="store.nextFromQuiz"
          @check="store.submitCurrentAnswer"
        >
          <template #top-right>
            <ThemeToggle :is-night="isNight" @toggle="toggleTheme" />
          </template>
        </QuizStep>

        <ScoreStep
          v-else
          :score="store.score"
          :total="store.totalQuestions"
          @restart="store.restart"
        >
          <template #top-right>
            <ThemeToggle :is-night="isNight" @toggle="toggleTheme" />
          </template>
        </ScoreStep>
      </transition>
    </div>

    <p v-if="store.rateLimitNotice" class="global-warning" role="status" aria-live="polite">
      {{ store.rateLimitNotice }}
    </p>

    <footer class="app-footer">
      <p class="footer-copy">Created and hosted by Aniket Shedge</p>
      <button type="button" class="footer-link" @click="legalVisible = true">Disclaimers and terms</button>
    </footer>

    <PopupModal
      :visible="store.popup.visible"
      :title="store.popup.title"
      :message="store.popup.message"
      @close="store.closePopup"
    />

    <div v-if="legalVisible" class="popup-overlay" @click.self="legalVisible = false">
      <div class="popup-card legal-card" role="dialog" aria-modal="true" aria-label="Disclaimers and terms">
        <h3>Disclaimers and terms</h3>
        <p>
          This hobby project was initially built for self-learning. It is not a production-grade managed
          service.
        </p>
        <p>
          Created using OpenAI GPT-5.3 Codex. Outputs can be imperfect, incomplete, or unsuitable for your
          use case. No guarantees of any kind are provided.
        </p>
        <h4>Terms of use</h4>
        <ul class="legal-list">
          <li>Use this app for learning and demo purposes only.</li>
          <li>Do not rely on quiz outputs for high-stakes academic, legal, medical, or financial decisions.</li>
          <li>Do not submit personal, sensitive, or confidential information.</li>
          <li>You are responsible for verifying content correctness before any external use.</li>
          <li>Service behavior, availability, and features may change at any time without notice.</li>
          <li>
            Output quality depends on AI model responses, and this service may use different models at different
            times.
          </li>
          <li>This service may not work when upstream AI services are unavailable.</li>
          <li>This service may be rate limited.</li>
        </ul>
        <div class="actions legal-actions">
          <button type="button" class="btn btn-primary" @click="legalVisible = false">Close</button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useQuizStore } from "./stores/quiz";
import TopicStep from "./components/TopicStep.vue";
import ArticleConfirmStep from "./components/ArticleConfirmStep.vue";
import QuizStep from "./components/QuizStep.vue";
import ScoreStep from "./components/ScoreStep.vue";
import PopupModal from "./components/PopupModal.vue";
import AppBackground from "./components/AppBackground.vue";
import ThemeToggle from "./components/ThemeToggle.vue";

const store = useQuizStore();
const legalVisible = ref(false);
const isNight = ref(false);
const supportedThemes = new Set(["day", "night"]);

function applyTheme(theme: "day" | "night"): void {
  const root = document.documentElement;
  if (theme === "night") {
    root.setAttribute("data-theme", "night");
    isNight.value = true;
  } else {
    root.removeAttribute("data-theme");
    isNight.value = false;
  }
}

function getTimeBasedTheme(): "day" | "night" {
  const hour = new Date().getHours();
  return hour >= 18 || hour < 6 ? "night" : "day";
}

function applyThemeFromRuntime(): void {
  const params = new URLSearchParams(window.location.search);
  const themeFromUrl = params.get("theme")?.trim().toLowerCase();
  const chosen = supportedThemes.has(themeFromUrl || "")
    ? (themeFromUrl as "day" | "night")
    : getTimeBasedTheme();

  applyTheme(chosen);
}

function toggleTheme(): void {
  applyTheme(isNight.value ? "day" : "night");
}

onMounted(() => {
  applyThemeFromRuntime();
  void store.initialize();
});
</script>

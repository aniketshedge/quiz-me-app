<template>
  <motion.section class="panel score-panel" :initial="panelInitial" :animate="panelAnimate" :transition="panelTransition">
    <h2>Quiz complete!</h2>
    <motion.p class="score-value" :initial="scoreInitial" :animate="scoreAnimate" :transition="scoreTransition">
      {{ displayedScore }} / {{ total }}
    </motion.p>
    <button type="button" class="btn btn-primary" @click="$emit('restart')">Try another topic</button>
  </motion.section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { motion, useReducedMotion } from "motion-v";

const props = defineProps<{
  score: number;
  total: number;
}>();

defineEmits<{
  (event: "restart"): void;
}>();

const prefersReducedMotion = useReducedMotion();
const reducedMotion = computed(() => Boolean(prefersReducedMotion.value));

const displayedScore = ref(0);
let rafId: number | null = null;

function stopCountAnimation(): void {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function animateScore(targetScore: number): void {
  stopCountAnimation();
  const boundedTarget = Math.max(0, Math.floor(targetScore));
  const startValue = boundedTarget > 0 ? 1 : 0;
  displayedScore.value = startValue;

  if (boundedTarget <= startValue || reducedMotion.value) {
    displayedScore.value = boundedTarget;
    return;
  }

  const durationMs = 1200;
  const startTs = performance.now();

  const tick = (now: number) => {
    const t = Math.min(1, (now - startTs) / durationMs);
    const eased = 1 - Math.pow(1 - t, 3);
    displayedScore.value = Math.round(startValue + (boundedTarget - startValue) * eased);
    if (t < 1) {
      rafId = requestAnimationFrame(tick);
      return;
    }
    displayedScore.value = boundedTarget;
    rafId = null;
  };

  rafId = requestAnimationFrame(tick);
}

watch(
  () => props.score,
  (nextScore) => {
    animateScore(nextScore);
  },
  { immediate: true }
);

onBeforeUnmount(() => {
  stopCountAnimation();
});

const panelInitial = computed(() => (reducedMotion.value ? { opacity: 0 } : { opacity: 0, y: 14 }));
const panelAnimate = { opacity: 1, y: 0 };
const panelTransition = computed(() =>
  reducedMotion.value
    ? { duration: 0.12 }
    : { duration: 0.3, ease: "easeOut" }
);

const scoreInitial = computed(() => (reducedMotion.value ? { opacity: 0 } : { opacity: 0, scale: 0.96 }));
const scoreAnimate = { opacity: 1, scale: 1 };
const scoreTransition = computed(() =>
  reducedMotion.value
    ? { duration: 0.14 }
    : { duration: 0.32, ease: "easeOut", delay: 0.08 }
);
</script>

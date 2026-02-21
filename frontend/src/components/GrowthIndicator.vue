<template>
  <div class="growth-indicator" aria-hidden="true">
    <div class="growth-svg-wrap">
      <img v-if="currentSrc" ref="baseRef" class="growth-svg" :src="currentSrc" alt="" />
      <img v-if="overlaySrc" ref="overlayRef" class="growth-svg overlay" :src="overlaySrc" alt="" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { gsap } from "gsap";

const props = defineProps<{
  correctCount: number;
  totalQuestions: number;
}>();

const svgModules = import.meta.glob("../assets/plant/plant-state-*.svg", {
  eager: true,
  import: "default",
  query: "?url"
}) as Record<string, string>;

const stages = Object.entries(svgModules)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([, value]) => value);

const stageIndex = computed(() => {
  const max = Math.max(0, stages.length - 1);
  return Math.min(Math.max(props.correctCount, 0), max);
});

const initialStage = stages[0] ?? "";
const currentSrc = ref(initialStage);
const overlaySrc = ref(initialStage);
const baseRef = ref<HTMLImageElement | null>(null);
const overlayRef = ref<HTMLImageElement | null>(null);

watch(
  stageIndex,
  async (nextIndex) => {
    const nextSrc = stages[nextIndex];
    if (!nextSrc || nextSrc === currentSrc.value) {
      return;
    }

    overlaySrc.value = nextSrc;
    await nextTick();

    if (!overlayRef.value || !baseRef.value) {
      currentSrc.value = nextSrc;
      return;
    }

    gsap.set(overlayRef.value, { opacity: 0, scale: 0.98 });
    gsap.to(overlayRef.value, {
      opacity: 1,
      scale: 1,
      duration: 0.3,
      ease: "power2.out"
    });

    gsap.to(baseRef.value, {
      opacity: 0,
      duration: 0.25,
      ease: "power2.out",
      onComplete: () => {
        currentSrc.value = nextSrc;
        gsap.set(baseRef.value, { opacity: 1 });
        gsap.set(overlayRef.value, { opacity: 0 });
      }
    });
  },
  { immediate: true }
);
</script>

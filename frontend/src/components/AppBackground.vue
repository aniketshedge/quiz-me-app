<template>
  <div class="app-background" aria-hidden="true">
    <motion.div
      class="aurora-layer aurora-layer-a"
      :initial="staticA"
      :animate="reducedMotion ? staticA : animateA"
      :transition="transitionA"
    />
    <motion.div
      class="aurora-layer aurora-layer-b"
      :initial="staticB"
      :animate="reducedMotion ? staticB : animateB"
      :transition="transitionB"
    />
    <motion.div
      class="aurora-layer aurora-layer-c"
      :initial="staticC"
      :animate="reducedMotion ? staticC : animateC"
      :transition="transitionC"
    />
    <div class="aurora-vignette"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { motion, useReducedMotion } from "motion-v";

const prefersReducedMotion = useReducedMotion();
const motionMode = ref<"auto" | "on" | "off">("auto");
const reducedMotion = computed(() => {
  if (motionMode.value === "on") {
    return false;
  }
  if (motionMode.value === "off") {
    return true;
  }
  return Boolean(prefersReducedMotion.value);
});

const staticA = {
  x: 0,
  y: 0,
  scale: 1,
  opacity: 0.56
};
const staticB = {
  x: 0,
  y: 0,
  scale: 1,
  opacity: 0.5
};
const staticC = {
  x: 0,
  y: 0,
  scale: 1,
  opacity: 0.44
};

const animateA = {
  x: [-92, 66, -44, -92],
  y: [-52, 30, 48, -52],
  scale: [1, 1.12, 0.92, 1],
  opacity: [0.44, 0.78, 0.54, 0.44]
};
const animateB = {
  x: [74, -48, 58, 74],
  y: [44, -32, 40, 44],
  scale: [1, 0.9, 1.08, 1],
  opacity: [0.36, 0.66, 0.42, 0.36]
};
const animateC = {
  x: [-38, 52, -26, -38],
  y: [56, -38, 30, 56],
  scale: [1, 1.09, 0.91, 1],
  opacity: [0.34, 0.62, 0.4, 0.34]
};

const transitionA = {
  duration: 16,
  repeat: Infinity,
  ease: "easeInOut"
};
const transitionB = {
  duration: 20,
  repeat: Infinity,
  ease: "easeInOut"
};
const transitionC = {
  duration: 18,
  repeat: Infinity,
  ease: "easeInOut"
};

onMounted(() => {
  const motionParam = new URLSearchParams(window.location.search).get("motion")?.toLowerCase();
  if (motionParam === "on" || motionParam === "off") {
    motionMode.value = motionParam;
  }
});
</script>

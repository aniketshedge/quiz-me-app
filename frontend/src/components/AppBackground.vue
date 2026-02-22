<template>
  <div class="app-background" aria-hidden="true">
    <motion.div
      class="aurora-layer aurora-layer-a"
      :animate="reducedMotion ? staticA : animateA"
      :transition="transitionA"
    />
    <motion.div
      class="aurora-layer aurora-layer-b"
      :animate="reducedMotion ? staticB : animateB"
      :transition="transitionB"
    />
    <motion.div
      class="aurora-layer aurora-layer-c"
      :animate="reducedMotion ? staticC : animateC"
      :transition="transitionC"
    />
    <div class="aurora-vignette"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { motion } from "motion-v";

const reducedMotion = ref(false);

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
  x: [-36, 26, -12, -36],
  y: [-20, 14, 22, -20],
  scale: [1, 1.07, 0.96, 1],
  opacity: [0.52, 0.68, 0.58, 0.52]
};
const animateB = {
  x: [24, -18, 22, 24],
  y: [16, -12, 18, 16],
  scale: [1, 0.94, 1.05, 1],
  opacity: [0.44, 0.58, 0.48, 0.44]
};
const animateC = {
  x: [-10, 18, -6, -10],
  y: [20, -16, 14, 20],
  scale: [1, 1.05, 0.95, 1],
  opacity: [0.4, 0.54, 0.46, 0.4]
};

const transitionA = {
  duration: 26,
  repeat: Number.POSITIVE_INFINITY,
  ease: "easeInOut"
};
const transitionB = {
  duration: 32,
  repeat: Number.POSITIVE_INFINITY,
  ease: "easeInOut"
};
const transitionC = {
  duration: 29,
  repeat: Number.POSITIVE_INFINITY,
  ease: "easeInOut"
};

onMounted(() => {
  reducedMotion.value = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
});
</script>

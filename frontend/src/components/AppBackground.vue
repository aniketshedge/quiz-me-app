<template>
  <div class="app-background" aria-hidden="true">
    <Motion
      as="div"
      class="aurora-layer aurora-layer-a"
      :animate="reducedMotion ? staticA : animateA"
      :transition="transitionA"
    />
    <Motion
      as="div"
      class="aurora-layer aurora-layer-b"
      :animate="reducedMotion ? staticB : animateB"
      :transition="transitionB"
    />
    <Motion
      as="div"
      class="aurora-layer aurora-layer-c"
      :animate="reducedMotion ? staticC : animateC"
      :transition="transitionC"
    />
    <div class="aurora-vignette"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Motion, useReducedMotion } from "motion-v";

const prefersReducedMotion = useReducedMotion();
const reducedMotion = computed(() => Boolean(prefersReducedMotion.value));

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
  x: [-64, 44, -28, -64],
  y: [-36, 22, 34, -36],
  scale: [1, 1.09, 0.94, 1],
  opacity: [0.48, 0.72, 0.56, 0.48]
};
const animateB = {
  x: [46, -34, 38, 46],
  y: [30, -24, 28, 30],
  scale: [1, 0.92, 1.06, 1],
  opacity: [0.4, 0.62, 0.46, 0.4]
};
const animateC = {
  x: [-22, 32, -14, -22],
  y: [38, -26, 20, 38],
  scale: [1, 1.07, 0.93, 1],
  opacity: [0.38, 0.58, 0.44, 0.38]
};

const transitionA = {
  duration: 19,
  repeat: Infinity,
  ease: "easeInOut"
};
const transitionB = {
  duration: 24,
  repeat: Infinity,
  ease: "easeInOut"
};
const transitionC = {
  duration: 21,
  repeat: Infinity,
  ease: "easeInOut"
};
</script>

<template>
  <button
    type="button"
    class="theme-toggle"
    :aria-label="isNight ? 'Switch to light mode' : 'Switch to dark mode'"
    :aria-pressed="isNight"
    @click="$emit('toggle')"
  >
    <span class="theme-toggle-track" aria-hidden="true">
      <span class="theme-toggle-hint theme-toggle-hint-day">L</span>
      <span class="theme-toggle-hint theme-toggle-hint-night">D</span>
      <motion.span
        class="theme-toggle-knob"
        :animate="{ x: isNight ? 22 : 0, rotate: isNight ? 180 : 0 }"
        :transition="{ type: 'spring', stiffness: 420, damping: 30, mass: 0.55 }"
      />
    </span>
    <span class="theme-toggle-text">{{ isNight ? "Dark mode" : "Light mode" }}</span>
  </button>
</template>

<script setup lang="ts">
import { motion } from "motion-v";

defineProps<{
  isNight: boolean;
}>();

defineEmits<{
  (event: "toggle"): void;
}>();
</script>

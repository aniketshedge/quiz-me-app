<template>
  <button
    type="button"
    class="theme-toggle"
    :aria-label="isNight ? 'Switch to day mode' : 'Switch to night mode'"
    :aria-pressed="isNight"
    @click="$emit('toggle')"
  >
    <span class="theme-toggle-track" aria-hidden="true">
      <span class="theme-toggle-hint theme-toggle-hint-day">D</span>
      <span class="theme-toggle-hint theme-toggle-hint-night">N</span>
      <motion.span
        class="theme-toggle-knob"
        :animate="{ x: isNight ? 22 : 0, rotate: isNight ? 180 : 0 }"
        :transition="{ type: 'spring', stiffness: 420, damping: 30, mass: 0.55 }"
      />
    </span>
    <span class="theme-toggle-text">{{ isNight ? "Night mode" : "Day mode" }}</span>
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

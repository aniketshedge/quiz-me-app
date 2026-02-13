<template>
  <section class="panel score-panel">
    <h2>Quiz complete</h2>
    <p class="score-value">{{ score }} / {{ total }}</p>
    <p class="subtext">Your plant has reached stage {{ score }}.</p>
    <button type="button" class="btn btn-primary" @click="$emit('restart')">Try another topic</button>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  score: number;
  total: number;
}>();

defineEmits<{
  (event: "restart"): void;
}>();
</script>

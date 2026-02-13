<template>
  <div v-if="visible" class="popup-overlay" @click.self="$emit('close')">
    <div class="popup-card" role="dialog" aria-modal="true">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
      <button type="button" class="btn btn-primary" @click="$emit('close')">OK</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  title: string;
  message: string;
}>();

defineEmits<{
  (event: "close"): void;
}>();
</script>

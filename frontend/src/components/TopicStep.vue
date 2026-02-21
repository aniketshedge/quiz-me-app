<template>
  <section class="panel">
    <h1>Quiz Me</h1>
    <p class="subtext">Enter a topic and we will build a grounded 15-question quiz for you.</p>

    <label for="topic-input" class="field-label">Topic</label>
    <input
      id="topic-input"
      class="text-input"
      type="text"
      :value="modelValue"
      :disabled="resolving"
      placeholder="e.g. Plate tectonics"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keyup.enter="$emit('submit')"
    />

    <p v-if="mockMode" class="warning-note" role="status" aria-live="polite">
      Mock mode is enabled. The app is using deterministic mock quiz data and will not call any LLM APIs.
    </p>

    <div class="actions">
      <button type="button" class="btn btn-primary" :disabled="resolving" @click="$emit('submit')">
        {{ resolving ? "Resolving topic..." : "Find article" }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string;
  resolving: boolean;
  mockMode: boolean;
}>();

defineEmits<{
  (event: "update:modelValue", value: string): void;
  (event: "submit"): void;
}>();
</script>

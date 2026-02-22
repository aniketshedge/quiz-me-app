<template>
  <section class="panel">
    <h1>Quiz Me!</h1>
    <p class="subtext">Create a quiz for yourself based on any topic!</p>

    <label for="topic-input" class="field-label">Enter your topic</label>
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

    <div class="actions">
      <button type="button" class="btn btn-primary" :disabled="resolving" @click="$emit('submit')">
        {{ resolving ? "Resolving topic..." : "Find article" }}
      </button>
    </div>

    <section class="topic-how-it-works" aria-label="How this app works">
      <h3>This is how this app works</h3>
      <ol>
        <li>You choose a topic.</li>
        <li>We find matching Wikipedia articles and you pick the closest one.</li>
        <li>We create a quiz based on the selected Wikipedia article.</li>
        <li>Solve the quiz to test your knowledge of your chosen topic.</li>
      </ol>
    </section>

    <p v-if="mockMode" class="warning-note" role="status" aria-live="polite">
      Mock mode is enabled. This app will use only sample data for the quiz, and not use any AI models.
    </p>
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

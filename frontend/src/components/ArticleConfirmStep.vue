<template>
  <section class="panel">
    <h2>Confirm the article</h2>
    <p class="subtext">Select the article that best matches your intended quiz topic.</p>

    <div v-if="primary" class="candidate-card" :class="{ selected: selected?.page_id === primary.page_id }">
      <div>
        <h3>{{ primary.title }}</h3>
        <p>{{ primary.summary }}</p>
        <a :href="primary.url" target="_blank" rel="noreferrer">Open source article</a>
      </div>
      <img v-if="primary.image_url" :src="primary.image_url" :alt="primary.title" />
      <button type="button" class="btn" @click="$emit('select', primary)">Use this article</button>
    </div>

    <div v-if="alternatives.length" class="alt-list">
      <h4>Alternatives</h4>
      <button
        v-for="item in alternatives"
        :key="item.page_id"
        type="button"
        class="alt-item"
        :class="{ selected: selected?.page_id === item.page_id }"
        @click="$emit('select', item)"
      >
        <strong>{{ item.title }}</strong>
        <span>{{ item.summary }}</span>
      </button>
    </div>

    <div class="actions">
      <button type="button" class="btn" :disabled="loading" @click="$emit('back')">Try another topic</button>
      <button type="button" class="btn btn-primary" :disabled="loading || !selected" @click="$emit('create')">
        {{ loading ? "Generating quiz..." : "Generate quiz" }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TopicCandidate } from "../types";

defineProps<{
  primary: TopicCandidate | null;
  alternatives: TopicCandidate[];
  selected: TopicCandidate | null;
  loading: boolean;
}>();

defineEmits<{
  (event: "select", value: TopicCandidate): void;
  (event: "create"): void;
  (event: "back"): void;
}>();
</script>

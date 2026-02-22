<template>
  <section class="panel article-confirm-panel">
    <h2>Confirm the article</h2>
    <p class="subtext">Select the article that best matches your intended quiz topic.</p>

    <div
      v-if="primary"
      class="candidate-card candidate-card-main"
      :class="{ selected: selected?.page_id === primary.page_id, disabled: loading }"
      role="button"
      tabindex="0"
      @click="onPrimaryCardClick"
      @keydown.enter.prevent="onPrimaryCardClick"
      @keydown.space.prevent="onPrimaryCardClick"
    >
      <div>
        <h3>{{ primary.title }}</h3>
        <p>{{ primary.summary }}</p>
        <a :href="primary.url" target="_blank" rel="noreferrer" @click.stop>Open source article</a>
      </div>
      <img v-if="primary.image_url" :src="primary.image_url" :alt="primary.title" />
      <button
        type="button"
        class="btn btn-primary candidate-card-main-btn"
        :disabled="loading"
        @click.stop="$emit('use-primary')"
      >
        {{ loading ? "Generating quiz..." : "Use this article" }}
      </button>
      <p class="attribution" v-if="primary.image_url">
        Image source: Wikimedia Commons (via Wikipedia). Original creator/license apply.
        <a :href="primary.url" target="_blank" rel="noreferrer" @click.stop>Source</a>
      </p>
    </div>

    <div v-if="alternatives.length" class="alt-list">
      <h4>Alternatives</h4>
      <button
        v-for="item in alternatives"
        :key="item.page_id"
        type="button"
        class="alt-item"
        :class="{ selected: selected?.page_id === item.page_id }"
        :disabled="loading"
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

    <div v-if="loading" class="loading-overlay" role="status" aria-live="polite">
      <div class="loading-card">
        <div class="loading-spinner" aria-hidden="true"></div>
        <p>Generating your quiz. This can take up to 1-2 minutes.</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { TopicCandidate } from "../types";

const emit = defineEmits<{
  (event: "select", value: TopicCandidate): void;
  (event: "use-primary"): void;
  (event: "create"): void;
  (event: "back"): void;
}>();

const props = defineProps<{
  primary: TopicCandidate | null;
  alternatives: TopicCandidate[];
  selected: TopicCandidate | null;
  loading: boolean;
}>();

function onPrimaryCardClick(): void {
  if (!props.primary || props.loading) {
    return;
  }
  emit("select", props.primary);
}
</script>

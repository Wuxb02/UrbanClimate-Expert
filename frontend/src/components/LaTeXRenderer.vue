<template>
  <div v-html="compiled" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown } from "../utils/markdown";

const props = defineProps<{ text: string }>();
const compiled = computed(() => renderMarkdown(props.text));
</script>

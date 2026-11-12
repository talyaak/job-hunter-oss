<script setup lang="ts">
import { computed } from 'vue'
import { sharedPrefs } from '../composables/usePreferences'

const props = defineProps<{ score: number | null }>()

const color = computed(() => {
  if (props.score == null) return 'text-slate-500 border-slate-700/60 bg-transparent'
  if (props.score >= sharedPrefs.high_score_threshold) return 'text-amber-300 border-amber-500/50 bg-amber-500/15'
  if (props.score >= sharedPrefs.score_threshold) return 'text-teal-300 border-teal-500/50 bg-teal-500/15'
  return 'text-slate-400 border-slate-600/50 bg-slate-600/15'
})
</script>

<template>
  <span
    class="inline-flex min-w-[2.5rem] justify-center rounded-md border px-1.5 py-0.5 text-xs font-bold tabular-nums"
    :class="color"
    :title="score == null ? 'Not scored' : undefined"
  >{{ score == null ? '—' : score + '%' }}</span>
</template>

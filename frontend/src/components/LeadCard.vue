<script setup lang="ts">
import type { Lead, ApplicationStatus } from '../types/lead'
import PlatformBadge from './PlatformBadge.vue'
import ScoreBadge from './ScoreBadge.vue'
import MatchReasonTooltip from './MatchReasonTooltip.vue'

defineProps<{ leads: Lead[] }>()
const emit = defineEmits<{
  'update-status': [id: number, status: ApplicationStatus]
  apply: [lead: Lead]
  'cover-letter': [lead: Lead]
}>()

const statuses: ApplicationStatus[] = ['hidden', 'saved', 'applied']
</script>

<template>
  <div class="space-y-3 lg:hidden">
    <article
      v-for="(lead, i) in leads"
      :key="lead.id"
      class="glass-panel animate-fade-up p-4"
      :style="{ animationDelay: `${i * 60}ms` }"
    >
      <div class="mb-3 flex items-start justify-between gap-2">
        <PlatformBadge :source="lead.platform_source" />
        <ScoreBadge :score="lead.relevance_score" />
      </div>

      <a :href="lead.job_url" target="_blank" rel="noopener noreferrer" class="font-display text-lg font-semibold text-slate-100">
        {{ lead.job_title }}
      </a>
      <p class="mt-0.5 text-sm text-slate-500">{{ lead.company }}</p>

      <div class="mt-3">
        <MatchReasonTooltip
          :reason="lead.match_reason"
          :stack-match="lead.stack_match"
          :evaluation="lead.match_evaluation"
          :score="lead.relevance_score"
        />
      </div>

      <div class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button
          type="button"
          class="btn-primary w-full py-3 text-sm font-semibold"
          @click="emit('apply', lead)"
        >
          Apply
        </button>
        <button
          type="button"
          class="w-full rounded-lg border-2 border-teal-500/40 bg-teal-500/15 py-3 text-sm font-semibold text-teal-100"
          @click="emit('cover-letter', lead)"
        >
          Cover letter
        </button>
      </div>

      <div class="mt-3 grid grid-cols-2 gap-2">
        <button
          type="button"
          class="w-full rounded-lg border py-2.5 text-sm font-medium transition-colors"
          :class="lead.application_status === 'applied' ? 'border-teal-500/40 bg-teal-500/20 text-teal-100' : 'border-white/10 text-slate-200 hover:bg-white/5'"
          @click="emit('update-status', lead.id, lead.application_status === 'applied' ? 'saved' : 'applied')"
        >
          {{ lead.application_status === 'applied' ? 'Applied ✓' : 'Mark applied' }}
        </button>
        <select
          :value="lead.application_status"
          class="select-surface w-full capitalize"
          @change="emit('update-status', lead.id, ($event.target as HTMLSelectElement).value as ApplicationStatus)"
        >
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>
    </article>
  </div>
</template>

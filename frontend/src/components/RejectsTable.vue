<script setup lang="ts">
import type { Reject } from '../types/reject'
import ScoreBadge from './ScoreBadge.vue'

withDefaults(
  defineProps<{ rejects: Reject[]; mode?: 'default' | 'unscored' }>(),
  { mode: 'default' },
)

const stageLabels: Record<string, string> = {
  llm_score: 'Below threshold',
  location: 'Location filter',
  hard_title: 'Title filter',
  dedupe: 'Duplicate',
  embedding_filter: 'Similarity filter',
  gemma_filter: 'Gemma hard-no',
}

const stageStyles: Record<string, string> = {
  llm_score: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  location: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
  hard_title: 'border-slate-500/30 bg-slate-500/10 text-slate-400',
  dedupe: 'border-slate-600/30 bg-slate-600/10 text-slate-500',
  embedding_filter: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300',
  gemma_filter: 'border-violet-500/30 bg-violet-500/10 text-violet-300',
  unscored: 'border-red-500/30 bg-red-500/10 text-red-300',
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function errorLabel(reason: string) {
  if (reason.startsWith('429')) return 'Gemini quota exceeded'
  if (reason.length > 80) return reason.slice(0, 77) + '…'
  return reason
}
</script>

<template>
  <div class="hidden rounded-2xl border border-white/[0.08] md:block">
    <div class="overflow-x-auto">
      <table class="w-full min-w-[900px] text-left text-sm">
        <thead>
          <tr class="border-b border-white/[0.06] bg-white/[0.02] text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            <th class="px-4 py-3.5">Seen</th>
            <th class="min-w-[12rem] px-4 py-3.5">Role</th>
            <th v-if="mode === 'default'" class="px-4 py-3.5">Stage</th>
            <th v-if="mode === 'default'" class="px-4 py-3.5">Score</th>
            <th v-if="mode === 'unscored'" class="px-4 py-3.5">Status</th>
            <th class="min-w-[14rem] px-4 py-3.5">{{ mode === 'unscored' ? 'Error' : 'Reason' }}</th>
            <th v-if="mode === 'default'" class="px-4 py-3.5">Stack</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, i) in rejects"
            :key="row.id"
            class="border-b border-white/[0.04] transition-colors hover:bg-white/[0.02]"
            :style="{ animationDelay: `${i * 30}ms` }"
          >
            <td class="whitespace-nowrap px-4 py-3.5 text-xs tabular-nums text-slate-500">
              {{ formatDate(row.created_at) }}
            </td>
            <td class="px-4 py-3.5">
              <a
                :href="row.job_url"
                target="_blank"
                rel="noopener noreferrer"
                class="font-medium text-slate-200 hover:text-amber-200"
              >{{ row.job_title ?? 'Unknown role' }}</a>
              <div class="mt-0.5 text-xs text-slate-500">{{ row.company ?? '—' }}</div>
            </td>
            <td v-if="mode === 'default'" class="px-4 py-3.5">
              <span
                class="inline-block rounded-md border px-2 py-0.5 text-[10px] font-medium"
                :class="stageStyles[row.reject_stage] ?? stageStyles.hard_title"
              >{{ stageLabels[row.reject_stage] ?? row.reject_stage }}</span>
            </td>
            <td v-if="mode === 'default'" class="px-4 py-3.5">
              <ScoreBadge v-if="row.relevance_score != null" :score="row.relevance_score" />
              <span v-else class="text-xs text-slate-600">—</span>
            </td>
            <td v-if="mode === 'unscored'" class="px-4 py-3.5">
              <span class="inline-block rounded-md border px-2 py-0.5 text-[10px] font-medium" :class="stageStyles.unscored">
                Not scored
              </span>
            </td>
            <td class="max-w-[24rem] px-4 py-3.5 text-xs leading-snug text-slate-400">
              <span class="line-clamp-2" :title="row.reject_reason">{{ errorLabel(row.reject_reason) }}</span>
            </td>
            <td v-if="mode === 'default'" class="px-4 py-3.5">
              <div v-if="row.stack_match.length" class="flex flex-wrap gap-1">
                <span
                  v-for="tech in row.stack_match.slice(0, 4)"
                  :key="tech"
                  class="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-400"
                >{{ tech }}</span>
                <span v-if="row.stack_match.length > 4" class="text-[10px] text-slate-600">+{{ row.stack_match.length - 4 }}</span>
              </div>
              <span v-else class="text-xs text-slate-600">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <div v-if="mode === 'unscored'" class="mt-3 space-y-3 md:hidden">
    <article
      v-for="row in rejects"
      :key="row.id"
      class="glass-panel p-4"
    >
      <span class="mb-2 inline-block rounded-md border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-300">
        Not scored
      </span>
      <a :href="row.job_url" target="_blank" rel="noopener noreferrer" class="mt-2 block font-display font-semibold text-slate-100">
        {{ row.job_title ?? 'Unknown role' }}
      </a>
      <p class="text-sm text-slate-500">{{ row.company ?? '—' }}</p>
      <p class="mt-2 text-xs text-slate-400">{{ errorLabel(row.reject_reason) }}</p>
    </article>
  </div>
</template>

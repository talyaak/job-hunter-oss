<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { api } from '../api/client'
import { useSyncWs } from '../composables/useSyncWs'
import type { SyncPhase } from '../types/sync'

const emit = defineEmits<{ synced: [] }>()

const { state, connected, isRunning, refreshStatus } = useSyncWs(() => emit('synced'))

const loading = computed(() => isRunning())
const error = computed(() =>
  state.value.phase === 'failed' ? state.value.error_message : null,
)

const phaseLabel: Record<SyncPhase, string> = {
  idle: 'Ready',
  scraping: 'Scraping job boards…',
  enriching: 'Enriching LinkedIn descriptions…',
  filtering: 'LLM recruiter scoring…',
  completed: 'Sync complete',
  failed: 'Sync failed',
}

const progressPct = computed(() => {
  if (!state.value.raw_count) return 0
  return Math.min(100, Math.round((state.value.processed / state.value.raw_count) * 100))
})

const showStatusPanel = computed(
  () => loading.value || (state.value.phase === 'completed' && !error.value) || state.value.phase === 'failed',
)

const lastSync = computed(() =>
  state.value.phase === 'completed' ? new Date().toLocaleString() : null,
)

async function syncNow() {
  state.value = { ...state.value, phase: 'idle', error_message: null }
  try {
    await api.startSync()
  } catch (e) {
    state.value = {
      ...state.value,
      phase: 'failed',
      error_message: e instanceof Error ? e.message : 'Sync failed',
    }
  }
}

onMounted(() => refreshStatus())
</script>

<template>
  <div class="flex w-full max-w-sm flex-col items-end gap-2">
    <button type="button" class="btn-primary flex items-center gap-2" :disabled="loading" @click="syncNow">
      <svg v-if="loading" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
      </svg>
      <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 12a9 9 0 11-2.64-6.36M21 3v6h-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ loading ? 'Syncing…' : 'Sync Now' }}
    </button>

    <div
      v-if="showStatusPanel"
      class="glass-panel w-full p-3 text-xs"
    >
      <div class="mb-2 flex items-center justify-between">
        <span class="font-medium text-slate-300">{{ phaseLabel[state.phase] }}</span>
        <span class="text-[10px] text-slate-600" :class="connected ? 'text-teal-500' : 'text-amber-500'">
          {{ connected ? 'live' : 'reconnecting…' }}
        </span>
      </div>

      <div v-if="state.raw_count" class="mb-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          class="h-full rounded-full bg-gradient-to-r from-amber-500 to-teal-400 transition-all duration-300"
          :style="{ width: `${progressPct}%` }"
        />
      </div>

      <p v-if="state.current_job && loading" class="mb-2 truncate text-[10px] text-slate-500">
        {{ state.current_job }}
      </p>

      <div v-if="state.sources && Object.keys(state.sources).length" class="mb-2 flex flex-wrap gap-1.5">
        <span
          v-for="(count, src) in state.sources"
          :key="src"
          class="rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] capitalize text-slate-400"
        >{{ src }} {{ count }}</span>
      </div>

      <div v-if="state.raw_count" class="grid grid-cols-3 gap-2 text-center text-[10px]">
        <div><span class="block font-bold text-white">{{ state.raw_count }}</span><span class="text-slate-600">scraped</span></div>
        <div><span class="block font-bold text-teal-300">{{ state.passed_count }}</span><span class="text-slate-600">passed</span></div>
        <div><span class="block font-bold text-slate-400">{{ state.llm_rejected + state.hard_rejected + state.deduped }}</span><span class="text-slate-600">rejected</span></div>
      </div>
    </div>

    <p v-if="lastSync && state.phase === 'completed'" class="text-[11px] text-slate-500">Finished {{ lastSync }}</p>
    <p v-if="error" class="text-[11px] text-red-400">{{ error }}</p>
  </div>
</template>

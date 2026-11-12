<script setup lang="ts">
import { ref, computed } from 'vue'
import type { MatchEvaluation } from '../types/evaluation'

const props = defineProps<{
  reason: string
  stackMatch: string[]
  evaluation?: MatchEvaluation
  score?: number | null
}>()

const open = ref(false)
const style = ref<Record<string, string>>({ top: '0px', left: '0px', transform: 'none' })

const dimensionLabels: Record<string, string> = {
  hard_requirements_score: 'Hard reqs',
  domain_similarity_score: 'Domain',
  seniority_score: 'Seniority',
  technology_score: 'Tech',
  signal_score: 'Signals',
}

const label = computed(() =>
  props.score != null ? `${props.score}% match` : 'Match analysis',
)

function show(e: MouseEvent | FocusEvent) {
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const w = 320
  const pad = 12
  let left = rect.left
  if (left + w > window.innerWidth - pad) left = window.innerWidth - w - pad
  if (left < pad) left = pad

  const estHeight = 280
  let top: number
  if (rect.top > estHeight + pad) {
    top = rect.top - pad
    style.value = { top: `${top}px`, left: `${left}px`, transform: 'translateY(-100%)' }
  } else {
    top = rect.bottom + pad
    style.value = { top: `${top}px`, left: `${left}px`, transform: 'none' }
  }
  open.value = true
}

function hide() {
  open.value = false
}
</script>

<template>
  <span
    class="inline-block"
    @mouseenter="show"
    @mouseleave="hide"
    @focus="show"
    @blur="hide"
  >
    <button
      type="button"
      class="cursor-help truncate text-left text-xs leading-snug text-slate-400 underline decoration-dotted decoration-slate-600 underline-offset-2 transition-colors hover:text-slate-200 focus:text-slate-200 focus:outline-none"
    >
      {{ label }}
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        class="pointer-events-none fixed z-[100] w-80 max-w-[calc(100vw-1.5rem)] rounded-xl border border-white/10 bg-[#1a222d]/98 p-3 shadow-2xl backdrop-blur-xl"
        :style="style"
      >
        <p class="text-xs leading-relaxed text-slate-200">{{ reason }}</p>

        <div v-if="evaluation?.scores" class="mt-2.5 grid grid-cols-2 gap-1.5">
          <div
            v-for="(dim, key) in evaluation.scores"
            :key="key"
            class="rounded-md border border-white/5 bg-white/[0.03] px-2 py-1"
          >
            <div class="flex justify-between text-[10px]">
              <span class="text-slate-500">{{ dimensionLabels[key] ?? key }}</span>
              <span class="font-semibold tabular-nums text-amber-300">{{ dim.value }}</span>
            </div>
            <p class="mt-0.5 line-clamp-2 text-[9px] leading-tight text-slate-500">{{ dim.explanation }}</p>
          </div>
        </div>

        <ul v-if="evaluation?.strengths?.length" class="mt-2 space-y-0.5 text-[10px] text-teal-300/90">
          <li v-for="s in evaluation.strengths.slice(0, 2)" :key="s">+ {{ s }}</li>
        </ul>
        <ul v-if="evaluation?.gaps?.length" class="mt-1 space-y-0.5 text-[10px] text-amber-400/80">
          <li v-for="g in evaluation.gaps.slice(0, 2)" :key="g">− {{ g }}</li>
        </ul>

        <div v-if="stackMatch.length" class="mt-2.5 flex flex-wrap gap-1.5">
          <span
            v-for="tech in stackMatch"
            :key="tech"
            class="rounded-md border border-teal-500/30 bg-teal-500/10 px-2 py-0.5 text-[10px] font-medium text-teal-300"
          >{{ tech }}</span>
        </div>
      </div>
    </Teleport>
  </span>
</template>

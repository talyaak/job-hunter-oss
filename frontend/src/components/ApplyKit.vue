<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { Lead, ApplicationStatus } from '../types/lead'
import type { ApplyProfile } from '../types/profile'
import { api } from '../api/client'

const props = defineProps<{
  lead: Lead | null
  open: boolean
}>()
const emit = defineEmits<{ close: []; 'cover-letter': []; 'set-status': [status: ApplicationStatus] }>()

const profile = ref<ApplyProfile | null>(null)
const loading = ref(false)
const copyMsg = ref('')
const error = ref('')

const linkedinUrl = computed(() => profile.value?.linkedin_url || '')

const fields = computed(() => {
  const p = profile.value
  if (!p) return []
  return [
    { key: 'full_name', label: 'Full name', value: p.full_name },
    { key: 'email', label: 'Email', value: p.email },
    { key: 'phone', label: 'Phone', value: p.phone },
    { key: 'location', label: 'Location', value: p.location },
    { key: 'github_url', label: 'GitHub', value: p.github_url },
    { key: 'portfolio_url', label: 'Portfolio', value: p.portfolio_url },
  ].filter((f) => f.value)
})

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    copyMsg.value = ''
    error.value = ''
    loading.value = true
    try {
      profile.value = await api.getApplyProfile()
    } catch {
      error.value = 'Could not load apply profile. Upload CV or set APPLY_* in .env.'
      profile.value = null
    } finally {
      loading.value = false
    }
  },
)

async function copyValue(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value)
    copyMsg.value = `${label} copied`
    setTimeout(() => {
      if (copyMsg.value === `${label} copied`) copyMsg.value = ''
    }, 2000)
  } catch {
    copyMsg.value = 'Copy failed — select text manually'
  }
}

async function copyAll() {
  const lines = [`LinkedIn profile: ${linkedinUrl.value}`, ...fields.value.map((f) => `${f.label}: ${f.value}`)]
  await copyValue(lines.join('\n'), 'All fields')
}

</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && lead"
      class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
      @click.self="emit('close')"
    >
      <div class="flex max-h-[90vh] w-full max-w-md flex-col rounded-t-2xl border border-white/10 bg-slate-900 shadow-2xl sm:rounded-2xl">
        <header class="border-b border-white/10 px-5 py-4">
          <p class="text-[10px] font-semibold uppercase tracking-wider text-amber-400/90">Apply helper</p>
          <h2 class="font-display mt-1 text-lg font-semibold text-white">{{ lead.job_title }}</h2>
          <p class="text-sm text-slate-500">{{ lead.company }}</p>
        </header>

        <div class="flex-1 overflow-y-auto px-5 py-4">
          <p class="mb-4 text-xs leading-relaxed text-slate-400">
            On phone: copy fields below, open the application, then paste into each box.
            On desktop: install the Job Hunter Chrome extension for one-click autofill.
          </p>

          <p v-if="loading" class="text-sm text-slate-500">Loading profile…</p>
          <p v-else-if="error" class="text-sm text-red-400">{{ error }}</p>

          <template v-else>
            <div class="mb-3 flex items-center justify-between gap-3 rounded-lg border border-sky-500/25 bg-sky-500/10 px-3 py-2.5">
              <div class="min-w-0 flex-1">
                <p class="text-[10px] font-semibold uppercase tracking-wider text-sky-300/80">LinkedIn profile</p>
                <p class="truncate text-sm text-sky-100">{{ linkedinUrl }}</p>
              </div>
              <button
                type="button"
                class="shrink-0 rounded-md border border-sky-400/40 bg-sky-500/20 px-2.5 py-1 text-[11px] font-medium text-sky-100"
                @click="copyValue(linkedinUrl, 'LinkedIn profile')"
              >
                Copy
              </button>
            </div>

            <ul v-if="fields.length" class="space-y-2">
              <li
                v-for="f in fields"
                :key="f.key"
                class="flex items-center justify-between gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5"
              >
                <div class="min-w-0 flex-1">
                  <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-600">{{ f.label }}</p>
                  <p class="truncate text-sm text-slate-200">{{ f.value }}</p>
                </div>
                <button
                  type="button"
                  class="shrink-0 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-200"
                  @click="copyValue(f.value, f.label)"
                >
                  Copy
                </button>
              </li>
            </ul>
            <p v-else class="text-sm text-slate-500">No other apply fields found. Upload CV or configure APPLY_* env vars.</p>
          </template>

          <p v-if="copyMsg" class="mt-3 text-xs text-teal-400">{{ copyMsg }}</p>
        </div>

        <footer class="flex flex-col gap-2 border-t border-white/10 px-5 py-4 sm:flex-row sm:flex-wrap">
          <a
            :href="lead.job_url"
            target="_blank"
            rel="noopener noreferrer"
            class="btn-primary flex-1 text-center"
          >
            Open application
          </a>
          <button
            type="button"
            class="rounded-lg border px-4 py-2 text-sm font-medium transition-colors"
            :class="lead.application_status === 'applied' ? 'border-teal-400/50 bg-teal-500/25 text-teal-100' : 'border-white/10 text-slate-200 hover:bg-white/5'"
            @click="emit('set-status', lead.application_status === 'applied' ? 'saved' : 'applied')"
          >
            {{ lead.application_status === 'applied' ? 'Applied ✓' : 'Mark applied' }}
          </button>
          <button
            type="button"
            class="rounded-lg border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-200 hover:bg-teal-500/20"
            @click="emit('cover-letter')"
          >
            Cover letter
          </button>
          <button
            type="button"
            class="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-300 hover:bg-white/5"
            @click="copyAll"
          >
            Copy all
          </button>
          <button type="button" class="rounded-lg px-4 py-2 text-sm text-slate-500 hover:text-slate-300" @click="emit('close')">
            Close
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

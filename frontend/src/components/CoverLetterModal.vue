<script setup lang="ts">
import { ref } from 'vue'
import type { Lead } from '../types/lead'
import type { CoverLetterOptions } from '../types/coverLetter'
import { api } from '../api/client'
import { downloadCoverLetterPdf } from '../utils/coverLetterPdf'

const props = defineProps<{
  lead: Lead | null
  open: boolean
}>()
const emit = defineEmits<{ close: [] }>()

const tone = ref<CoverLetterOptions['tone']>('professional')
const length = ref<CoverLetterOptions['length']>('medium')
const instructions = ref('')
const text = ref('')
const loading = ref(false)
const error = ref('')
const copyMsg = ref('')

async function generate() {
  if (!props.lead) return
  loading.value = true
  error.value = ''
  copyMsg.value = ''
  try {
    const res = await api.generateCoverLetter(props.lead.id, {
      tone: tone.value,
      length: length.value,
      instructions: instructions.value.trim() || undefined,
    })
    text.value = res.cover_letter
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Generation failed'
  } finally {
    loading.value = false
  }
}

async function copyLetter() {
  if (!text.value) return
  try {
    await navigator.clipboard.writeText(text.value)
    copyMsg.value = 'Copied to clipboard'
  } catch {
    copyMsg.value = 'Copy failed'
  }
}

function downloadPdf() {
  if (!text.value || !props.lead) return
  const safe = props.lead.company.replace(/[^\w\-]+/g, '_').slice(0, 40)
  downloadCoverLetterPdf({
    filename: `cover-letter_${safe}.pdf`,
    heading: 'Cover Letter',
    subheading: `${props.lead.job_title} — ${props.lead.company}`,
    body: text.value,
  })
  copyMsg.value = 'PDF downloaded'
}

function onClose() {
  text.value = ''
  instructions.value = ''
  error.value = ''
  copyMsg.value = ''
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open && lead"
      class="fixed inset-0 z-[60] flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
      @click.self="onClose"
    >
      <div class="flex max-h-[92vh] w-full max-w-lg flex-col rounded-t-2xl border border-white/10 bg-slate-900 shadow-2xl sm:rounded-2xl">
        <header class="border-b border-white/10 px-5 py-4">
          <p class="text-[10px] font-semibold uppercase tracking-wider text-teal-400/90">Cover letter</p>
          <h2 class="font-display mt-1 text-lg font-semibold text-white">{{ lead.job_title }}</h2>
          <p class="text-sm text-slate-500">{{ lead.company }}</p>
        </header>

        <div class="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <p class="text-xs text-slate-500">
            Optional — uses one Gemini call from your CV, profile, and match score. Edit before pasting or downloading.
          </p>

          <div class="flex flex-wrap gap-3">
            <label class="text-xs text-slate-400">
              Tone
              <select v-model="tone" class="select-surface mt-1 block min-w-[8rem]">
                <option value="professional">Professional</option>
                <option value="concise">Concise</option>
                <option value="warm">Warm</option>
              </select>
            </label>
            <label class="text-xs text-slate-400">
              Length
              <select v-model="length" class="select-surface mt-1 block min-w-[8rem]">
                <option value="short">Short (~120 words)</option>
                <option value="medium">Medium (~220 words)</option>
              </select>
            </label>
          </div>

          <label class="block text-xs text-slate-400">
            Custom instructions (optional)
            <textarea
              v-model="instructions"
              rows="3"
              placeholder="e.g. Mention my AI platform work, keep it under 200 words, address the hiring manager by name…"
              class="input-surface mt-1 w-full resize-y text-sm text-slate-200"
            />
          </label>

          <button type="button" class="btn-primary w-full sm:w-auto" :disabled="loading" @click="generate">
            {{ loading ? 'Generating…' : text ? 'Regenerate' : 'Generate cover letter' }}
          </button>

          <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

          <textarea
            v-model="text"
            rows="12"
            placeholder="Click Generate to draft a letter tailored to this role…"
            class="input-surface w-full resize-y text-sm leading-relaxed text-slate-200"
          />
          <p v-if="copyMsg" class="text-xs text-teal-400">{{ copyMsg }}</p>
        </div>

        <footer class="flex flex-wrap gap-2 border-t border-white/10 px-5 py-4">
          <button
            type="button"
            class="rounded-lg border border-white/10 px-4 py-2 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-40"
            :disabled="!text"
            @click="copyLetter"
          >
            Copy
          </button>
          <button
            type="button"
            class="rounded-lg border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-200 hover:bg-teal-500/20 disabled:opacity-40"
            :disabled="!text"
            @click="downloadPdf"
          >
            Download PDF
          </button>
          <button type="button" class="ml-auto rounded-lg px-4 py-2 text-sm text-slate-500 hover:text-slate-300" @click="onClose">
            Close
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

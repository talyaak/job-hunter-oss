<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import type { DeepHealth, OnboardingStatus, Preferences } from '../types/preferences'

const emit = defineEmits<{ close: []; changed: [] }>()

const status = ref<OnboardingStatus | null>(null)
const prefs = ref<Preferences | null>(null)
const health = ref<DeepHealth | null>(null)
const msg = ref('')
const busy = ref(false)

const geminiKey = ref('')
const linkedinCookie = ref('')
const ntfyTopic = ref('')
const cvFile = ref<File | null>(null)

// Comma-separated editors for list fields
const titles = ref('')
const blockedTitles = ref('')
const blockedCompanies = ref('')
const cronHours = ref('')

function csv(value: string): string[] {
  return value.split(',').map((v) => v.trim()).filter(Boolean)
}

async function refresh() {
  status.value = await api.getOnboardingStatus()
  const p = await api.getPreferences()
  prefs.value = p
  titles.value = p.target_titles.join(', ')
  blockedTitles.value = p.blocked_title_keywords.join(', ')
  blockedCompanies.value = p.blocked_companies.join(', ')
  cronHours.value = p.cron_hours.join(', ')
}

async function guard<T>(fn: () => Promise<T>, ok: string): Promise<T | undefined> {
  busy.value = true
  msg.value = ''
  try {
    const out = await fn()
    msg.value = ok
    emit('changed')
    return out
  } catch (e) {
    msg.value = e instanceof Error ? e.message : 'Something went wrong'
  } finally {
    busy.value = false
  }
}

async function saveGemini() {
  if (!geminiKey.value.trim()) return
  await guard(async () => {
    await api.setOnboardingEnv({ gemini_api_key: geminiKey.value.trim() })
    geminiKey.value = ''
    const res = await api.validateOnboarding('gemini')
    msg.value = res.ok ? 'Gemini key saved and working.' : `Saved, but the test call failed: ${res.detail}`
    await refresh()
  }, '')
}

async function uploadCv() {
  if (!cvFile.value) return
  await guard(async () => {
    await api.uploadProfile(cvFile.value, null)
    await refresh()
  }, 'CV uploaded.')
}

async function savePrefs() {
  if (!prefs.value) return
  const body: Preferences = {
    ...prefs.value,
    target_titles: csv(titles.value),
    blocked_title_keywords: csv(blockedTitles.value),
    blocked_companies: csv(blockedCompanies.value),
    cron_hours: csv(cronHours.value).map(Number).filter((n) => Number.isInteger(n) && n >= 0 && n <= 23),
  }
  await guard(async () => {
    prefs.value = await api.savePreferences(body)
    await api.completeOnboarding()
    await refresh()
  }, 'Preferences saved.')
}

async function saveLinkedin() {
  if (!linkedinCookie.value.trim()) return
  await guard(async () => {
    await api.setOnboardingEnv({ linkedin_cookie_string: linkedinCookie.value.trim() })
    linkedinCookie.value = ''
    const res = await api.validateOnboarding('linkedin')
    msg.value = res.ok ? 'LinkedIn cookie works.' : `Saved, but: ${res.detail}`
    await refresh()
  }, '')
}

async function makeTopic() {
  await guard(async () => {
    const res = await api.generateNtfyTopic()
    ntfyTopic.value = res.topic
    await refresh()
  }, 'Topic created. Subscribe to it in the ntfy app (keep it private).')
}

async function runHealth(probe: boolean) {
  await guard(async () => {
    health.value = await api.getDeepHealth(probe)
  }, probe ? 'Live health check finished.' : 'Health check finished.')
}

const stepDone = computed(() => Object.fromEntries((status.value?.steps ?? []).map((s) => [s.id, s.done])))
const badge = (s: string) => ({ pass: 'text-teal-300', warn: 'text-amber-300', fail: 'text-red-400', skip: 'text-slate-500' })[s] ?? ''

onMounted(refresh)
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-6" @click.self="emit('close')">
    <div class="glass-panel-strong flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-2xl sm:rounded-2xl">
      <div class="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-wider text-amber-400/90">Setup &amp; settings</p>
          <h2 class="font-display text-lg font-bold text-white">Make Job Hunter yours</h2>
        </div>
        <button type="button" class="btn-ghost" @click="emit('close')">Close</button>
      </div>

      <div class="space-y-6 overflow-y-auto px-5 py-5 text-sm">
        <p v-if="msg" class="rounded-md bg-white/5 px-3 py-2 text-xs text-slate-300">{{ msg }}</p>

        <section>
          <h3 class="mb-2 font-semibold text-slate-200">1. Gemini API key {{ stepDone.gemini ? '✓' : '' }}</h3>
          <p class="mb-2 text-xs text-slate-500">
            Free key at aistudio.google.com/apikey. Stored in your local <code>.env</code> only.
            <span v-if="status?.secrets.gemini_api_key"> Current: {{ status.secrets.gemini_api_key }}</span>
          </p>
          <div class="flex gap-2">
            <input v-model="geminiKey" type="password" autocomplete="off" placeholder="AIza..." class="input-surface flex-1" />
            <button type="button" class="btn-primary" :disabled="busy" @click="saveGemini">Save &amp; test</button>
          </div>
        </section>

        <section>
          <h3 class="mb-2 font-semibold text-slate-200">2. Your CV {{ stepDone.profile ? '✓' : '' }}</h3>
          <div class="flex gap-2">
            <input type="file" accept=".pdf" class="input-surface flex-1" @change="cvFile = ($event.target as HTMLInputElement).files?.[0] ?? null" />
            <button type="button" class="btn-primary" :disabled="busy || !cvFile" @click="uploadCv">Upload</button>
          </div>
          <p class="mt-1 text-xs text-slate-500">Text-based PDF. Used to score jobs and sent to Gemini; never published.</p>
        </section>

        <section v-if="prefs">
          <h3 class="mb-2 font-semibold text-slate-200">3. What you are looking for {{ stepDone.preferences ? '✓' : '' }}</h3>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs text-slate-500 sm:col-span-2">Job titles (comma separated)
              <input v-model="titles" class="input-surface mt-1 w-full" placeholder="Backend Engineer, Platform Engineer" />
            </label>
            <label class="text-xs text-slate-500">Location
              <input v-model="prefs.search_location" class="input-surface mt-1 w-full" placeholder="Berlin, Germany or Remote" />
            </label>
            <label class="text-xs text-slate-500">Country for Indeed
              <input v-model="prefs.country" class="input-surface mt-1 w-full" placeholder="Germany (optional)" />
            </label>
            <label class="text-xs text-slate-500">Always reject titles containing
              <input v-model="blockedTitles" class="input-surface mt-1 w-full" placeholder="Manager, Intern, QA" />
            </label>
            <label class="text-xs text-slate-500">Blocked companies
              <input v-model="blockedCompanies" class="input-surface mt-1 w-full" />
            </label>
            <label class="text-xs text-slate-500">Keep leads scoring at least
              <input v-model.number="prefs.score_threshold" type="number" min="0" max="100" class="input-surface mt-1 w-full" />
            </label>
            <label class="text-xs text-slate-500">Highlight scores from
              <input v-model.number="prefs.high_score_threshold" type="number" min="0" max="100" class="input-surface mt-1 w-full" />
            </label>
            <label class="text-xs text-slate-500">Sweep hours (0-23)
              <input v-model="cronHours" class="input-surface mt-1 w-full" placeholder="10, 15, 19" />
            </label>
            <label class="text-xs text-slate-500">Timezone
              <input v-model="prefs.timezone" class="input-surface mt-1 w-full" placeholder="Europe/Berlin" />
            </label>
            <label class="text-xs text-slate-500 sm:col-span-2">Tell the scorer what you want and avoid
              <textarea v-model="prefs.candidate_notes" rows="3" class="input-surface mt-1 w-full" placeholder="e.g. Prefer product companies, remote-friendly; avoid agencies and on-call-heavy roles." />
            </label>
          </div>
          <button type="button" class="btn-primary mt-3" :disabled="busy" @click="savePrefs">Save preferences</button>
        </section>

        <section>
          <h3 class="mb-2 font-semibold text-slate-200">4. LinkedIn cookie (optional) {{ stepDone.linkedin ? '✓' : '' }}</h3>
          <p class="mb-2 text-xs text-slate-500">
            Guest scraping works without this. A <code>li_at</code> cookie unlocks full descriptions. Automated access may
            violate LinkedIn's terms; use at your own risk and keep volumes low. See docs/LINKEDIN.md.
          </p>
          <div class="flex gap-2">
            <input v-model="linkedinCookie" type="password" autocomplete="off" placeholder="li_at value" class="input-surface flex-1" />
            <button type="button" class="btn-primary" :disabled="busy" @click="saveLinkedin">Save &amp; test</button>
          </div>
        </section>

        <section>
          <h3 class="mb-2 font-semibold text-slate-200">5. Phone notifications (optional) {{ stepDone.ntfy ? '✓' : '' }}</h3>
          <button type="button" class="btn-ghost" :disabled="busy" @click="makeTopic">Generate private ntfy topic</button>
          <p v-if="ntfyTopic" class="mt-2 break-all text-xs text-amber-300">{{ ntfyTopic }}</p>
        </section>

        <section>
          <h3 class="mb-2 font-semibold text-slate-200">Health check</h3>
          <div class="flex gap-2">
            <button type="button" class="btn-ghost" :disabled="busy" @click="runHealth(false)">Quick check</button>
            <button type="button" class="btn-ghost" :disabled="busy" @click="runHealth(true)">Live check (calls Gemini/LinkedIn/ntfy)</button>
          </div>
          <ul v-if="health" class="mt-3 space-y-1 text-xs">
            <li v-for="c in health.checks" :key="c.name">
              <span :class="badge(c.status)" class="font-mono uppercase">{{ c.status }}</span>
              <span class="ml-2 text-slate-300">{{ c.name }}</span>
              <span class="ml-2 text-slate-500">{{ c.detail }}</span>
              <div v-if="c.fix && c.status !== 'pass'" class="ml-10 text-amber-300/80">→ {{ c.fix }}</div>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

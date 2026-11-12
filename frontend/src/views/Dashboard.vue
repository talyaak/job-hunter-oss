<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import type { Lead, ApplicationStatus, LeadCounts } from '../types/lead'
import type { Reject, RejectStage } from '../types/reject'
import type { UserProfile } from '../types/profile'
import { api } from '../api/client'
import {
  loadDashboardState,
  saveDashboardState,
  isDashboardDataFresh,
  loadLeadsCache,
  saveLeadsCache,
  loadRejectsCache,
  saveRejectsCache,
  loadUnscoredCache,
  saveUnscoredCache,
  restoreScrollAfterPaint,
  type DashboardTab,
} from '../composables/useDashboardState'
import LeadsTable from '../components/LeadsTable.vue'
import LeadCard from '../components/LeadCard.vue'
import RejectsTable from '../components/RejectsTable.vue'
import SyncButton from '../components/SyncButton.vue'
import ApplyKit from '../components/ApplyKit.vue'
import CoverLetterModal from '../components/CoverLetterModal.vue'
import LinkedinSearch from '../components/LinkedinSearch.vue'
import SetupPanel from '../components/SetupPanel.vue'
import { loadSharedPreferences, sharedPrefs } from '../composables/usePreferences'

const PAGE_SIZE = 30
const persisted = loadDashboardState()

const activeTab = ref<DashboardTab>(persisted.activeTab)
const leads = ref<Lead[]>([])
const leadsTotal = ref(0)
const leadCounts = ref<LeadCounts>({ total: 0, saved: 0, applied: 0, hidden: 0 })
const rejects = ref<Reject[]>([])
const unscored = ref<Reject[]>([])
const profile = ref<UserProfile | null>(null)
const statusFilter = ref<string>(persisted.statusFilter)
const rejectStage = ref<RejectStage | ''>(persisted.rejectStage as RejectStage | '')
const minScore = ref<number | ''>(persisted.minScore)
const maxScore = ref<number | ''>(persisted.maxScore)
const cvFile = ref<File | null>(null)
const profileFile = ref<File | null>(null)
const uploadMsg = ref('')
const uploadError = ref(false)
const loadingLeads = ref(false)
const loadingMore = ref(false)
const loadSentinel = ref<HTMLElement | null>(null)
const lastFetchedAt = ref(persisted.fetchedAt)
const rejectsFetchedAt = ref(0)
const unscoredFetchedAt = ref(0)
const applyLead = ref<Lead | null>(null)
const applyKitOpen = ref(false)
const coverLetterLead = ref<Lead | null>(null)
const coverLetterOpen = ref(false)
type BacklogAction = 'batch' | 'all' | 'dismiss'
const backlogAction = ref<BacklogAction | null>(null)
const backlogMsg = ref('')

let observer: IntersectionObserver | null = null

const stats = computed(() => leadCounts.value)
const hasMoreLeads = computed(() => leads.value.length < leadsTotal.value)
const profileReady = computed(() => profile.value?.has_cv)
const showSetup = ref(false)

async function maybeOpenSetup() {
  await loadSharedPreferences()
  try {
    const st = await api.getOnboardingStatus()
    if (!st.complete) showSetup.value = true
  } catch {
    /* gate or network issue: the AccessGate handles it */
  }
}

function onSetupChanged() {
  loadSharedPreferences()
  loadProfile()
}

function persistUi() {
  saveDashboardState({
    activeTab: activeTab.value,
    statusFilter: statusFilter.value,
    rejectStage: rejectStage.value,
    minScore: minScore.value,
    maxScore: maxScore.value,
    scrollY: window.scrollY,
  })
}

async function loadLeads(reset = true, background = false) {
  if (reset) {
    if (!background) {
      loadingLeads.value = true
      leads.value = []
    }
  } else {
    loadingMore.value = true
  }
  try {
    const res = await api.getLeads({
      status: statusFilter.value || undefined,
      offset: reset ? 0 : leads.value.length,
      limit: PAGE_SIZE,
    })
    if (reset) {
      leads.value = res.items
    } else {
      leads.value = [...leads.value, ...res.items]
    }
    leadsTotal.value = res.total
    if (res.counts) leadCounts.value = res.counts
    lastFetchedAt.value = Date.now()
    saveLeadsCache({
      statusFilter: statusFilter.value,
      items: leads.value,
      total: leadsTotal.value,
      counts: leadCounts.value,
      fetchedAt: lastFetchedAt.value,
    })
    persistUi()
  } finally {
    loadingLeads.value = false
    loadingMore.value = false
  }
}

function restoreLeadsFromCache(): boolean {
  const cache = loadLeadsCache(statusFilter.value)
  if (!cache) return false
  leads.value = cache.items as Lead[]
  leadsTotal.value = cache.total
  leadCounts.value = cache.counts
  lastFetchedAt.value = cache.fetchedAt
  return true
}

function openApplyKit(lead: Lead) {
  applyLead.value = lead
  applyKitOpen.value = true
  persistUi()
}

function openCoverLetter(lead: Lead) {
  coverLetterLead.value = lead
  coverLetterOpen.value = true
  applyKitOpen.value = false
}

function onApplyKitStatus(status: ApplicationStatus) {
  if (applyLead.value) onStatusChange(applyLead.value.id, status)
}

async function loadRejects() {
  const res = await api.getRejects({
    stage: rejectStage.value || undefined,
    min_score: minScore.value === '' ? undefined : Number(minScore.value),
    max_score: maxScore.value === '' ? undefined : Number(maxScore.value),
  })
  rejects.value = res.items
  rejectsFetchedAt.value = Date.now()
  saveRejectsCache(res.items)
  persistUi()
}

async function loadUnscored() {
  const res = await api.getRejects({ scored: false })
  unscored.value = res.items
  unscoredFetchedAt.value = Date.now()
  saveUnscoredCache(res.items)
  persistUi()
}

function restoreRejectsFromCache(): boolean {
  const cached = loadRejectsCache()
  if (!cached) return false
  rejects.value = cached.items as Reject[]
  rejectsFetchedAt.value = cached.fetchedAt
  return true
}

function restoreUnscoredFromCache(): boolean {
  const cached = loadUnscoredCache()
  if (!cached) return false
  unscored.value = cached.items as Reject[]
  unscoredFetchedAt.value = cached.fetchedAt
  return true
}

async function loadProfile() {
  profile.value = await api.getProfile()
}

async function onStatusChange(id: number, status: ApplicationStatus) {
  const idx = leads.value.findIndex((l) => l.id === id)
  const prev = idx >= 0 ? leads.value[idx].application_status : null
  if (idx >= 0) leads.value[idx].application_status = status

  const counts = { ...leadCounts.value }
  const statusKeys: ApplicationStatus[] = ['saved', 'applied', 'hidden']
  if (prev && statusKeys.includes(prev)) {
    counts[prev] = Math.max(0, counts[prev] - 1)
  }
  if (statusKeys.includes(status)) {
    counts[status] = counts[status] + 1
  }
  leadCounts.value = counts

  if (statusFilter.value && statusFilter.value !== status) {
    leads.value = leads.value.filter((l) => l.id !== id)
    leadsTotal.value = Math.max(0, leadsTotal.value - 1)
  }

  saveLeadsCache({
    statusFilter: statusFilter.value,
    items: leads.value,
    total: leadsTotal.value,
    counts: leadCounts.value,
    fetchedAt: lastFetchedAt.value,
  })

  try {
    await api.patchLead(id, { application_status: status })
  } catch {
    if (idx >= 0 && prev) leads.value[idx].application_status = prev
    await loadLeads(true, true)
  }
}

type BacklogTotals = Record<'processed' | 'leads_created' | 'scored_rejected' | 'hard_filtered' | 'dismissed' | 'deduped', number>

const BACKLOG_BATCH: Record<BacklogAction, number> = { batch: 50, all: 20, dismiss: 100 }
let backlogStopRequested = false

function backlogSummary(t: BacklogTotals, remaining: number, quotaStopped: boolean): string {
  const parts = [
    t.leads_created ? `${t.leads_created} new leads` : '',
    t.scored_rejected ? `${t.scored_rejected} scored & rejected` : '',
    t.hard_filtered ? `${t.hard_filtered} filtered` : '',
    t.dismissed ? `${t.dismissed} dismissed` : '',
    t.deduped ? `${t.deduped} duplicates` : '',
  ].filter(Boolean)
  const head = parts.length ? `Processed ${t.processed}: ${parts.join(', ')}.` : `Processed ${t.processed}.`
  return `${head} ${remaining} remaining.${quotaStopped ? ' Stopped — Gemini quota hit.' : ''}`
}

function stopBacklog() {
  backlogStopRequested = true
}

async function runBacklog(action: BacklogAction) {
  backlogMsg.value = ''
  backlogAction.value = action
  backlogStopRequested = false
  const dismiss = action === 'dismiss'
  const totals: BacklogTotals = { processed: 0, leads_created: 0, scored_rejected: 0, hard_filtered: 0, dismissed: 0, deduped: 0 }
  try {
    for (;;) {
      const res = await api.processUnscored(dismiss ? 'dismiss' : 'auto', BACKLOG_BATCH[action])
      for (const key of Object.keys(totals) as (keyof BacklogTotals)[]) totals[key] += res[key]
      backlogMsg.value = backlogSummary(totals, res.remaining, res.quota_stopped)
      sessionStorage.removeItem('jh_unscored_cache_v1')
      await loadUnscored()
      if (res.leads_created) await loadLeads(true, true)
      if (action === 'batch' || res.processed === 0 || res.remaining === 0 || res.quota_stopped) break
      if (backlogStopRequested) {
        backlogMsg.value += ' Stopped.'
        break
      }
    }
  } catch (e) {
    backlogMsg.value = e instanceof Error ? e.message : 'Backlog processing failed.'
  } finally {
    backlogAction.value = null
  }
}

async function onSynced() {
  await loadLeads(true)
  if (activeTab.value === 'rejects') await loadRejects()
  if (activeTab.value === 'unscored') await loadUnscored()
}

async function uploadProfile() {
  uploadMsg.value = ''
  uploadError.value = false
  try {
    profile.value = await api.uploadProfile(cvFile.value, profileFile.value)
    uploadMsg.value = 'Profile saved — ready to sync.'
  } catch (e) {
    uploadError.value = true
    uploadMsg.value = e instanceof Error ? e.message : 'Upload failed.'
  }
}

function setupObserver() {
  observer?.disconnect()
  if (!loadSentinel.value || activeTab.value !== 'leads') return
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMoreLeads.value && !loadingLeads.value && !loadingMore.value) {
        loadLeads(false)
      }
    },
    { rootMargin: '200px' },
  )
  observer.observe(loadSentinel.value)
}

function onVisibilityChange() {
  if (document.visibilityState !== 'visible') {
    persistUi()
    return
  }
  const scrollY = loadDashboardState().scrollY
  restoreScrollAfterPaint(scrollY)

  if (activeTab.value === 'leads') {
    restoreLeadsFromCache()
    if (!isDashboardDataFresh(lastFetchedAt.value)) loadLeads(true, true)
  } else if (activeTab.value === 'rejects') {
    restoreRejectsFromCache()
    if (!isDashboardDataFresh(rejectsFetchedAt.value)) loadRejects()
  } else if (activeTab.value === 'unscored') {
    restoreUnscoredFromCache()
    if (!isDashboardDataFresh(unscoredFetchedAt.value)) loadUnscored()
  }
}

function onPageShow(event: PageTransitionEvent) {
  if (!event.persisted) return
  const scrollY = loadDashboardState().scrollY
  if (activeTab.value === 'leads') restoreLeadsFromCache()
  else if (activeTab.value === 'rejects') restoreRejectsFromCache()
  else if (activeTab.value === 'unscored') restoreUnscoredFromCache()
  restoreScrollAfterPaint(scrollY)
}

watch(activeTab, (tab) => {
  persistUi()
  if (tab === 'rejects') {
    if (!restoreRejectsFromCache()) loadRejects()
  } else if (tab === 'unscored') {
    if (!restoreUnscoredFromCache()) loadUnscored()
  }
  nextTick(setupObserver)
})

watch(statusFilter, () => loadLeads(true))

watch(() => leads.value.length, () => nextTick(setupObserver))

onMounted(async () => {
  if (activeTab.value === 'leads') {
    const cached = restoreLeadsFromCache()
    if (!cached || !isDashboardDataFresh(lastFetchedAt.value)) {
      if (!cached) await loadLeads(true)
      else loadLeads(true, true)
    }
  } else if (activeTab.value === 'rejects') {
    if (!restoreRejectsFromCache()) await loadRejects()
  } else if (activeTab.value === 'unscored' && !restoreUnscoredFromCache()) {
    await loadUnscored()
  }
  if (!restoreUnscoredFromCache()) loadUnscored()
  await loadProfile()
  maybeOpenSetup()

  await nextTick()
  restoreScrollAfterPaint(persisted.scrollY)
  setupObserver()
  window.addEventListener('pageshow', onPageShow)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('scroll', persistUi, { passive: true })
})

onUnmounted(() => {
  observer?.disconnect()
  window.removeEventListener('pageshow', onPageShow)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('scroll', persistUi)
})
</script>

<template>
  <div class="relative mx-auto max-w-7xl px-4 py-8 sm:px-6">
    <header class="animate-fade-up mb-8 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="mb-2 inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-amber-300/90">
          <span class="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse-ring" />
          Lead aggregator
        </div>
        <h1 class="font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Job <span class="bg-gradient-to-r from-amber-300 to-amber-500 bg-clip-text text-transparent">Hunter</span>
        </h1>
        <p class="mt-1.5 text-sm text-slate-500">AI-filtered roles scoring {{ sharedPrefs.score_threshold }}%+ · synced {{ sharedPrefs.sweeps_per_day }}× daily</p>
      </div>
      <div class="flex items-center gap-3">
        <button type="button" class="btn-ghost" @click="showSetup = true">Setup &amp; settings</button>
        <SyncButton @synced="onSynced" />
      </div>
    </header>
    <SetupPanel v-if="showSetup" @close="showSetup = false" @changed="onSetupChanged" />

    <div class="animate-fade-up mb-6 grid grid-cols-3 gap-3 sm:gap-4" style="animation-delay: 80ms">
      <div class="glass-panel px-4 py-3">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Leads</p>
        <p class="font-display mt-1 text-2xl font-bold tabular-nums text-white">{{ stats.total }}</p>
      </div>
      <div class="glass-panel px-4 py-3">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Saved</p>
        <p class="font-display mt-1 text-2xl font-bold tabular-nums text-amber-300">{{ stats.saved }}</p>
      </div>
      <div class="glass-panel px-4 py-3">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Applied</p>
        <p class="font-display mt-1 text-2xl font-bold tabular-nums text-teal-300">{{ stats.applied }}</p>
      </div>
    </div>

    <section class="animate-fade-up glass-panel-strong mb-6 p-5 sm:p-6" style="animation-delay: 120ms">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="font-display text-sm font-semibold text-slate-200">Your profile</h2>
        <span
          class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
          :class="profileReady ? 'bg-teal-500/15 text-teal-300' : 'bg-amber-500/15 text-amber-300'"
        >{{ profileReady ? 'Ready' : 'Required for sync' }}</span>
      </div>
      <div class="flex flex-col gap-4 sm:flex-row sm:items-end">
        <label class="flex-1 text-xs text-slate-500">
          <span class="mb-1.5 block font-medium text-slate-400">CV (PDF)</span>
          <input type="file" accept=".pdf" class="input-surface w-full" @change="cvFile = ($event.target as HTMLInputElement).files?.[0] ?? null" />
        </label>
        <label class="flex-1 text-xs text-slate-500">
          <span class="mb-1.5 block font-medium text-slate-400">LinkedIn Profile (PDF)</span>
          <input type="file" accept=".pdf" class="input-surface w-full" @change="profileFile = ($event.target as HTMLInputElement).files?.[0] ?? null" />
        </label>
        <button type="button" class="btn-primary shrink-0" @click="uploadProfile">Upload</button>
      </div>
      <p v-if="profile?.has_cv || profile?.has_profile" class="mt-3 text-xs text-teal-400/90">
        {{ profile?.cv_filename ? `✓ ${profile.cv_filename}` : '' }}
        {{ profile?.has_profile ? ' · Profile loaded' : '' }}
      </p>
      <p v-if="uploadMsg" class="mt-2 text-xs" :class="uploadError ? 'text-red-400' : 'text-slate-400'">{{ uploadMsg }}</p>
    </section>

    <div class="animate-fade-up mb-4 flex flex-wrap items-center gap-3" style="animation-delay: 160ms">
      <div class="flex rounded-lg border border-white/10 bg-white/[0.03] p-0.5">
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="activeTab === 'leads' ? 'bg-amber-500/20 text-amber-200' : 'text-slate-500 hover:text-slate-300'"
          @click="activeTab = 'leads'"
        >Leads</button>
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="activeTab === 'rejects' ? 'bg-amber-500/20 text-amber-200' : 'text-slate-500 hover:text-slate-300'"
          @click="activeTab = 'rejects'"
        >Rejected<span class="hidden sm:inline"> (scored &lt;{{ sharedPrefs.score_threshold }}%)</span></button>
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="activeTab === 'unscored' ? 'bg-amber-500/20 text-amber-200' : 'text-slate-500 hover:text-slate-300'"
          @click="activeTab = 'unscored'"
        >Awaiting score{{ unscored.length ? ` (${unscored.length})` : '' }}</button>
        <button
          type="button"
          class="rounded-md px-3 py-1.5 text-xs font-medium transition-colors"
          :class="activeTab === 'search' ? 'bg-amber-500/20 text-amber-200' : 'text-slate-500 hover:text-slate-300'"
          @click="activeTab = 'search'"
        >LinkedIn search</button>
      </div>

      <template v-if="activeTab === 'leads'">
        <select v-model="statusFilter" class="select-surface">
          <option value="saved">Saved</option>
          <option value="applied">Applied</option>
          <option value="hidden">Hidden</option>
          <option value="">All statuses</option>
        </select>
        <span class="text-xs text-slate-600">
          {{ leads.length }} of {{ leadsTotal }} result{{ leadsTotal === 1 ? '' : 's' }}
        </span>
      </template>

      <template v-else-if="activeTab === 'rejects'">
        <select v-model="rejectStage" class="select-surface" @change="loadRejects()">
          <option value="">All stages</option>
          <option value="llm_score">Below threshold</option>
          <option value="embedding_filter">Similarity filter</option>
          <option value="gemma_filter">Gemma hard-no</option>
          <option value="location">Location filter</option>
          <option value="hard_title">Title filter</option>
          <option value="dedupe">Duplicate</option>
        </select>
        <label class="flex items-center gap-1.5 text-xs text-slate-500">
          Min %
          <input
            v-model.number="minScore"
            type="number"
            min="0"
            max="100"
            placeholder="0"
            class="input-surface w-16 px-2 py-1 text-xs"
            @change="loadRejects()"
          />
        </label>
        <label class="flex items-center gap-1.5 text-xs text-slate-500">
          Max %
          <input
            v-model.number="maxScore"
            type="number"
            min="0"
            max="100"
            placeholder="84"
            class="input-surface w-16 px-2 py-1 text-xs"
            @change="loadRejects()"
          />
        </label>
        <span class="text-xs text-slate-600">{{ rejects.length }} scored below {{ sharedPrefs.score_threshold }}%</span>
      </template>

      <template v-else-if="activeTab === 'unscored'">
        <span class="text-xs text-amber-400/80">{{ unscored.length }} never scored (quota / parse errors)</span>
        <button
          type="button"
          class="btn-primary px-3 py-1.5 text-xs"
          :disabled="backlogAction !== null || unscored.length === 0"
          @click="runBacklog('batch')"
        >{{ backlogAction === 'batch' ? 'Processing…' : 'Process backlog' }}</button>
        <button
          type="button"
          class="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
          :disabled="backlogAction !== null || unscored.length === 0"
          @click="runBacklog('all')"
        >{{ backlogAction === 'all' ? 'Processing all…' : 'Process all' }}</button>
        <button
          type="button"
          class="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
          :disabled="backlogAction !== null || unscored.length === 0"
          @click="runBacklog('dismiss')"
        >{{ backlogAction === 'dismiss' ? 'Dismissing…' : 'Dismiss all' }}</button>
        <button
          v-if="backlogAction === 'all' || backlogAction === 'dismiss'"
          type="button"
          class="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-amber-300 hover:text-amber-100"
          @click="stopBacklog"
        >Stop</button>
      </template>
    </div>

    <template v-if="activeTab === 'leads'">
      <div v-if="loadingLeads && leads.length === 0" class="glass-panel flex justify-center py-16 text-sm text-slate-500">
        Loading leads…
      </div>
      <div v-else-if="leads.length === 0" class="animate-fade-up glass-panel flex flex-col items-center justify-center py-16 text-center" style="animation-delay: 200ms">
        <p class="font-display text-lg font-semibold text-slate-300">No leads yet</p>
        <p class="mt-1 max-w-sm text-sm text-slate-500">
          {{ statusFilter === 'saved' ? 'No saved jobs — mark leads as saved or switch status filter.' : 'Upload your profile and hit Sync Now to scrape and filter matching roles.' }}
        </p>
      </div>
      <template v-else>
        <LeadsTable
          :leads="leads"
          @update-status="onStatusChange"
          @apply="openApplyKit"
          @cover-letter="openCoverLetter"
        />
        <LeadCard
          :leads="leads"
          @update-status="onStatusChange"
          @apply="openApplyKit"
          @cover-letter="openCoverLetter"
        />
        <div ref="loadSentinel" class="py-4 text-center text-xs text-slate-600">
          <span v-if="loadingMore">Loading more…</span>
          <span v-else-if="hasMoreLeads">Scroll for more</span>
        </div>
      </template>
    </template>

    <template v-else-if="activeTab === 'rejects'">
      <div v-if="rejects.length === 0" class="glass-panel flex flex-col items-center justify-center py-16 text-center">
        <p class="font-display text-lg font-semibold text-slate-300">No rejected jobs match filters</p>
        <p class="mt-1 max-w-sm text-sm text-slate-500">Try widening the score range or clearing the stage filter.</p>
      </div>
      <RejectsTable v-else :rejects="rejects" mode="default" />
    </template>

    <template v-else-if="activeTab === 'unscored'">
      <p class="mb-3 text-xs text-amber-400/70">
        These jobs were scraped but never scored — usually Gemini API quota (429) or JSON parse failures.
        This is not the same as <strong class="font-medium text-slate-400">Rejected</strong> (roles scored below {{ sharedPrefs.score_threshold }}%).
        Use <strong class="font-medium text-slate-400">Process backlog</strong> to hard-filter irrelevant roles and score one batch of 50.
        <strong class="font-medium text-slate-400">Process all</strong> repeats that until nothing is left, the Gemini quota runs out, or you press Stop.
        <strong class="font-medium text-slate-400">Dismiss all</strong> discards the whole list.
      </p>
      <p v-if="backlogMsg" class="mb-3 text-xs text-slate-400">{{ backlogMsg }}</p>
      <div v-if="unscored.length === 0" class="glass-panel flex flex-col items-center justify-center py-16 text-center">
        <p class="font-display text-lg font-semibold text-slate-300">Nothing awaiting score</p>
        <p class="mt-1 max-w-sm text-sm text-slate-500">All scraped jobs were scored or filtered.</p>
      </div>
      <RejectsTable v-else :rejects="unscored" mode="unscored" />
    </template>

    <LinkedinSearch v-show="activeTab === 'search'" @lead-saved="loadLeads(true, true)" />

    <ApplyKit
      :lead="applyLead"
      :open="applyKitOpen"
      @close="applyKitOpen = false"
      @cover-letter="applyLead && openCoverLetter(applyLead)"
      @set-status="onApplyKitStatus"
    />
    <CoverLetterModal
      :lead="coverLetterLead"
      :open="coverLetterOpen"
      @close="coverLetterOpen = false"
    />
  </div>
</template>

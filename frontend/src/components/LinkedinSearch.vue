<script setup lang="ts">
import { sharedPrefs } from '../composables/usePreferences'
import { ref, computed, watch, onUnmounted } from 'vue'
import type { ApplicationStatus } from '../types/lead'
import type {
  LinkedinSearchFiltersParams,
  LinkedinSearchHistoryEntry,
  LinkedinSearchItem,
  LinkedinSearchResponse,
} from '../types/search'
import { api } from '../api/client'
import { formatPostedDate } from '../utils/formatPostedDate'
import {
  clearLegacyLinkedinFilters,
  isSameSearch,
  loadLinkedinView,
  readLegacyLinkedinFilters,
  storeLinkedinView,
} from '../utils/recentSearches'
import type { SearchQuery } from '../utils/recentSearches'

const emit = defineEmits<{ 'lead-saved': [] }>()

const POSTED_OPTIONS = [
  { hours: 2, label: 'Past 2 hours' },
  { hours: 24, label: 'Past 24 hours' },
  { hours: 168, label: 'Past week' },
  { hours: 720, label: 'Past month' },
]
const SORT_OPTIONS = [
  { key: 'newest', label: 'Newest first', compare: byDate(-1) },
  { key: 'oldest', label: 'Oldest first', compare: byDate(1) },
  { key: 'company-asc', label: 'Company A–Z', compare: byText('company', 1) },
  { key: 'company-desc', label: 'Company Z–A', compare: byText('company', -1) },
  { key: 'title-asc', label: 'Title A–Z', compare: byText('job_title', 1) },
  { key: 'title-desc', label: 'Title Z–A', compare: byText('job_title', -1) },
]

// Undated jobs sink to the end in both date directions.
function byDate(direction: 1 | -1) {
  return (a: LinkedinSearchItem, b: LinkedinSearchItem) => {
    if (!a.date_posted || !b.date_posted) return Number(!a.date_posted) - Number(!b.date_posted)
    return direction * a.date_posted.localeCompare(b.date_posted)
  }
}

function byText(field: 'company' | 'job_title', direction: 1 | -1) {
  return (a: LinkedinSearchItem, b: LinkedinSearchItem) =>
    direction * a[field].localeCompare(b[field], undefined, { sensitivity: 'base' })
}

const HOUR_LABEL_WINDOW_MS = 48 * 60 * 60 * 1000
const HOUR_LABEL_PACING_MS = 500
const LINKEDIN_JOB_ID = /\/jobs\/view\/(\d+)/

const savedView = loadLinkedinView()
const term = ref(savedView?.form.term ?? '')
const place = ref(savedView?.form.location ?? sharedPrefs.search_location)
const hours = ref(savedView?.form.hours ?? 168)
const active = ref<SearchQuery | null>(savedView?.active ?? null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saveError = ref('')
const historyError = ref('')
const result = ref<LinkedinSearchResponse | null>(null)
const fetchedAt = ref('')
const newUrls = ref<string[] | null>(null)
const hourLabels = ref<Record<string, string>>({})
const recent = ref<LinkedinSearchHistoryEntry[]>([])
const ignoreText = ref('')
const removedKeys = ref<string[]>([])
const filtersLoaded = ref(false)
const filtersError = ref('')
const sortKey = ref(SORT_OPTIONS.find((o) => o.key === savedView?.sort)?.key ?? SORT_OPTIONS[0].key)
let latestRequest = 0

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function resultKey(item: LinkedinSearchItem) {
  return LINKEDIN_JOB_ID.exec(item.job_url)?.[1] ?? item.job_url
}

function isIgnored(item: LinkedinSearchItem, patterns: RegExp[]) {
  return patterns.some((pattern) => pattern.test(item.job_title) || pattern.test(item.company))
}

const removedSet = computed(() => new Set(removedKeys.value))
const ignorePatterns = computed(() =>
  ignoreText.value
    .split(',')
    .map((word) => word.trim())
    .filter(Boolean)
    .map((word) => new RegExp(`(?<![\\p{L}\\p{N}])${escapeRegExp(word)}(?![\\p{L}\\p{N}])`, 'iu')),
)
const visibleItems = computed(() =>
  (result.value?.items ?? []).filter(
    (item) => !removedSet.value.has(resultKey(item)) && !isIgnored(item, ignorePatterns.value),
  ),
)
const hiddenCount = computed(() => (result.value?.items.length ?? 0) - visibleItems.value.length)
const newVisibleCount = computed(() => {
  if (!newUrls.value) return null
  const fresh = new Set(newUrls.value)
  return visibleItems.value.filter((item) => fresh.has(item.job_url)).length
})
const sortedItems = computed(() => {
  const option = SORT_OPTIONS.find((o) => o.key === sortKey.value) ?? SORT_OPTIONS[0]
  return [...visibleItems.value].sort(option.compare)
})

const FILTERS_SAVE_DELAY_MS = 400
let savedFilters: string | null = null
let filtersTimer: ReturnType<typeof setTimeout> | null = null
let filtersQueue: Promise<void> = Promise.resolve()

function filtersParams(): LinkedinSearchFiltersParams {
  return { ignore_text: ignoreText.value, removed_keys: removedKeys.value }
}

function saveFilters() {
  if (filtersTimer) clearTimeout(filtersTimer)
  filtersTimer = null
  filtersQueue = filtersQueue.then(async () => {
    const params = filtersParams()
    const snapshot = JSON.stringify(params)
    if (snapshot === savedFilters) return
    try {
      await api.saveLinkedinSearchFilters(params)
      savedFilters = snapshot
      filtersError.value = ''
    } catch (e) {
      filtersError.value = e instanceof Error ? e.message : 'Could not save your ignore words.'
    }
  })
}

function scheduleFiltersSave() {
  if (savedFilters === null) return
  if (filtersTimer) clearTimeout(filtersTimer)
  filtersTimer = setTimeout(saveFilters, FILTERS_SAVE_DELAY_MS)
}

watch([ignoreText, removedKeys], scheduleFiltersSave)

function removeResult(item: LinkedinSearchItem) {
  const key = resultKey(item)
  if (!removedSet.value.has(key)) removedKeys.value = [...removedKeys.value, key]
}

function restoreRemoved() {
  removedKeys.value = []
}

const canSearch = computed(() => term.value.trim().length >= 2 && !loading.value)

function windowLabel(postedHours: number) {
  return POSTED_OPTIONS.find((o) => o.hours === postedHours)?.label ?? ''
}

const resultPosted = computed(() => windowLabel(result.value?.hours ?? 0).toLowerCase())

function formatFetchedAt(iso: string) {
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function withinHourWindow(postedDate: string) {
  return Date.now() - new Date(`${postedDate}T00:00:00`).getTime() < HOUR_LABEL_WINDOW_MS
}

async function fillHourLabels(seq: number, items: LinkedinSearchItem[]) {
  for (const item of items) {
    if (seq !== latestRequest) return
    if (!item.date_posted || !withinHourWindow(item.date_posted)) continue
    try {
      const { posted_ago } = await api.linkedinPostedAgo(item.job_url)
      if (seq === latestRequest && posted_ago) hourLabels.value[item.job_url] = posted_ago
    } catch {
      /* keep the date label */
    }
    await new Promise((resolve) => setTimeout(resolve, HOUR_LABEL_PACING_MS))
  }
}

function showEntry(entry: LinkedinSearchHistoryEntry) {
  const seq = ++latestRequest
  error.value = ''
  saveError.value = ''
  loading.value = false
  result.value = entry.response
  fetchedAt.value = entry.fetched_at
  newUrls.value = entry.new_urls
  hourLabels.value = {}
  active.value = { term: entry.term, location: entry.location, hours: entry.hours }
  fillHourLabels(seq, entry.response.items)
}

function restoreActive() {
  const query = active.value
  const entry = query ? recent.value.find((e) => isSameSearch(e, query)) : undefined
  if (entry) showEntry(entry)
  else active.value = null
}

async function loadHistory() {
  try {
    recent.value = await api.getLinkedinSearchHistory()
  } catch (e) {
    historyError.value = e instanceof Error ? e.message : 'Could not load recent searches.'
  }
}

async function loadFilters() {
  try {
    let stored = await api.getLinkedinSearchFilters()
    const legacy = stored.updated_at === null ? readLegacyLinkedinFilters() : null
    if (legacy) stored = await api.saveLinkedinSearchFilters(legacy)
    clearLegacyLinkedinFilters()
    ignoreText.value = stored.ignore_text
    removedKeys.value = stored.removed_keys
    savedFilters = JSON.stringify(filtersParams())
    filtersLoaded.value = true
  } catch (e) {
    filtersError.value = e instanceof Error ? e.message : 'Could not load your ignore words.'
  }
}

const historyReady = Promise.all([loadHistory(), loadFilters()]).then(() => {
  if (!loading.value && !result.value) restoreActive()
})

watch([term, place, hours, active, sortKey], () => {
  storeLinkedinView({
    form: { term: term.value, location: place.value, hours: hours.value },
    active: active.value,
    sort: sortKey.value,
  })
})

async function runSearch(query: SearchQuery) {
  if (query.term.length < 2) return
  const seq = ++latestRequest
  loading.value = true
  error.value = ''
  saveError.value = ''
  historyError.value = ''
  result.value = null
  hourLabels.value = {}
  newUrls.value = null
  try {
    const res = await api.searchLinkedin({ q: query.term, location: query.location, hours: query.hours })
    if (seq !== latestRequest) return
    result.value = res
    fetchedAt.value = new Date().toISOString()
    active.value = { term: res.query, location: res.location, hours: res.hours }
    fillHourLabels(seq, res.items)
    recordSearch(seq, res)
  } catch (e) {
    if (seq === latestRequest) error.value = e instanceof Error ? e.message : 'LinkedIn search failed.'
  } finally {
    if (seq === latestRequest) loading.value = false
  }
}

async function recordSearch(seq: number, res: LinkedinSearchResponse) {
  await historyReady
  try {
    const entries = await api.recordLinkedinSearch(res)
    recent.value = entries
    if (seq === latestRequest) newUrls.value = entries[0]?.new_urls ?? null
  } catch (e) {
    if (seq === latestRequest) historyError.value = e instanceof Error ? e.message : 'Could not save this search to history.'
  }
}

function search() {
  runSearch({ term: term.value.trim(), location: place.value.trim(), hours: hours.value })
}

function refresh() {
  if (result.value) runSearch({ term: result.value.query, location: result.value.location, hours: result.value.hours })
}

function openRecent(entry: LinkedinSearchHistoryEntry) {
  term.value = entry.term
  place.value = entry.location
  hours.value = entry.hours
  showEntry(entry)
}

async function clearRecent() {
  latestRequest++
  loading.value = false
  recent.value = []
  result.value = null
  active.value = null
  historyError.value = ''
  try {
    await api.clearLinkedinSearchHistory()
  } catch (e) {
    historyError.value = e instanceof Error ? e.message : 'Could not clear recent searches.'
  }
}

function withLeadStatus(items: LinkedinSearchItem[], jobUrl: string, status: ApplicationStatus) {
  return items.map((item) => (item.job_url === jobUrl ? { ...item, lead_status: status } : item))
}

function applyLeadStatus(jobUrl: string, status: ApplicationStatus) {
  if (result.value) result.value = { ...result.value, items: withLeadStatus(result.value.items, jobUrl, status) }
  recent.value = recent.value.map((entry) => ({
    ...entry,
    response: { ...entry.response, items: withLeadStatus(entry.response.items, jobUrl, status) },
  }))
}

async function saveJob(item: LinkedinSearchItem, status: 'saved' | 'applied') {
  if (saving.value) return
  saving.value = true
  saveError.value = ''
  try {
    const res = await api.saveLinkedinJob({
      job_title: item.job_title,
      company: item.company,
      job_url: item.job_url,
      date_posted: item.date_posted,
      status,
    })
    applyLeadStatus(item.job_url, res.application_status)
    emit('lead-saved')
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : 'Could not save this job.'
  } finally {
    saving.value = false
  }
}

onUnmounted(() => {
  latestRequest++
  if (filtersTimer) saveFilters()
})
</script>

<template>
  <section class="animate-fade-up space-y-4">
    <form class="glass-panel flex flex-col gap-3 p-4 sm:flex-row sm:flex-wrap sm:items-end" @submit.prevent="search">
      <label class="flex flex-col gap-1.5 text-xs text-slate-500 sm:min-w-[16rem] sm:flex-1">
        <span class="font-medium text-slate-400">Search term</span>
        <input
          v-model="term"
          type="text"
          maxlength="120"
          placeholder="e.g. Full Stack Developer"
          class="input-surface w-full"
        />
      </label>
      <label class="flex flex-col gap-1.5 text-xs text-slate-500 sm:w-56">
        <span class="font-medium text-slate-400">Location</span>
        <input v-model="place" type="text" maxlength="120" class="input-surface w-full" />
      </label>
      <label class="flex flex-col gap-1.5 text-xs text-slate-500">
        <span class="font-medium text-slate-400">Posted</span>
        <select v-model.number="hours" class="select-surface">
          <option v-for="o in POSTED_OPTIONS" :key="o.hours" :value="o.hours">{{ o.label }}</option>
        </select>
      </label>
      <button type="submit" class="btn-primary w-full sm:w-auto" :disabled="!canSearch">
        {{ loading ? 'Searching…' : 'Search' }}
      </button>
    </form>

    <div class="flex flex-col gap-3 sm:flex-row sm:items-end">
      <label class="flex flex-1 flex-col gap-1.5 text-xs text-slate-500">
        <span class="font-medium text-slate-400">Ignore titles or companies containing (comma-separated, whole words)</span>
        <textarea v-model="ignoreText" rows="3" maxlength="2000" placeholder="e.g. senior, intern, sales" class="input-surface w-full resize-y disabled:cursor-not-allowed disabled:opacity-50" :disabled="!filtersLoaded" />
      </label>
      <button
        v-if="removedKeys.length"
        type="button"
        class="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:border-amber-200/60 hover:text-amber-200"
        @click="restoreRemoved"
      >Restore {{ removedKeys.length }} removed</button>
    </div>
    <p v-if="filtersError" class="text-xs text-red-400">{{ filtersError }}</p>

    <div v-if="recent.length" class="flex flex-wrap items-center gap-2">
      <span class="text-xs text-slate-500">Recent</span>
      <button
        v-for="entry in recent"
        :key="`${entry.term}|${entry.location}|${entry.hours}`"
        type="button"
        class="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-amber-200/60 hover:text-amber-200"
        :title="`${entry.location} · fetched ${formatFetchedAt(entry.fetched_at)}`"
        @click="openRecent(entry)"
      >{{ entry.term }} · {{ windowLabel(entry.hours) }}</button>
      <button type="button" class="text-xs text-slate-500 hover:text-slate-300" @click="clearRecent">Clear</button>
    </div>

    <p v-if="error" class="text-xs text-red-400">{{ error }}</p>
    <div v-else-if="result" class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-xs text-slate-500">
      <p>
        {{ result.total }} result{{ result.total === 1 ? '' : 's' }} for "{{ result.query }}" · {{ resultPosted }} · fetched {{ formatFetchedAt(fetchedAt) }} · not scored
        <span v-if="hiddenCount > 0">· {{ hiddenCount }} hidden</span>
        <span v-if="newVisibleCount !== null">· {{ newVisibleCount }} new since last fetch</span>
      </p>
      <div class="flex flex-wrap items-center gap-2">
        <label class="flex items-center gap-2">
          <span>Sort</span>
          <select v-model="sortKey" class="select-surface">
            <option v-for="o in SORT_OPTIONS" :key="o.key" :value="o.key">{{ o.label }}</option>
          </select>
        </label>
        <button
          type="button"
          class="rounded-lg border border-slate-700 px-3 py-1 text-slate-300 hover:border-amber-200/60 hover:text-amber-200"
          @click="refresh"
        >Refresh new results</button>
      </div>
    </div>
    <p v-if="saveError" class="text-xs text-red-400">{{ saveError }}</p>
    <p v-if="historyError" class="text-xs text-red-400">{{ historyError }}</p>

    <div v-if="loading" class="glass-panel flex justify-center py-16 text-sm text-slate-500">
      Searching LinkedIn…
    </div>
    <div v-else-if="result && result.items.length === 0" class="glass-panel flex flex-col items-center justify-center py-16 text-center">
      <p class="font-display text-lg font-semibold text-slate-300">No jobs found</p>
      <p class="mt-1 max-w-sm text-sm text-slate-500">Try a broader term or a longer Posted window.</p>
    </div>
    <div v-else-if="result && visibleItems.length === 0" class="glass-panel flex flex-col items-center justify-center py-16 text-center">
      <p class="font-display text-lg font-semibold text-slate-300">All {{ result.items.length }} results are hidden</p>
      <p class="mt-1 max-w-sm text-sm text-slate-500">Your ignore words or removed results are hiding every match. Edit the ignore words or restore removed results.</p>
    </div>
    <ul v-else-if="result" class="space-y-2">
      <li
        v-for="(item, i) in sortedItems"
        :key="`${i}-${item.job_url}`"
        class="glass-panel animate-fade-up flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-4"
        :style="{ animationDelay: `${i * 30}ms` }"
      >
        <div class="min-w-0 flex-1">
          <a
            :href="item.job_url"
            target="_blank"
            rel="noopener noreferrer"
            class="font-medium text-slate-100 hover:text-amber-200"
          >{{ item.job_title }}</a>
          <span
            v-if="newUrls?.includes(item.job_url)"
            class="ml-2 rounded-full bg-amber-400/15 px-2 py-0.5 align-middle text-[10px] font-medium text-amber-200"
          >New</span>
          <p class="mt-0.5 truncate text-xs text-slate-500">
            {{ item.company }} · {{ item.location || 'Location not listed' }}
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-2 sm:shrink-0">
          <span
            class="text-xs tabular-nums text-slate-500"
            :title="formatPostedDate(item.date_posted).title"
          >{{ hourLabels[item.job_url] || formatPostedDate(item.date_posted).label }}</span>
          <span
            v-if="item.lead_status === 'applied'"
            class="rounded-md border border-teal-500/50 bg-teal-500/15 px-2 py-0.5 text-xs font-medium text-teal-300"
          >Applied</span>
          <template v-else>
            <span
              v-if="item.lead_status"
              class="rounded-md border border-slate-600/50 bg-slate-600/15 px-2 py-0.5 text-xs text-slate-300"
            >{{ item.lead_status === 'hidden' ? 'Hidden in leads' : 'In leads' }}</span>
            <button
              v-if="item.lead_status !== 'saved'"
              type="button"
              class="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-amber-200/60 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="saving"
              @click="saveJob(item, 'saved')"
            >Save to leads</button>
            <button
              type="button"
              class="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-300 hover:border-amber-200/60 hover:text-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="saving"
              @click="saveJob(item, 'applied')"
            >Mark applied</button>
          </template>
          <button
            type="button"
            class="rounded-lg px-2 py-1 text-xs text-slate-500 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!filtersLoaded"
            @click="removeResult(item)"
          >Remove</button>
        </div>
      </li>
    </ul>
    <div v-else-if="!error" class="glass-panel flex flex-col items-center justify-center py-16 text-center">
      <p class="font-display text-lg font-semibold text-slate-300">LinkedIn job search</p>
      <p class="mt-1 max-w-sm text-sm text-slate-500">Nothing is scored; save a job to add it to your leads.</p>
    </div>
  </section>
</template>

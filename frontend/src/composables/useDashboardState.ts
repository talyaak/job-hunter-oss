import type { LeadCounts } from '../types/lead'
import type { Reject } from '../types/reject'

const STORAGE_KEY = 'jh_dashboard_v2'
const CACHE_KEY = 'jh_leads_cache_v1'
const REJECTS_CACHE_KEY = 'jh_rejects_cache_v1'
const UNSCORED_CACHE_KEY = 'jh_unscored_cache_v1'
const STALE_MS = 300_000

export type DashboardTab = 'leads' | 'rejects' | 'unscored' | 'search'

export interface DashboardPersistedState {
  activeTab: DashboardTab
  statusFilter: string
  rejectStage: string
  minScore: number | ''
  maxScore: number | ''
  scrollY: number
  fetchedAt: number
}

export interface LeadsCachePayload {
  statusFilter: string
  items: unknown[]
  total: number
  counts: LeadCounts
  fetchedAt: number
}

interface ListCachePayload {
  items: unknown[]
  fetchedAt: number
}

const defaults: DashboardPersistedState = {
  activeTab: 'leads',
  statusFilter: 'saved',
  rejectStage: '',
  minScore: '',
  maxScore: 84,
  scrollY: 0,
  fetchedAt: 0,
}

function readStorage(): DashboardPersistedState {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...defaults }
    return { ...defaults, ...JSON.parse(raw) }
  } catch {
    return { ...defaults }
  }
}

export function loadDashboardState(): DashboardPersistedState {
  const fromHash = parseRouteHash()
  return { ...readStorage(), ...fromHash }
}

export function saveDashboardState(state: Partial<DashboardPersistedState>) {
  const merged = { ...readStorage(), ...state, fetchedAt: Date.now() }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(merged))
  writeRouteHash(merged)
}

export function isDashboardDataFresh(fetchedAt: number): boolean {
  return fetchedAt > 0 && Date.now() - fetchedAt < STALE_MS
}

export function saveLeadsCache(payload: LeadsCachePayload) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(payload))
  } catch {
    /* quota */
  }
}

export function loadLeadsCache(statusFilter: string): LeadsCachePayload | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const cache = JSON.parse(raw) as LeadsCachePayload
    if (cache.statusFilter !== statusFilter) return null
    if (!isDashboardDataFresh(cache.fetchedAt)) return null
    return cache
  } catch {
    return null
  }
}

export function saveRejectsCache(items: Reject[]) {
  try {
    const payload: ListCachePayload = { items, fetchedAt: Date.now() }
    sessionStorage.setItem(REJECTS_CACHE_KEY, JSON.stringify(payload))
  } catch {
    /* quota */
  }
}

export function loadRejectsCache(): ListCachePayload | null {
  try {
    const raw = sessionStorage.getItem(REJECTS_CACHE_KEY)
    if (!raw) return null
    const cache = JSON.parse(raw) as ListCachePayload
    if (!isDashboardDataFresh(cache.fetchedAt)) return null
    return cache
  } catch {
    return null
  }
}

export function saveUnscoredCache(items: Reject[]) {
  try {
    const payload: ListCachePayload = { items, fetchedAt: Date.now() }
    sessionStorage.setItem(UNSCORED_CACHE_KEY, JSON.stringify(payload))
  } catch {
    /* quota */
  }
}

export function loadUnscoredCache(): ListCachePayload | null {
  try {
    const raw = sessionStorage.getItem(UNSCORED_CACHE_KEY)
    if (!raw) return null
    const cache = JSON.parse(raw) as ListCachePayload
    if (!isDashboardDataFresh(cache.fetchedAt)) return null
    return cache
  } catch {
    return null
  }
}

function statusToken(status: string) {
  return status || '_all'
}

function statusFromToken(token: string) {
  return token === '_all' ? '' : token
}

export function parseRouteHash(): Partial<DashboardPersistedState> {
  const hash = window.location.hash.replace(/^#/, '')
  if (!hash.startsWith('/')) return {}
  const parts = hash.slice(1).split('/')
  const tab = parts[0] as DashboardTab
  if (!['leads', 'rejects', 'unscored', 'search'].includes(tab)) return {}
  const out: Partial<DashboardPersistedState> = { activeTab: tab }
  if (parts[1]) out.statusFilter = statusFromToken(parts[1])
  return out
}

export function writeRouteHash(state: DashboardPersistedState) {
  const status = state.activeTab === 'leads' ? `/${statusToken(state.statusFilter)}` : ''
  const next = `#/${state.activeTab}${status}`
  if (window.location.hash !== next) {
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}${next}`)
  }
}

export function restoreScrollAfterPaint(y: number) {
  if (y <= 0) return
  requestAnimationFrame(() => {
    window.scrollTo(0, y)
    requestAnimationFrame(() => window.scrollTo(0, y))
  })
}

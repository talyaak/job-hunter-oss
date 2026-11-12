import type { LinkedinSearchFiltersParams } from '../types/search'

export interface SearchQuery {
  term: string
  location: string
  hours: number
}

export interface LinkedinView {
  form: SearchQuery
  active: SearchQuery | null
  sort?: string
}

const VIEW_KEY = 'jh_linkedin_view'
const LEGACY_FILTERS_KEY = 'jh_linkedin_filters'

export function isSameSearch(a: SearchQuery, b: SearchQuery) {
  return (
    a.term.toLowerCase() === b.term.toLowerCase() &&
    a.location.toLowerCase() === b.location.toLowerCase() &&
    a.hours === b.hours
  )
}

function isSearchQuery(value: unknown): value is SearchQuery {
  if (typeof value !== 'object' || value === null) return false
  const v = value as Record<string, unknown>
  return typeof v.term === 'string' && typeof v.location === 'string' && typeof v.hours === 'number'
}

export function loadLinkedinView(): LinkedinView | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(VIEW_KEY) ?? 'null')
    if (typeof parsed !== 'object' || parsed === null) return null
    const { form, active, sort } = parsed as Record<string, unknown>
    if (!isSearchQuery(form)) return null
    return { form, active: isSearchQuery(active) ? active : null, sort: typeof sort === 'string' ? sort : undefined }
  } catch {
    return null
  }
}

export function storeLinkedinView(view: LinkedinView) {
  try {
    localStorage.setItem(VIEW_KEY, JSON.stringify(view))
  } catch {
    /* storage unavailable or full */
  }
}

export function readLegacyLinkedinFilters(): LinkedinSearchFiltersParams | null {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(LEGACY_FILTERS_KEY) ?? 'null')
    if (typeof parsed !== 'object' || parsed === null) return null
    const { ignoreText, removedKeys } = parsed as Record<string, unknown>
    const ignore_text = typeof ignoreText === 'string' ? ignoreText : ''
    const removed_keys = Array.isArray(removedKeys) ? removedKeys.filter((k): k is string => typeof k === 'string') : []
    return ignore_text.trim() || removed_keys.length ? { ignore_text, removed_keys } : null
  } catch {
    return null
  }
}

export function clearLegacyLinkedinFilters() {
  try {
    localStorage.removeItem(LEGACY_FILTERS_KEY)
  } catch {
    /* storage unavailable */
  }
}

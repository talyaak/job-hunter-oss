import { reactive } from 'vue'
import { api } from '../api/client'
import type { Preferences } from '../types/preferences'

// Shared, lazily loaded singleton so badges and headers agree with the saved thresholds.
export const sharedPrefs = reactive({
  loaded: false,
  score_threshold: 80,
  high_score_threshold: 90,
  search_location: '',
  sweeps_per_day: 3,
})

export async function loadSharedPreferences(): Promise<Preferences | null> {
  try {
    const p = await api.getPreferences()
    sharedPrefs.score_threshold = p.score_threshold
    sharedPrefs.high_score_threshold = p.high_score_threshold
    sharedPrefs.search_location = p.search_location
    sharedPrefs.sweeps_per_day = p.cron_hours.length
    sharedPrefs.loaded = true
    return p
  } catch {
    return null
  }
}

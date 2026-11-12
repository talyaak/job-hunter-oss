import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api/client'
import type { SyncLiveState } from '../types/sync'

const DEFAULT: SyncLiveState = {
  phase: 'idle',
  run_id: null,
  raw_count: 0,
  passed_count: 0,
  processed: 0,
  hard_rejected: 0,
  deduped: 0,
  llm_rejected: 0,
  current_job: null,
  error_message: null,
}

export function useSyncWs(onComplete?: () => void) {
  const state = ref<SyncLiveState>({ ...DEFAULT })
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${proto}//${location.host}/api/sync/ws`)
    ws.onopen = () => { connected.value = true }
    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }
    ws.onmessage = (ev) => {
      const data = JSON.parse(ev.data) as SyncLiveState
      state.value = data
      if (data.phase === 'completed' || data.phase === 'failed') {
        onComplete?.()
      }
    }
  }

  async function refreshStatus() {
    try {
      const status = await api.getSyncStatus()
      if (status.current) {
        state.value = {
          ...state.value,
          phase: 'filtering',
          run_id: status.current.id,
          raw_count: status.current.raw_count,
          passed_count: status.current.passed_count,
        }
        return
      }
      if (status.last_completed) {
        state.value = {
          ...state.value,
          phase: 'completed',
          run_id: status.last_completed.id,
          raw_count: status.last_completed.raw_count,
          passed_count: status.last_completed.passed_count,
          processed: status.last_completed.raw_count,
        }
      }
    } catch {
      /* offline */
    }
  }

  onMounted(() => {
    connect()
    refreshStatus()
  })
  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  const isRunning = () => ['scraping', 'enriching', 'filtering'].includes(state.value.phase)

  return { state, connected, isRunning, refreshStatus }
}

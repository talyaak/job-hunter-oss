// All API calls go through the service worker (host permissions apply here, page CORS does not).
const DEFAULT_API = 'http://localhost:8000'

async function settings() {
  const sync = await chrome.storage.sync.get(['apiBase'])
  // The access token is a secret: keep it on this device only (storage.local), never synced.
  const local = await chrome.storage.local.get(['accessToken'])
  return {
    base: (sync.apiBase || DEFAULT_API).replace(/\/$/, ''),
    token: local.accessToken || '',
  }
}

async function apiFetch(path) {
  const { base, token } = await settings()
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const res = await fetch(`${base}${path}`, { headers })
  if (res.status === 401) throw new Error('Access token missing or wrong. Set it in the extension popup.')
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res
}

function toBase64(buffer) {
  let binary = ''
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'fetchApplyProfile') {
    apiFetch('/api/profile/apply')
      .then(async (res) => sendResponse({ ok: true, profile: await res.json() }))
      .catch((err) => sendResponse({ ok: false, error: String(err.message || err) }))
    return true
  }
  if (msg.type === 'fetchResume') {
    apiFetch('/api/profile/cv')
      .then(async (res) => sendResponse({ ok: true, base64: toBase64(await res.arrayBuffer()) }))
      .catch((err) => sendResponse({ ok: false, error: String(err.message || err) }))
    return true
  }
})

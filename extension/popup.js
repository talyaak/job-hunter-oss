const DEFAULT_API = 'http://localhost:8000'
const apiInput = document.getElementById('apiBase')
const tokenInput = document.getElementById('token')
const status = document.getElementById('status')

chrome.storage.sync.get(['apiBase'], (stored) => {
  apiInput.value = stored.apiBase || DEFAULT_API
})
chrome.storage.local.get(['accessToken'], (stored) => {
  tokenInput.value = stored.accessToken || ''
})

async function ensureHostPermission(url) {
  try {
    const origin = new URL(url).origin + '/*'
    if (origin.startsWith('http://localhost') || origin.startsWith('http://127.0.0.1')) return true
    return await chrome.permissions.request({ origins: [origin] })
  } catch {
    return false
  }
}

apiInput.addEventListener('change', async () => {
  const value = apiInput.value.trim() || DEFAULT_API
  const granted = await ensureHostPermission(value)
  chrome.storage.sync.set({ apiBase: value })
  status.textContent = granted ? 'Saved.' : 'Saved, but access to that host was not granted.'
})

tokenInput.addEventListener('change', () => {
  chrome.storage.local.set({ accessToken: tokenInput.value.trim() })
  status.textContent = 'Token saved on this device.'
})

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { api, UNAUTHORIZED_EVENT } from '../api/client'

const ready = ref(false)
const authenticated = ref(false)
const token = ref('')
const error = ref('')
const busy = ref(false)

// The private link looks like https://<tunnel>/?t=<token>. Exchange it for an HttpOnly cookie, then
// remove it from the address bar so it does not linger in history or screenshots.
async function consumeLinkToken(): Promise<void> {
  const url = new URL(window.location.href)
  const t = url.searchParams.get('t')
  if (!t) return
  url.searchParams.delete('t')
  window.history.replaceState({}, '', url.pathname + (url.search || '') + url.hash)
  try {
    await api.createSession(t)
  } catch {
    error.value = 'That link is invalid or expired.'
  }
}

async function check() {
  try {
    const status = await api.getAuthStatus()
    authenticated.value = status.authenticated
  } catch {
    authenticated.value = false
  }
  ready.value = true
}

async function submit() {
  if (!token.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    await api.createSession(token.value.trim())
    token.value = ''
    await check()
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Invalid token'
  } finally {
    busy.value = false
  }
}

function onUnauthorized() {
  authenticated.value = false
}

onMounted(async () => {
  window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  await consumeLinkToken()
  await check()
})
onUnmounted(() => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized))
</script>

<template>
  <slot v-if="ready && authenticated" />
  <div v-else-if="ready" class="mx-auto flex min-h-screen max-w-md items-center px-4">
    <form class="glass-panel-strong w-full p-6" @submit.prevent="submit">
      <h1 class="font-display text-xl font-bold text-white">Private access</h1>
      <p class="mt-2 text-sm text-slate-400">
        This Job Hunter instance is protected. Open the private link that was sent to your ntfy topic or printed in the
        terminal, or paste your access token (<code class="text-amber-300">ACCESS_TOKEN</code> in <code>.env</code>).
      </p>
      <input
        v-model="token"
        type="password"
        autocomplete="off"
        placeholder="Access token"
        class="input-surface mt-4 w-full"
      />
      <p v-if="error" class="mt-2 text-xs text-red-400">{{ error }}</p>
      <button type="submit" class="btn-primary mt-4 w-full" :disabled="busy">{{ busy ? 'Checking...' : 'Unlock' }}</button>
    </form>
  </div>
</template>

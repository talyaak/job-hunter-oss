<script setup lang="ts">
import type { PlatformSource } from '../types/lead'

const props = defineProps<{ source: PlatformSource }>()

const styles: Record<PlatformSource, string> = {
  linkedin: 'bg-[#0a66c2]/20 text-[#7ab8f5] border-[#0a66c2]/40',
  indeed: 'bg-[#2164f3]/20 text-[#93b4ff] border-[#2164f3]/40',
  glassdoor: 'bg-[#0caa41]/20 text-[#6ee7a0] border-[#0caa41]/40',
  google: 'bg-[#ea4335]/20 text-[#fca5a5] border-[#ea4335]/40',
}

const labels: Record<PlatformSource, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  glassdoor: 'Glassdoor',
  google: 'Google',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
    :class="styles[props.source]"
  >{{ labels[props.source] }}</span>
</template>

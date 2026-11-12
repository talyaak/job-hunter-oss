<script setup lang="ts">
import type { Lead, ApplicationStatus } from '../types/lead'
import { formatPostedDate } from '../utils/formatPostedDate'
import MatchReasonTooltip from './MatchReasonTooltip.vue'
import PlatformBadge from './PlatformBadge.vue'
import ScoreBadge from './ScoreBadge.vue'

defineProps<{ leads: Lead[] }>()
const emit = defineEmits<{
  'update-status': [id: number, status: ApplicationStatus]
  apply: [lead: Lead]
  'cover-letter': [lead: Lead]
}>()

const statuses: ApplicationStatus[] = ['hidden', 'saved', 'applied']

const statusStyles: Record<ApplicationStatus, string> = {
  saved: 'text-amber-300',
  applied: 'text-teal-300',
  hidden: 'text-slate-500',
}

function workplaceIcon(w: string) {
  if (w === 'remote') return '⌂'
  if (w === 'hybrid') return '◐'
  if (w === 'onsite') return '▣'
  return '?'
}

function workplaceLabel(w: string) {
  return w === 'unknown' ? 'Unknown' : w
}

function companyInfo(lead: Lead): string {
  const size = lead.company_size !== 'Unknown' ? lead.company_size : null
  const vertical = lead.product_vertical !== 'Unknown' ? lead.product_vertical : null
  if (!size && !vertical) return '—'
  return [size, vertical].filter(Boolean).join(' · ')
}

function contactLabel(lead: Lead): string {
  if (lead.contact_name) return lead.contact_name
  if (lead.contact_email) return lead.contact_email
  if (lead.contact_linkedin_url) return 'LinkedIn'
  return '—'
}

function contactTitle(lead: Lead): string | undefined {
  const parts = [lead.contact_name, lead.contact_email, lead.contact_linkedin_url].filter(Boolean)
  return parts.length ? parts.join(' · ') : undefined
}
</script>

<template>
  <div class="hidden rounded-2xl border border-white/[0.08] lg:block">
    <div class="overflow-x-auto">
      <table class="w-full min-w-[1100px] text-left text-sm">
        <thead>
          <tr class="border-b border-white/[0.06] bg-white/[0.02] text-[10px] font-semibold uppercase tracking-widest text-slate-500">
            <th class="px-4 py-3.5">Posted</th>
            <th class="min-w-[12rem] px-4 py-3.5">Role</th>
            <th class="px-4 py-3.5">Source</th>
            <th class="px-4 py-3.5">Apply via</th>
            <th class="px-4 py-3.5">Type</th>
            <th class="px-4 py-3.5">Work</th>
            <th class="min-w-[8rem] px-4 py-3.5">Company</th>
            <th class="min-w-[8rem] px-4 py-3.5">Contact</th>
            <th class="min-w-[6rem] px-4 py-3.5">Match</th>
            <th class="px-4 py-3.5">Score</th>
            <th class="px-4 py-3.5">Status</th>
            <th class="px-4 py-3.5">Apply</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(lead, i) in leads"
            :key="lead.id"
            class="group border-b border-white/[0.04] transition-colors hover:bg-amber-500/[0.03]"
            :style="{ animationDelay: `${i * 40}ms` }"
          >
            <td class="whitespace-nowrap px-4 py-3.5 text-xs tabular-nums text-slate-500">
              <span :title="formatPostedDate(lead.date_posted).title">{{ formatPostedDate(lead.date_posted).label }}</span>
            </td>
            <td class="px-4 py-3.5">
              <a
                :href="lead.job_url"
                target="_blank"
                rel="noopener noreferrer"
                class="font-medium text-slate-100 transition-colors group-hover:text-amber-200"
              >{{ lead.job_title }}</a>
              <div class="mt-0.5 text-xs text-slate-500">{{ lead.company }}</div>
            </td>
            <td class="px-4 py-3.5"><PlatformBadge :source="lead.platform_source" /></td>
            <td class="px-4 py-3.5 text-xs text-slate-400">{{ lead.submission_method }}</td>
            <td class="px-4 py-3.5 text-xs">
              <span :class="lead.recruiter_type === 'direct' ? 'text-slate-300' : 'text-slate-500'">
                {{ lead.recruiter_type === 'direct' ? 'Direct' : '3rd Party' }}
              </span>
            </td>
            <td class="px-4 py-3.5">
              <span class="inline-flex items-center gap-1 text-xs text-slate-400">
                <span class="text-slate-600">{{ workplaceIcon(lead.workplace_type) }}</span>
                {{ workplaceLabel(lead.workplace_type) }}
              </span>
            </td>
            <td class="px-4 py-3.5 text-xs text-slate-400">{{ companyInfo(lead) }}</td>
            <td class="max-w-[10rem] px-4 py-3.5 text-[11px] text-slate-500">
              <a
                v-if="lead.contact_email"
                :href="`mailto:${lead.contact_email}`"
                :title="contactTitle(lead)"
                class="block truncate text-teal-400/90 hover:text-teal-300"
              >{{ contactLabel(lead) }}</a>
              <a
                v-else-if="lead.contact_linkedin_url"
                :href="lead.contact_linkedin_url"
                target="_blank"
                rel="noopener noreferrer"
                :title="contactTitle(lead)"
                class="block truncate text-slate-400 hover:text-slate-300"
              >{{ contactLabel(lead) }}</a>
              <span v-else :title="contactTitle(lead)" class="block truncate">{{ contactLabel(lead) }}</span>
            </td>
            <td class="px-4 py-3.5">
              <MatchReasonTooltip
                :reason="lead.match_reason"
                :stack-match="lead.stack_match"
                :evaluation="lead.match_evaluation"
                :score="lead.relevance_score"
              />
            </td>
            <td class="px-4 py-3.5"><ScoreBadge :score="lead.relevance_score" /></td>
            <td class="px-4 py-3.5">
              <select
                :value="lead.application_status"
                class="select-surface text-xs capitalize"
                :class="statusStyles[lead.application_status]"
                @change="emit('update-status', lead.id, ($event.target as HTMLSelectElement).value as ApplicationStatus)"
              >
                <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
              </select>
            </td>
            <td class="px-4 py-3.5">
              <div class="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  class="rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] font-medium text-amber-200 hover:bg-amber-500/20"
                  @click="emit('apply', lead)"
                >
                  Apply
                </button>
                <button
                  type="button"
                  class="rounded-md border border-teal-500/30 bg-teal-500/10 px-2.5 py-1 text-[11px] font-medium text-teal-200 hover:bg-teal-500/20"
                  @click="emit('cover-letter', lead)"
                >
                  Letter
                </button>
                <button
                  type="button"
                  class="rounded-md border px-2.5 py-1 text-[11px] font-medium transition-colors"
                  :class="lead.application_status === 'applied' ? 'border-teal-400/50 bg-teal-500/25 text-teal-100' : 'border-white/10 text-slate-300 hover:bg-white/5'"
                  @click="emit('update-status', lead.id, lead.application_status === 'applied' ? 'saved' : 'applied')"
                >
                  {{ lead.application_status === 'applied' ? 'Applied ✓' : 'Mark applied' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

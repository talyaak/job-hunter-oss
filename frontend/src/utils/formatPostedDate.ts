export interface PostedDateDisplay {
  label: string
  title?: string
}

export function formatPostedDate(dateStr: string | null): PostedDateDisplay {
  if (!dateStr) return { label: '—' }

  const posted = new Date(`${dateStr}T12:00:00`)
  if (Number.isNaN(posted.getTime())) return { label: '—' }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const postedDay = new Date(posted)
  postedDay.setHours(0, 0, 0, 0)
  const diffDays = Math.round((today.getTime() - postedDay.getTime()) / 86_400_000)

  const short = posted.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: posted.getFullYear() !== today.getFullYear() ? 'numeric' : undefined,
  })

  if (diffDays < 0) return { label: short }
  if (diffDays === 0) return { label: 'Today', title: short }
  if (diffDays === 1) return { label: 'Yesterday', title: short }
  if (diffDays < 7) return { label: `${diffDays} days ago`, title: short }
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return { label: weeks === 1 ? '1 week ago' : `${weeks} weeks ago`, title: short }
  }
  return { label: short }
}

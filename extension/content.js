(() => {
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const ATS_HOSTS = ['greenhouse.io', 'lever.co', 'comeet.co', 'comeet.com', 'myworkdayjobs.com']

  function detectAts() {
    const host = location.hostname
    return ATS_HOSTS.find((h) => host.includes(h)) || null
  }

  function setValue(el, value) {
    if (!el || value == null || value === '') return false
    el.focus()
    el.value = value
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }

  function pick(selectors) {
    for (const sel of selectors) {
      const el = document.querySelector(sel)
      if (el) return el
    }
    return null
  }

  function fillCommon(p) {
    const map = [
      [['#first_name', 'input[name*="first_name" i]', 'input[id*="first_name" i]'], p.first_name],
      [['#last_name', 'input[name*="last_name" i]', 'input[id*="last_name" i]'], p.last_name],
      [['#email', 'input[type="email"]', 'input[name*="email" i]'], p.email],
      [['#phone', 'input[type="tel"]', 'input[name*="phone" i]'], p.phone],
      [['input[name*="location" i]', 'input[id*="location" i]', '#location'], p.location],
      [['input[name*="linkedin" i]', 'input[id*="linkedin" i]'], p.linkedin_url],
      [['input[name*="github" i]', 'input[id*="github" i]', 'input[name*="website" i]'], p.github_url || p.portfolio_url],
    ]
    let filled = 0
    for (const [sels, val] of map) {
      if (setValue(pick(sels), val)) filled += 1
    }
    return filled
  }

  async function attachResume() {
    const input = pick(['input[type="file"]', 'input[name*="resume" i]'])
    if (!input) return false
    try {
      const resp = await chrome.runtime.sendMessage({ type: 'fetchResume' })
      if (!resp?.ok) return false
      const bytes = Uint8Array.from(atob(resp.base64), (c) => c.charCodeAt(0))
      const file = new File([bytes], 'resume.pdf', { type: 'application/pdf' })
      const dt = new DataTransfer()
      dt.items.add(file)
      input.files = dt.files
      input.dispatchEvent(new Event('change', { bubbles: true }))
      return true
    } catch {
      return false
    }
  }

  function panel() {
    let root = document.getElementById('jh-apply-panel')
    if (root) return root
    root = document.createElement('div')
    root.id = 'jh-apply-panel'
    root.style.cssText =
      'position:fixed;bottom:16px;right:16px;z-index:2147483646;font:13px system-ui,sans-serif;color:#e2e8f0;background:#0f172a;border:1px solid #f59e0b55;border-radius:12px;padding:12px 14px;box-shadow:0 8px 32px #0008;max-width:280px'
    document.documentElement.appendChild(root)
    return root
  }

  function showPanel(html) {
    panel().innerHTML = html
  }

  async function runFill() {
    const ats = detectAts()
    if (!ats) {
      showPanel('<strong>Job Hunter</strong><p style="margin:8px 0 0;font-size:12px;color:#94a3b8">Unsupported page. Use Greenhouse, Lever, or Comeet.</p>')
      return
    }

    showPanel('<strong>Job Hunter</strong><p style="margin:8px 0 0;font-size:12px;color:#94a3b8">Loading profile…</p>')

    const resp = await chrome.runtime.sendMessage({ type: 'fetchApplyProfile' })
    if (!resp?.ok) {
      showPanel(`<strong>Job Hunter</strong><p style="margin:8px 0 0;font-size:12px;color:#f87171">${esc(resp?.error || 'Could not load profile')}</p>`)
      return
    }

    const p = resp.profile
    const preview = [
      p.full_name && `Name: ${esc(p.full_name)}`,
      p.email && `Email: ${esc(p.email)}`,
      p.phone && `Phone: ${esc(p.phone)}`,
    ]
      .filter(Boolean)
      .join('<br>')

    showPanel(`
      <strong>Job Hunter · ${ats.split('.')[0]}</strong>
      <p style="margin:8px 0;font-size:12px;color:#94a3b8;line-height:1.4">${preview || 'Profile fields empty — set APPLY_* in .env or upload CV.'}</p>
      <button id="jh-fill-btn" style="margin-right:6px;padding:6px 10px;border:0;border-radius:8px;background:#f59e0b;color:#0f172a;font-weight:600;cursor:pointer">Fill form</button>
      <button id="jh-close-btn" style="padding:6px 10px;border:1px solid #334155;border-radius:8px;background:transparent;color:#94a3b8;cursor:pointer">Close</button>
      <p style="margin:8px 0 0;font-size:10px;color:#64748b">Review fields before submitting — autofill never clicks Submit.</p>
    `)

    document.getElementById('jh-close-btn')?.addEventListener('click', () => document.getElementById('jh-apply-panel')?.remove())
    document.getElementById('jh-fill-btn')?.addEventListener('click', async () => {
      const n = fillCommon(p)
      const resume = p.has_resume_file ? await attachResume() : false
      showPanel(`<strong>Job Hunter</strong><p style="margin:8px 0 0;font-size:12px;color:#6ee7b7">Filled ${n} field${n === 1 ? '' : 's'}${resume ? ' + resume' : ''}. Review and submit manually.</p>`)
    })
  }

  const ats = detectAts()
  if (!ats) return

  const fab = document.createElement('button')
  fab.textContent = 'JH Fill'
  fab.title = 'Job Hunter — fill application form'
  fab.style.cssText =
    'position:fixed;bottom:16px;right:16px;z-index:2147483645;padding:10px 14px;border:0;border-radius:999px;background:#f59e0b;color:#0f172a;font:600 12px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 16px #0006'
  fab.addEventListener('click', runFill)
  document.documentElement.appendChild(fab)
})()

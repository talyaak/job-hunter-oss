function pdfEscape(text: string): string {
  return text.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)')
}

function wrapLine(text: string, max = 88): string[] {
  const words = text.split(/\s+/)
  const lines: string[] = []
  let line = ''
  for (const w of words) {
    const next = line ? `${line} ${w}` : w
    if (next.length > max && line) {
      lines.push(line)
      line = w
    } else {
      line = next
    }
  }
  if (line) lines.push(line)
  return lines
}

export function downloadCoverLetterPdf(opts: {
  filename: string
  heading: string
  subheading: string
  body: string
}) {
  const margin = 72
  const pageH = 792
  const lineH = 14
  let y = pageH - margin

  const content: string[] = []
  const add = (size: number, text: string, gap = lineH) => {
    content.push('BT', `/F1 ${size} Tf`, `1 0 0 1 ${margin} ${y} Tm`, `(${pdfEscape(text)}) Tj`, 'ET')
    y -= gap
  }

  add(14, opts.heading, 20)
  add(11, opts.subheading, 22)

  for (const para of opts.body.split(/\n\s*\n/)) {
    const trimmed = para.trim()
    if (!trimmed) continue
    for (const line of wrapLine(trimmed)) {
      if (y < margin + lineH) break
      add(11, line, lineH)
    }
    y -= 6
  }

  const stream = content.join('\n')
  const objs = [
    '1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
    '2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj',
    '3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj',
    `4 0 obj << /Length ${stream.length} >> stream\n${stream}\nendstream endobj`,
    '5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
  ]

  let pdf = '%PDF-1.4\n'
  const offsets: number[] = [0]
  for (const obj of objs) {
    offsets.push(pdf.length)
    pdf += `${obj}\n`
  }
  const xref = pdf.length
  pdf += `xref\n0 ${objs.length + 1}\n`
  pdf += '0000000000 65535 f \n'
  for (let i = 1; i <= objs.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`
  }
  pdf += `trailer << /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`

  const blob = new Blob([pdf], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = opts.filename
  a.click()
  URL.revokeObjectURL(url)
}

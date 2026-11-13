// accent-insensitive, lower-case (same rules as norm_text in the database)
export const norm = (s) =>
  String(s ?? '').toLowerCase().replace(/œ/g, 'oe').normalize('NFD').replace(/[\u0300-\u036f]/g, '')

const hasWord = (text, w) => new RegExp(`(^|[^a-z0-9])${w}([^a-z0-9]|$)`).test(text)

// Deliberately small. This is a hint, never a substitute for the dentist's check.
const CLASSES = [
  {
    label: 'pénicillines',
    history: ['penicilline', 'penicillines', 'betalactamine', 'betalactamines', 'beta-lactamine', 'beta lactamine'],
    drugs: ['amoxicilline', 'ampicilline', 'oxacilline', 'cloxacilline', 'penicilline', 'clavulanique'],
  },
  {
    label: 'anti-inflammatoires (AINS)',
    history: ['ains', 'anti-inflammatoire', 'anti-inflammatoires', 'anti inflammatoire', 'aspirine'],
    drugs: ['ibuprofene', 'ketoprofene', 'naproxene', 'diclofenac', 'flurbiprofene', 'nimesulide',
            'acide acetylsalicylique', 'aspirine'],
  },
]

export function allergyWarnings(history, lines) {
  const h = norm(history)
  if (!h.trim()) return []
  const out = []
  for (const l of lines ?? []) {
    if (!l.name?.trim()) continue
    const hay = norm(`${l.name} ${l.ingredients ?? ''}`)
    // direct match on the first word of each ingredient (and of the name)
    const tokens = new Set(
      [l.name, ...String(l.ingredients ?? '').split(/[+;,/]/)]
        .map((s) => norm(s).trim().split(/\s+/)[0])
        .filter((t) => t && t.length >= 5)
    )
    for (const t of tokens) {
      if (h.includes(t)) out.push(`${l.name} : les antécédents du patient mentionnent « ${t} ».`)
    }
    for (const c of CLASSES) {
      const drugHit = c.drugs.some((d) => hay.includes(d))
      const histHit = c.history.some((w) => hasWord(h, w))
      if (drugHit && histHit) out.push(`${l.name} : les antécédents mentionnent une allergie ou intolérance possible (${c.label}).`)
    }
  }
  return [...new Set(out)]
}
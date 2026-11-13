import { useEffect, useRef, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { norm } from '../../lib/rx'

export default function MedSearch({ onPick }) {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const seq = useRef(0)

  useEffect(() => {
    const term = norm(q).trim().replace(/[%_\\]/g, ' ')
    if (term.length < 2) { setResults([]); return }
    const mine = ++seq.current
    const timer = setTimeout(async () => {
      const { data, error } = await supabase
        .from('medications')
        .select('id, name, form, ingredients, source')
        .ilike('search', `%${term}%`)
        .order('name')
        .limit(12)
      if (mine !== seq.current) return   // a newer search replaced this one
      if (error) setError(error.message)
      else { setError(''); setResults(data) }
    }, 250)
    return () => clearTimeout(timer)
  }, [q])

  function pick(m) {
    onPick(m)
    setQ(''); setResults([]); setOpen(false)
  }

  async function addCustom() {
    const name = q.trim()
    const { data, error } = await supabase
      .from('medications')
      .insert({ doctor_id: user.id, name, source: 'custom' })
      .select('id, name, form, ingredients')
      .single()
    if (error) return setError(error.message)
    pick(data)
  }

  const exact = results.some((r) => norm(r.name) === norm(q).trim())

  return (
    <div className="medsearch">
      <input
        className="clinic-input"
        placeholder="Rechercher un médicament (nom ou principe actif)…"
        value={q}
        onChange={(e) => { setQ(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        aria-label="Rechercher un médicament"
      />
      {error && <p className="clinic-error">{error}</p>}
      {open && q.trim().length >= 2 && (
        <ul className="medsearch-list">
          {results.map((m) => (
            <li key={m.id} onMouseDown={(e) => { e.preventDefault(); pick(m) }}>
              <strong>{m.name}</strong>
              <small>{[m.form, m.ingredients].filter(Boolean).join(' · ')}</small>
            </li>
          ))}
          {!exact && (
            <li className="medsearch-add" onMouseDown={(e) => { e.preventDefault(); addCustom() }}>
              + Ajouter « {q.trim()} » à mon catalogue
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
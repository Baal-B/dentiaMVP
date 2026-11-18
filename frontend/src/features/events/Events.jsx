import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { markEventsSeen } from './EventsBell'

const fmt = (d) => new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })

export default function Events() {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    markEventsSeen()
    const today = new Date().toISOString().slice(0, 10)
    supabase.from('events').select('id, title, starts_on, ends_on, location, url')
      .gte('starts_on', today).order('starts_on').then(({ data }) => setRows(data || []))
  }, [])

  return (
    <>
      <Link to="/" className="clinic-btn clinic-btn-ghost" style={{ marginBottom: 16 }}>
        <ArrowLeft size={16} /> Tableau de bord
      </Link>
      <h1 className="clinic-page-title">Événements et congrès</h1>
      <p className="clinic-page-sub">Détectés automatiquement par l'agent de veille sur des sources officielles.</p>
      {rows === null ? <p>Chargement…</p> : rows.length === 0 ? (
        <div className="clinic-card"><div className="clinic-empty">Aucun événement à venir pour le moment.</div></div>
      ) : (
        <div className="ev-list">
          {rows.map((e) => (
            <a key={e.id} className="ev-item" href={e.url} target="_blank" rel="noreferrer">
              <strong>{e.title}</strong>
              <span>
                {fmt(e.starts_on)}{e.ends_on && e.ends_on !== e.starts_on ? ` → ${fmt(e.ends_on)}` : ''}
                {e.location ? ` · ${e.location}` : ''}
              </span>
            </a>
          ))}
        </div>
      )}
    </>
  )
}
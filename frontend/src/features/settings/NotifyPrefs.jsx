import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'

export default function NotifyPrefs() {
  const [prefs, setPrefs] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    (async () => {
      const { data: u } = await supabase.auth.getUser()
      const { data, error } = await supabase.from('profiles')
        .select('notify_articles, notify_events').eq('id', u.user.id).single()
      if (error) setErr('Impossible de charger vos préférences.')
      else setPrefs(data)
    })()
  }, [])

  async function toggle(key) {
    const previous = prefs
    setPrefs({ ...prefs, [key]: !prefs[key] })
    setErr('')
    const { data: u } = await supabase.auth.getUser()
    const { error } = await supabase.from('profiles').update({ [key]: !previous[key] }).eq('id', u.user.id)
    if (error) { setPrefs(previous); setErr("Enregistrement impossible, réessayez.") }
  }

  if (!prefs) return err ? <p className="error">{err}</p> : null
  return (
    <section className="card" style={{ marginTop: 24 }}>
      <h2>Notifications</h2>
      <p className="muted">L'agent de veille tourne chaque jour et vous prévient selon ces choix.</p>
      <label style={{ display: 'flex', gap: 10, margin: '10px 0' }}>
        <input type="checkbox" checked={prefs.notify_articles} onChange={() => toggle('notify_articles')} />
        Recevoir les nouveaux articles (selon mes centres d'intérêt)
      </label>
      <label style={{ display: 'flex', gap: 10, margin: '10px 0' }}>
        <input type="checkbox" checked={prefs.notify_events} onChange={() => toggle('notify_events')} />
        Recevoir les congrès et événements
      </label>
      {err && <p className="error">{err}</p>}
    </section>
  )
}
import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { TOPICS } from '../../lib/topics'

export default function Settings() {
  const { user } = useAuth()
  const [name, setName] = useState('')
  const [interests, setInterests] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    supabase.from('profiles').select('full_name, interests').eq('id', user.id).single()
      .then(({ data, error }) => {
        if (error) setError(error.message)
        else { setName(data.full_name); setInterests(data.interests ?? []) }
        setLoading(false)
      })
  }, [user.id])

  const toggle = (key) => {
    setSaved(false)
    setInterests((list) => (list.includes(key) ? list.filter((k) => k !== key) : [...list, key]))
  }

  async function save(e) {
    e.preventDefault()
    setSaving(true); setError(''); setSaved(false)
    const { error } = await supabase
      .from('profiles').update({ full_name: name.trim(), interests }).eq('id', user.id)
    setSaving(false)
    if (error) return setError(error.message)
    setSaved(true)
  }

  if (loading) return <div className="clinic-loading">Chargement…</div>

  return (
    <>
      <h1 className="clinic-page-title">Paramètres</h1>
      <p className="clinic-page-sub">Votre profil et vos alertes de veille scientifique.</p>

      <form onSubmit={save}>
        <section className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Profil</h2></div>
          <div className="clinic-card-body">
            <div className="clinic-field" style={{ maxWidth: 420, marginBottom: 0 }}>
              <label htmlFor="name">Nom affiché</label>
              <input id="name" className="clinic-input" value={name} onChange={(e) => { setSaved(false); setName(e.target.value) }} />
            </div>
          </div>
        </section>

        <section className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Centres d'intérêt</h2></div>
          <div className="clinic-card-body">
            <p style={{ marginTop: 0, color: 'var(--clinic-muted)' }}>
              Vous serez notifié des nouveaux articles sur ces sujets.
            </p>
            <div className="clinic-topic-grid">
              {TOPICS.map((t) => (
                <label key={t.key} className={'clinic-topic' + (interests.includes(t.key) ? ' on' : '')}>
                  <input type="checkbox" checked={interests.includes(t.key)} onChange={() => toggle(t.key)} />
                  {t.label}
                </label>
              ))}
            </div>
          </div>
        </section>

        <button className="clinic-btn clinic-btn-primary" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </button>
        {saved && <span className="clinic-success" style={{ marginLeft: 12, display: 'inline-block' }}>Enregistré.</span>}
        {error && <p className="clinic-error">{error}</p>}
      </form>
    </>
  )
}
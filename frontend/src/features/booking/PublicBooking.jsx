import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const isoLocal = (offsetDays = 0) => {
  const d = new Date(Date.now() + offsetDays * 86400000)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const EMPTY = {
  first_name: '', last_name: '', phone: '', email: '',
  preferred_date: '', preferred_slot: 'any', note: '', consent: false, website: '',
}

export default function PublicBooking() {
  const { slug } = useParams()
  const [doctor, setDoctor] = useState(undefined)   // undefined = loading, null = invalid link
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    fetch(`${API}/public/doctors/${encodeURIComponent(slug)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setDoctor)
      .catch(() => setDoctor(null))
  }, [slug])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const res = await fetch(`${API}/public/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, slug, email: form.email || null }),
      })
      if (res.ok) { setDone(true); return }
      const body = await res.json().catch(() => ({}))
      setError(typeof body.detail === 'string' ? body.detail : 'Vérifiez les champs du formulaire.')
    } catch {
      setError('Connexion impossible. Réessayez ou appelez le cabinet.')
    } finally {
      setBusy(false)
    }
  }

  if (doctor === undefined) return <div className="clinic-loading">Chargement…</div>
  if (doctor === null) {
    return <div className="public-wrap"><div className="clinic-empty">Ce lien de réservation n'est pas valide.</div></div>
  }

  return (
    <div className="public-wrap">
      <section className="clinic-card">
        <div className="clinic-card-body">
          <header className="rx-head" style={{ marginBottom: 8 }}>
            <div className="rx-col">
              <strong className="rx-doctor">{doctor.full_name}</strong>
              {doctor.title_fr && <div>{doctor.title_fr}</div>}
            </div>
            <div className="rx-col rx-ar" dir="rtl" lang="ar">
              <strong className="rx-doctor">{doctor.name_ar}</strong>
              {doctor.title_ar && <div>{doctor.title_ar}</div>}
            </div>
          </header>
          <p style={{ margin: '8px 0 0', color: 'var(--clinic-muted)', whiteSpace: 'pre-line' }}>
            {[doctor.practice_address, doctor.practice_phone && `Tél. ${doctor.practice_phone}`].filter(Boolean).join('\n')}
          </p>
        </div>
      </section>

      {done ? (
        <section className="clinic-card" style={{ marginTop: 20 }}>
          <div className="clinic-card-body">
            <h2 className="clinic-card-title">Demande envoyée</h2>
            <p>Le cabinet vous contactera par téléphone pour fixer l'heure. <strong>Ce n'est pas encore un rendez-vous confirmé.</strong></p>
          </div>
        </section>
      ) : (
        <section className="clinic-card" style={{ marginTop: 20 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Demander un rendez-vous</h2></div>
          <div className="clinic-card-body">
            <form onSubmit={submit} className="clinic-form-grid">
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_first">Prénom</label>
                <input id="b_first" className="clinic-input" value={form.first_name} onChange={set('first_name')} maxLength={80} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_last">Nom</label>
                <input id="b_last" className="clinic-input" value={form.last_name} onChange={set('last_name')} maxLength={80} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_phone">Téléphone</label>
                <input id="b_phone" className="clinic-input" type="tel" value={form.phone} onChange={set('phone')} maxLength={30} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_email">E-mail (facultatif)</label>
                <input id="b_email" className="clinic-input" type="email" value={form.email} onChange={set('email')} maxLength={120} />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_date">Jour souhaité</label>
                <input id="b_date" className="clinic-input" type="date" min={isoLocal(0)} max={isoLocal(60)}
                  value={form.preferred_date} onChange={set('preferred_date')} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_slot">Moment de la journée</label>
                <select id="b_slot" className="clinic-input" value={form.preferred_slot} onChange={set('preferred_slot')}>
                  <option value="any">Peu importe</option>
                  <option value="morning">Matin</option>
                  <option value="afternoon">Après-midi</option>
                </select>
              </div>
              <div className="clinic-field clinic-col-12">
                <label htmlFor="b_note">Motif (facultatif)</label>
                <textarea id="b_note" className="clinic-input" value={form.note} onChange={set('note')} maxLength={300}
                  placeholder="Ex : contrôle, détartrage…" />
                <small style={{ color: 'var(--clinic-muted)' }}>
                  N'indiquez aucune information médicale. Pour une urgence, appelez directement le cabinet.
                </small>
              </div>

              {/* honeypot: invisible to people, tempting to bots */}
              <div className="hp" aria-hidden="true">
                <label htmlFor="b_site">Site web</label>
                <input id="b_site" tabIndex={-1} autoComplete="off" value={form.website} onChange={set('website')} />
              </div>

              <div className="clinic-col-12">
                <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <input type="checkbox" checked={form.consent} onChange={set('consent')} required style={{ marginTop: 4 }} />
                  J'accepte que le cabinet utilise ces informations pour me contacter au sujet de ma demande.
                </label>
              </div>
              {error && <p className="clinic-error clinic-col-12">{error}</p>}
              <div className="clinic-col-12">
                <button className="clinic-btn clinic-btn-primary" disabled={busy}>
                  {busy ? 'Envoi…' : 'Envoyer la demande'}
                </button>
              </div>
            </form>
          </div>
        </section>
      )}
    </div>
  )
}
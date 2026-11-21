import { useEffect, useState } from 'react'
import { useParams,Link } from 'react-router-dom'
import { MapPin, Phone, CheckCircle2, CalendarDays, PhoneCall, User } from 'lucide-react'
import logo from '../../assets/logo.png'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const isoLocal = (offsetDays = 0) => {
  const d = new Date(Date.now() + offsetDays * 86400000)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const EMPTY = {
  first_name: '', last_name: '', phone: '', email: '',
  preferred_date: '', preferred_slot: 'any', note: '', consent: false, website: '',
}

const SLOT = { any: 'à un moment qui vous convient', morning: 'le matin', afternoon: "l'après-midi" }
const initials = (name) =>
  (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join('')
const longDate = (iso) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })

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
      <Link to="/cabinets" className="clinic-back">← Tous les cabinets</Link>

      <section className="clinic-card bk-doctor">
        <div className="clinic-card-body">
          <div className="bk-doctor-top">
            <div className="cab-avatar bk-avatar" aria-hidden="true">{initials(doctor.full_name)}</div>
            <div className="bk-doctor-names">
              <strong className="bk-doctor-name">{doctor.full_name}</strong>
              {doctor.title_fr && <div className="rx-muted">{doctor.title_fr}</div>}
              {doctor.practice_name && <div className="cab-practice">{doctor.practice_name}</div>}
            </div>
            {doctor.name_ar && (
              <div dir="rtl" lang="ar" className="bk-doctor-ar">
                <strong>{doctor.name_ar}</strong>
                {doctor.title_ar && <div className="rx-muted">{doctor.title_ar}</div>}
              </div>
            )}
          </div>
          {(doctor.practice_address || doctor.practice_phone) && (
            <div className="bk-doctor-info">
              {doctor.practice_address && (
                <div className="cab-line"><MapPin size={16} aria-hidden="true" /><span style={{ whiteSpace: 'pre-line' }}>{doctor.practice_address}</span></div>
              )}
              {doctor.practice_phone && (
                <div className="cab-line"><Phone size={16} aria-hidden="true" /><span>{doctor.practice_phone}</span></div>
              )}
            </div>
          )}
        </div>
      </section>

      {done ? (
        <section className="clinic-card bk-done">
          <div className="clinic-card-body">
            <CheckCircle2 size={56} className="bk-done-icon" aria-hidden="true" />
            <h2>Merci {form.first_name}, votre demande est envoyée</h2>
            <p>
              Vous avez demandé un rendez-vous <strong>{longDate(form.preferred_date)}</strong>, {SLOT[form.preferred_slot]}.
            </p>
            <div className="clinic-notice">
              <strong>Ce n'est pas encore un rendez-vous confirmé.</strong>
              <span>Le cabinet vous appellera au {form.phone} pour fixer l'heure.</span>
            </div>
            <Link to="/cabinets" className="clinic-btn clinic-btn-ghost">Retour aux cabinets</Link>
          </div>
        </section>
      ) : (
        <section className="clinic-card" style={{ marginTop: 20 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Demander un rendez-vous</h2></div>
          <div className="clinic-card-body">
            <p className="bk-intro">Cela prend moins de 2 minutes. Aucun compte n'est nécessaire.</p>
            <form onSubmit={submit} className="clinic-form-grid">
              <div className="bk-step clinic-col-12"><User size={18} aria-hidden="true" /> Vos coordonnées</div>
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
                <small style={{ color: 'var(--clinic-muted)' }}>Le cabinet vous rappellera sur ce numéro.</small>
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="b_email">E-mail (facultatif)</label>
                <input id="b_email" className="clinic-input" type="email" value={form.email} onChange={set('email')} maxLength={120} />
              </div>

              <div className="bk-step clinic-col-12"><CalendarDays size={18} aria-hidden="true" /> Quand souhaitez-vous venir ?</div>
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

              <div className="bk-step clinic-col-12"><PhoneCall size={18} aria-hidden="true" /> Motif de la visite</div>
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
                <button className="clinic-btn clinic-btn-primary clinic-btn-block" disabled={busy}>
                  {busy ? 'Envoi…' : 'Envoyer la demande'}
                </button>
              </div>
            </form>
          </div>
        </section>
      )}

      <div className="bk-footer">
        <img src={logo} alt="DentIA" />
        <span>Réservation sécurisée avec DentIA</span>
      </div>
    </div>
  )
}
import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useActingId } from './useActingId'
import { fmtDate, fmtDateTime } from '../../lib/format'
import { norm } from '../../lib/rx'
import Pager from '../../components/Pager'
import { usePager } from '../../lib/usePager'

const SLOT = { morning: 'matin', afternoon: 'après-midi', any: 'peu importe' }
const STATUS = { confirmed: { text: 'Confirmée', cls: 'ok' }, declined: { text: 'Refusée', cls: 'danger' } }
const digits = (s) => String(s ?? '').replace(/\D/g, '')

function matchesOf(r, patients) {
  const want = norm(`${r.first_name} ${r.last_name}`).trim()
  const wantRev = norm(`${r.last_name} ${r.first_name}`).trim()
  const out = []
  for (const p of patients) {
    const full = norm(`${p.first_name} ${p.last_name}`).trim()
    const nameMatch = full === want || full === wantRev
    const phoneMatch = digits(p.phone).length >= 6 && digits(p.phone) === digits(r.phone)
    if (nameMatch || phoneMatch) out.push({ ...p, nameMatch })
  }
  return out
}

export default function Requests() {
  const actingId = useActingId()
  const [reqs, setReqs] = useState([])
  const [patients, setPatients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [openId, setOpenId] = useState(null)
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)

  const pending = reqs.filter((r) => r.status === 'pending').reverse()   // oldest first
  const handled = reqs.filter((r) => r.status !== 'pending')
  const pendingPager = usePager(pending, 8)
  const handledPager = usePager(handled, 8)

  async function load() {
    const [r, p] = await Promise.all([
      supabase.from('booking_requests')
        .select('id, first_name, last_name, phone, email, preferred_date, preferred_slot, note, status, decided_at, created_at')
        .order('created_at', { ascending: false }).limit(200),
      supabase.from('patients_basic')
        .select('id, first_name, last_name, phone').order('last_name').limit(1000),
    ])
    const err = r.error || p.error
    if (err) setError(err.message)
    else { setReqs(r.data); setPatients(p.data) }
    setLoading(false)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 60000)
    return () => clearInterval(t)
  }, [])

  function open(r) {
    setError('')
    if (openId === r.id) { setOpenId(null); return }
    const exact = matchesOf(r, patients).find((p) => p.nameMatch)
    setForm({
      patientId: exact?.id ?? 'new',
      start: `${r.preferred_date}T${r.preferred_slot === 'afternoon' ? '14:00' : '09:00'}`,
      minutes: 30,
    })
    setOpenId(r.id)
  }

  async function confirm(r) {
    setError('')
    if (!form.start || Number.isNaN(new Date(form.start).getTime())) return setError("Choisissez la date et l'heure.")
    setBusy(true)
    let patientId = form.patientId
    if (patientId === 'new') {
      const { data, error } = await supabase.from('patients_basic')
        .insert({ doctor_id: actingId, first_name: r.first_name, last_name: r.last_name, phone: r.phone, email: r.email })
        .select('id').single()
      if (error) { setBusy(false); return setError(error.message) }
      patientId = data.id
      setForm((f) => ({ ...f, patientId }))   // a retry reuses this patient instead of creating a duplicate
    }
    const starts = new Date(form.start)
    const ends = new Date(starts.getTime() + Number(form.minutes) * 60000)
    const { error } = await supabase.rpc('confirm_booking_request', {
      p_request: r.id, p_patient: patientId, p_starts: starts.toISOString(), p_ends: ends.toISOString(),
    })
    setBusy(false)
    if (error) {
      if (error.code === '23P01') return setError('Ce créneau chevauche un autre rendez-vous.')
      if (/already handled/.test(error.message)) { setError('Cette demande a déjà été traitée.'); return load() }
      return setError(error.message)
    }
    setOpenId(null)
    load()
  }

  async function decline(r) {
    if (!window.confirm(`Refuser la demande de ${r.first_name} ${r.last_name} ?`)) return
    const { error } = await supabase.from('booking_requests')
      .update({ status: 'declined' }).eq('id', r.id).eq('status', 'pending')
    if (error) return setError(error.message)
    load()
  }

  return (
    <>
      <h1 className="clinic-page-title">Demandes de rendez-vous</h1>
      <p className="clinic-page-sub">Rappelez le patient, puis confirmez pour créer le rendez-vous.</p>
      {error && <p className="clinic-error">{error}</p>}

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">
            À traiter <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>({pending.length})</span>
          </h2>
        </div>
        {loading ? (
          <div className="clinic-loading">Chargement…</div>
        ) : pending.length === 0 ? (
          <div className="clinic-empty">Aucune demande en attente.</div>
        ) : (
          <>
            <ul className="req-list">
              {pendingPager.slice.map((r) => {
                const matches = matchesOf(r, patients)
                return (
                  <li key={r.id} className="req">
                    <div className="req-main">
                      <strong>{r.last_name} {r.first_name}</strong>
                      <span><a href={`tel:${r.phone}`}>{r.phone}</a>{r.email && ` · ${r.email}`}</span>
                      <span>Souhaite le {fmtDate(r.preferred_date)} · {SLOT[r.preferred_slot]}</span>
                      {r.note && <span className="rx-muted">« {r.note} »</span>}
                      <small className="rx-muted">Reçue le {fmtDateTime(r.created_at)}</small>
                    </div>
                    <div className="req-actions">
                      <button className="clinic-btn clinic-btn-primary" onClick={() => open(r)}>
                        {openId === r.id ? 'Fermer' : 'Confirmer'}
                      </button>
                      <button className="clinic-btn clinic-btn-ghost" onClick={() => decline(r)}>Refuser</button>
                    </div>

                    {openId === r.id && form && (
                      <div className="req-confirm">
                        <div className="clinic-form-grid">
                          <div className="clinic-field clinic-col-12">
                            <label htmlFor={`pt-${r.id}`}>Patient</label>
                            <select id={`pt-${r.id}`} className="clinic-input" value={form.patientId}
                              onChange={(e) => setForm({ ...form, patientId: e.target.value })}>
                              <option value="new">Nouveau patient (créé avec les informations de la demande)</option>
                              {matches.length > 0 && (
                                <optgroup label="Patients correspondants : vérifiez avant de choisir">
                                  {matches.map((p) => (
                                    <option key={`m-${p.id}`} value={p.id}>
                                      {p.last_name} {p.first_name} · {p.phone || 'sans téléphone'} ({p.nameMatch ? 'même nom' : 'même téléphone'})
                                    </option>
                                  ))}
                                </optgroup>
                              )}
                              <optgroup label="Tous les patients">
                                {patients.map((p) => (
                                  <option key={p.id} value={p.id}>{p.last_name} {p.first_name}</option>
                                ))}
                              </optgroup>
                            </select>
                          </div>
                          <div className="clinic-field clinic-col-6">
                            <label htmlFor={`st-${r.id}`}>Date et heure</label>
                            <input id={`st-${r.id}`} className="clinic-input" type="datetime-local" value={form.start}
                              onChange={(e) => setForm({ ...form, start: e.target.value })} />
                          </div>
                          <div className="clinic-field clinic-col-6">
                            <label htmlFor={`du-${r.id}`}>Durée</label>
                            <select id={`du-${r.id}`} className="clinic-input" value={form.minutes}
                              onChange={(e) => setForm({ ...form, minutes: e.target.value })}>
                              {[15, 30, 45, 60, 90].map((m) => <option key={m} value={m}>{m} min</option>)}
                            </select>
                          </div>
                          <div className="clinic-col-12">
                            <button className="clinic-btn clinic-btn-primary" disabled={busy} onClick={() => confirm(r)}>
                              {busy ? 'Création…' : 'Créer le rendez-vous'}
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
            <Pager pager={pendingPager} />
          </>
        )}
      </section>

      {handled.length > 0 && (
        <section className="clinic-card">
          <div className="clinic-card-header"><h2 className="clinic-card-title">Déjà traitées</h2></div>
          <table className="clinic-table">
            <tbody>
              {handledPager.slice.map((r) => {
                const s = STATUS[r.status]
                return (
                  <tr key={r.id}>
                    <td className="clinic-patient-name">{r.last_name} {r.first_name}</td>
                    <td>{fmtDate(r.preferred_date)}</td>
                    <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <Pager pager={handledPager} />
        </section>
      )}
    </>
  )
}
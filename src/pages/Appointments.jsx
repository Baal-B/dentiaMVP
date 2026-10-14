import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDateTime, fullName } from '../lib/format'

const STATUS = {
  scheduled: { text: 'Prévu', cls: 'info' },
  completed: { text: 'Terminé', cls: 'ok' },
  cancelled: { text: 'Annulé', cls: '' },
  no_show: { text: 'Absent', cls: 'danger' },
}
const emptyForm = { patient_id: '', date: '', start: '09:00', end: '09:30', reason: '' }

export default function Appointments() {
  const { user } = useAuth()
  const [patients, setPatients] = useState([])
  const [appts, setAppts] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')

  async function load() {
    const { data: p, error: e1 } = await supabase
      .from('patients').select('id, first_name, last_name').order('last_name')
    if (e1) return setError(e1.message)
    setPatients(p)

    const startOfToday = new Date()
    startOfToday.setHours(0, 0, 0, 0)
    const { data: a, error: e2 } = await supabase
      .from('appointments')
      .select('id, patient_id, starts_at, ends_at, status, reason')
      .gte('starts_at', startOfToday.toISOString())
      .order('starts_at')
      .limit(50)
    if (e2) return setError(e2.message)
    setAppts(a)
  }

  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const byId = Object.fromEntries(patients.map((p) => [p.id, p]))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const starts = new Date(`${form.date}T${form.start}`)
    const ends = new Date(`${form.date}T${form.end}`)
    if (ends <= starts) return setError("L'heure de fin doit être après l'heure de début.")

    const { error } = await supabase.from('appointments').insert({
      doctor_id: user.id,
      patient_id: form.patient_id,
      starts_at: starts.toISOString(),
      ends_at: ends.toISOString(),
      reason: form.reason.trim(),
    })
    if (error) {
      return setError(
        error.code === '23P01' ? 'Ce créneau chevauche un autre rendez-vous.' : error.message
      )
    }
    setForm(emptyForm)
    load()
  }

  async function cancel(id) {
    const { error } = await supabase.from('appointments').update({ status: 'cancelled' }).eq('id', id)
    if (error) setError(error.message)
    else load()
  }

  return (
    <>
      <h1 className="clinic-page-title">Rendez-vous</h1>
      <p className="clinic-page-sub">Planifiez vos consultations.</p>

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Nouveau rendez-vous</h2>
        </div>
        <div className="clinic-card-body">
          <form onSubmit={handleSubmit} className="clinic-form-grid">
            <div className="clinic-field clinic-col-4">
              <label htmlFor="a_patient">Patient</label>
              <select id="a_patient" className="clinic-input" value={form.patient_id}
                onChange={set('patient_id')} required>
                <option value="">Sélectionner…</option>
                {patients.map((p) => <option key={p.id} value={p.id}>{fullName(p)}</option>)}
              </select>
            </div>
            <div className="clinic-field clinic-col-2">
              <label htmlFor="a_date">Date</label>
              <input id="a_date" className="clinic-input" type="date"
                value={form.date} onChange={set('date')} required />
            </div>
            <div className="clinic-field clinic-col-2">
              <label htmlFor="a_start">Début</label>
              <input id="a_start" className="clinic-input" type="time"
                value={form.start} onChange={set('start')} required />
            </div>
            <div className="clinic-field clinic-col-2">
              <label htmlFor="a_end">Fin</label>
              <input id="a_end" className="clinic-input" type="time"
                value={form.end} onChange={set('end')} required />
            </div>
            <div className="clinic-col-2">
              <button type="submit" className="clinic-btn clinic-btn-primary clinic-btn-block">Planifier</button>
            </div>
            <div className="clinic-field clinic-col-12">
              <label htmlFor="a_reason">Motif</label>
              <input id="a_reason" className="clinic-input" placeholder="Contrôle, douleur, détartrage…"
                value={form.reason} onChange={set('reason')} />
            </div>
          </form>
          {error && <p className="clinic-error">{error}</p>}
        </div>
      </section>

      <section className="clinic-card">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">À venir</h2>
        </div>
        {appts.length === 0 ? (
          <div className="clinic-empty">Aucun rendez-vous planifié.</div>
        ) : (
          <table className="clinic-table">
            <thead>
              <tr><th>Quand</th><th>Patient</th><th>Motif</th><th>Statut</th><th></th></tr>
            </thead>
            <tbody>
              {appts.map((a) => {
                const s = STATUS[a.status]
                return (
                  <tr key={a.id}>
                    <td>{fmtDateTime(a.starts_at)}</td>
                    <td className="clinic-patient-name">{fullName(byId[a.patient_id])}</td>
                    <td style={{ color: 'var(--clinic-muted)' }}>{a.reason || '—'}</td>
                    <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
                    <td>
                      {a.status === 'scheduled' && (
                        <button className="clinic-btn clinic-btn-ghost" onClick={() => cancel(a.id)}>
                          Annuler
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
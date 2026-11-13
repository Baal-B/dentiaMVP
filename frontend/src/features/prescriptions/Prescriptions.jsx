import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDate, fullName } from '../../lib/format'
import { REPORT_STATUS } from '../../lib/labels'

export default function Prescriptions() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [patients, setPatients] = useState([])
  const [items, setItems] = useState([])
  const [patientId, setPatientId] = useState(params.get('patient') ?? '')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      const { data: p, error: e1 } = await supabase
        .from('patients').select('id, first_name, last_name').order('last_name')
      if (e1) { setError(e1.message); setLoading(false); return }
      setPatients(p)
      setPatientId((cur) => (p.some((x) => x.id === cur) ? cur : ''))
      const { data: r, error: e2 } = await supabase
        .from('prescriptions')
        .select('id, patient_id, status, created_at, signed_at, content')
        .order('created_at', { ascending: false }).limit(100)
      if (e2) setError(e2.message)
      else setItems(r)
      setLoading(false)
    }
    load()
  }, [])

  const byId = Object.fromEntries(patients.map((p) => [p.id, p]))

  async function create(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const { data, error } = await supabase
      .from('prescriptions')
      .insert({ doctor_id: user.id, patient_id: patientId })
      .select('id').single()
    setBusy(false)
    if (error) return setError(error.message)
    navigate(`/prescriptions/${data.id}`)
  }

  return (
    <>
      <h1 className="clinic-page-title">Ordonnances</h1>
      <p className="clinic-page-sub">Rédigez, signez et imprimez vos ordonnances.</p>
      {error && <p className="clinic-error">{error}</p>}

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header"><h2 className="clinic-card-title">Nouvelle ordonnance</h2></div>
        <div className="clinic-card-body">
          {patients.length === 0 && !loading ? (
            <p style={{ margin: 0 }}>Aucun patient. <Link to="/patients">Ajoutez-en un</Link> d'abord.</p>
          ) : (
            <form onSubmit={create} className="clinic-form-grid">
              <div className="clinic-field clinic-col-6" style={{ marginBottom: 0 }}>
                <label htmlFor="rx_patient">Patient</label>
                <select id="rx_patient" className="clinic-input" value={patientId}
                  onChange={(e) => setPatientId(e.target.value)} required>
                  <option value="">Sélectionner…</option>
                  {patients.map((p) => <option key={p.id} value={p.id}>{fullName(p)}</option>)}
                </select>
              </div>
              <div className="clinic-col-3">
                <button className="clinic-btn clinic-btn-primary clinic-btn-block" disabled={busy || !patientId}>
                  {busy ? 'Création…' : 'Créer'}
                </button>
              </div>
            </form>
          )}
        </div>
      </section>

      <section className="clinic-card">
        <div className="clinic-card-header"><h2 className="clinic-card-title">Mes ordonnances</h2></div>
        {loading ? (
          <div className="clinic-loading">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="clinic-empty">Aucune ordonnance pour le moment.</div>
        ) : (
          <table className="clinic-table">
            <thead><tr><th>Patient</th><th>Date</th><th>Lignes</th><th>Statut</th></tr></thead>
            <tbody>
              {items.map((r) => {
                const s = REPORT_STATUS[r.status]
                return (
                  <tr key={r.id}>
                    <td className="clinic-patient-name">
                      <Link to={`/prescriptions/${r.id}`} className="clinic-link-name">{fullName(byId[r.patient_id])}</Link>
                    </td>
                    <td>{fmtDate(r.signed_at ?? r.created_at)}</td>
                    <td>{r.content?.lines?.length ?? 0}</td>
                    <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
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
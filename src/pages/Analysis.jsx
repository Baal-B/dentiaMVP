import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDate, fullName } from '../lib/format'

const MAX_SIZE = 30 * 1024 * 1024 // matches the bucket limit
const TYPES = ['image/png', 'image/jpeg']
const KINDS = { panoramic: 'Panoramique', periapical: 'Rétro-alvéolaire', bitewing: 'Bite-wing' }
const emptyForm = { patient_id: '', kind: 'panoramic', taken_at: '', symptoms: '' }

function statusLabel(a) {
  if (!a) return { text: 'Pas encore analysée', cls: '' }
  if (a.status === 'pending') return { text: 'Analyse en cours', cls: '' }
  if (a.status === 'failed') return { text: 'Échec', cls: 'danger' }
  if (a.validation_status === 'validated') return { text: 'Validée', cls: 'ok' }
  if (a.validation_status === 'rejected') return { text: 'Rejetée', cls: 'danger' }
  return { text: 'À valider', cls: 'info' }
}

export default function Analysis() {
  const { user } = useAuth()
  const [patients, setPatients] = useState([])
  const [recent, setRecent] = useState([])
  const [analyses, setAnalyses] = useState({})
  const [form, setForm] = useState(emptyForm)
  const [file, setFile] = useState(null)
  const [fileKey, setFileKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    const { data: p, error: e1 } = await supabase
      .from('patients').select('id, first_name, last_name').order('last_name')
    if (e1) return setError(e1.message)
    setPatients(p)

    const { data: r, error: e2 } = await supabase
      .from('radiographs')
      .select('id, patient_id, kind, taken_at, created_at')
      .order('created_at', { ascending: false })
      .limit(8)
    if (e2) return setError(e2.message)
    setRecent(r)

    if (r.length) {
      const { data: a } = await supabase
        .from('analyses')
        .select('radiograph_id, status, validation_status')
        .in('radiograph_id', r.map((x) => x.id))
      setAnalyses(Object.fromEntries((a ?? []).map((x) => [x.radiograph_id, x])))
    }
  }

  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const byId = Object.fromEntries(patients.map((p) => [p.id, p]))

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!file) return setError('Choisissez une image.')
    if (!TYPES.includes(file.type)) return setError('Format non supporté : PNG ou JPEG uniquement.')
    if (file.size > MAX_SIZE) return setError('Fichier trop volumineux (30 Mo maximum).')

    setBusy(true)
    const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_')
    const path = `${user.id}/${form.patient_id}/${Date.now()}-${safeName}`

    const { error: upErr } = await supabase.storage
      .from('radiographs')
      .upload(path, file, { contentType: file.type })
    if (upErr) {
      setBusy(false)
      return setError(upErr.message)
    }

    const { error: dbErr } = await supabase.from('radiographs').insert({
      doctor_id: user.id,
      patient_id: form.patient_id,
      storage_path: path,
      kind: form.kind,
      taken_at: form.taken_at || null,
      symptoms: form.symptoms.trim(),
    })
    if (dbErr) {
      await supabase.storage.from('radiographs').remove([path]) // no orphan file
      setBusy(false)
      return setError(dbErr.message)
    }

    setBusy(false)
    setForm(emptyForm)
    setFile(null)
    setFileKey((k) => k + 1)
    setSuccess('Radiographie enregistrée.')
    load()
  }

  return (
    <>
      <h1 className="clinic-page-title">Nouvelle analyse</h1>
      <p className="clinic-page-sub">Choisissez un patient, ajoutez la radiographie et décrivez les symptômes.</p>

      <div className="clinic-notice">
        <strong>Étape 1 sur 2.</strong>
        <span>
          L'analyse par l'IA sera lancée automatiquement une fois l'API agent branchée.
          Pour l'instant, l'image et les symptômes sont enregistrés dans le dossier du patient.
        </span>
      </div>

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Radiographie</h2>
        </div>
        <div className="clinic-card-body">
          {patients.length === 0 ? (
            <p style={{ margin: 0 }}>
              Vous n'avez pas encore de patient. <Link to="/patients">Ajoutez-en un</Link> d'abord.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="clinic-form-grid">
              <div className="clinic-field clinic-col-6">
                <label htmlFor="patient">Patient</label>
                <select id="patient" className="clinic-input" value={form.patient_id}
                  onChange={set('patient_id')} required>
                  <option value="">Sélectionner…</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>{fullName(p)}</option>
                  ))}
                </select>
              </div>

              <div className="clinic-field clinic-col-3">
                <label htmlFor="kind">Type</label>
                <select id="kind" className="clinic-input" value={form.kind} onChange={set('kind')}>
                  {Object.entries(KINDS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </div>

              <div className="clinic-field clinic-col-3">
                <label htmlFor="taken_at">Date de prise</label>
                <input id="taken_at" className="clinic-input" type="date"
                  value={form.taken_at} onChange={set('taken_at')} />
              </div>

              <div className="clinic-field clinic-col-12">
                <label htmlFor="file">Image (PNG ou JPEG, 30 Mo max)</label>
                <input key={fileKey} id="file" className="clinic-input" type="file"
                  accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files[0] ?? null)} />
              </div>

              <div className="clinic-field clinic-col-12">
                <label htmlFor="symptoms">Symptômes / motif de consultation</label>
                <textarea id="symptoms" className="clinic-input"
                  placeholder="Ex : douleur persistante molaire inférieure droite depuis 3 jours, sensibilité au froid…"
                  value={form.symptoms} onChange={set('symptoms')} />
              </div>

              <div className="clinic-col-12">
                <button type="submit" className="clinic-btn clinic-btn-primary" disabled={busy}>
                  {busy ? 'Envoi…' : 'Enregistrer la radiographie'}
                </button>
              </div>
            </form>
          )}
          {error && <p className="clinic-error">{error}</p>}
          {success && <p className="clinic-success">{success}</p>}
        </div>
      </section>

      <section className="clinic-card">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Dernières radiographies</h2>
        </div>
        {recent.length === 0 ? (
          <div className="clinic-empty">Aucune radiographie pour le moment.</div>
        ) : (
          <table className="clinic-table">
            <thead>
              <tr><th>Patient</th><th>Type</th><th>Date</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {recent.map((r) => {
                const s = statusLabel(analyses[r.id])
                return (
                  <tr key={r.id}>
                    <td className="clinic-patient-name">{fullName(byId[r.patient_id])}</td>
                    <td>{KINDS[r.kind]}</td>
                    <td>{fmtDate(r.taken_at ?? r.created_at)}</td>
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
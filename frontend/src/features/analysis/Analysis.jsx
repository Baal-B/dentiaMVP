import { useEffect, useState } from 'react'

import { supabase } from '../../lib/supabase'
import { api } from '../../lib/api'
import { useAuth } from '../auth/AuthProvider'
import { fmtDate, fullName } from '../../lib/format'
import AssistantPanel from './AssistantPanel'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'


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
  const navigate = useNavigate()
  const [patients, setPatients] = useState([])
  const [recent, setRecent] = useState([])
  const [analyses, setAnalyses] = useState({})
  const [params] = useSearchParams()
  const [form, setForm] = useState({ ...emptyForm, patient_id: params.get('patient') ?? '' })
  const [file, setFile] = useState(null)
  const [fileKey, setFileKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState('')
  const [error, setError] = useState('')
  const [answer, setAnswer] = useState([])

  async function load() {
    const { data: p, error: e1 } = await supabase
      .from('patients').select('id, first_name, last_name').order('last_name')
    if (e1) return setError(e1.message)
    setPatients(p)
    setForm((f) => (p.some((x) => x.id === f.patient_id) ? f : { ...f, patient_id: '' }))

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
        .select('radiograph_id, status, validation_status, created_at')
        .in('radiograph_id', r.map((x) => x.id))
        .order('created_at')
      // ordered oldest -> newest, so the newest analysis wins
      setAnalyses(Object.fromEntries((a ?? []).map((x) => [x.radiograph_id, x])))
    }
  }

  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const byId = Object.fromEntries(patients.map((p) => [p.id, p]))
  const symptoms = form.symptoms.trim()
  const canSubmit = form.patient_id && (file || symptoms)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setAnswer([])

    if (file) {
      if (!TYPES.includes(file.type)) return setError('Format non supporté : PNG ou JPEG uniquement.')
      if (file.size > MAX_SIZE) return setError('Fichier trop volumineux (30 Mo maximum).')
    }

    setBusy(true)
    let radiographId = null

    if (file) {
      setStep('Envoi de la radiographie…')
      const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_')
      const path = `${user.id}/${form.patient_id}/${Date.now()}-${safeName}`

      const { error: upErr } = await supabase.storage
        .from('radiographs').upload(path, file, { contentType: file.type })
      if (upErr) { setBusy(false); setStep(''); return setError(upErr.message) }

      const { data: row, error: dbErr } = await supabase
        .from('radiographs')
        .insert({
          doctor_id: user.id,
          patient_id: form.patient_id,
          storage_path: path,
          kind: form.kind,
          taken_at: form.taken_at || null,
          symptoms,
        })
        .select('id')
        .single()
      if (dbErr) {
        await supabase.storage.from('radiographs').remove([path]) // no orphan file
        setBusy(false); setStep('')
        return setError(dbErr.message)
      }
      radiographId = row.id

      setStep("Analyse par l'IA… (quelques secondes)")
      try {
        await api('/analyses', { method: 'POST', body: JSON.stringify({ radiograph_id: radiographId }) })
      } catch {
        // the review page shows the failed state with a retry button
      }
    }

    let query = null
    if (symptoms) {
      setStep('Recherche dans la littérature…')
      try {
        query = await api('/assistant', {
          method: 'POST',
          body: JSON.stringify({ question: symptoms, patient_id: form.patient_id, radiograph_id: radiographId }),
        })
      } catch (err) {
        if (!radiographId) setError(err.message)
      }
    }

    setBusy(false)
    setStep('')

    if (radiographId) {
      navigate(`/analysis/${radiographId}`)
    } else if (query) {
      setAnswer([query])
    }
  }

  const buttonText = file && symptoms ? 'Analyser et rechercher'
    : file ? 'Analyser la radiographie'
    : symptoms ? 'Rechercher dans la littérature'
    : 'Continuer'

  return (
    <>
      <h1 className="clinic-page-title">Nouvelle analyse</h1>
      <p className="clinic-page-sub">
        Ajoutez une radiographie, des symptômes, ou les deux. Le résultat s'affiche directement.
      </p>

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-body">
          {patients.length === 0 ? (
            <p style={{ margin: 0 }}>
              Vous n'avez pas encore de patient. <Link to="/patients">Ajoutez-en un</Link> d'abord.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="clinic-form-grid">
              <div className="clinic-field clinic-col-12">
                <label htmlFor="patient">Patient</label>
                <select id="patient" className="clinic-input" value={form.patient_id}
                  onChange={set('patient_id')} required>
                  <option value="">Sélectionner…</option>
                  {patients.map((p) => <option key={p.id} value={p.id}>{fullName(p)}</option>)}
                </select>
              </div>

              <div className="clinic-field clinic-col-12">
                <label htmlFor="file">Radiographie (facultatif — PNG ou JPEG, 30 Mo max)</label>
                <input key={fileKey} id="file" className="clinic-input" type="file"
                  accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files[0] ?? null)} />
              </div>

              {file && (
                <>
                  <div className="clinic-field clinic-col-6">
                    <label htmlFor="kind">Type</label>
                    <select id="kind" className="clinic-input" value={form.kind} onChange={set('kind')}>
                      {Object.entries(KINDS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </div>
                  <div className="clinic-field clinic-col-6">
                    <label htmlFor="taken_at">Date de prise</label>
                    <input id="taken_at" className="clinic-input" type="date"
                      value={form.taken_at} onChange={set('taken_at')} />
                  </div>
                </>
              )}

              <div className="clinic-field clinic-col-12">
                <label htmlFor="symptoms">Symptômes / motif de consultation (facultatif)</label>
                <textarea id="symptoms" className="clinic-input"
                  placeholder="Ex : douleur persistante molaire inférieure droite depuis 3 jours, sensibilité au froid…"
                  value={form.symptoms} onChange={set('symptoms')} />
              </div>

              <div className="clinic-col-12">
                <button type="submit" className="clinic-btn clinic-btn-primary" disabled={busy || !canSubmit}>
                  {busy ? step || '…' : buttonText}
                </button>
                {!canSubmit && form.patient_id && (
                  <span style={{ marginLeft: 12, color: 'var(--clinic-muted)', fontSize: 15 }}>
                    Ajoutez au moins une radiographie ou des symptômes.
                  </span>
                )}
              </div>
            </form>
          )}
          {error && <p className="clinic-error">{error}</p>}
        </div>
      </section>

      <AssistantPanel queries={answer} />

      <section className="clinic-card" style={{ marginTop: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Dernières radiographies</h2>
        </div>
        {recent.length === 0 ? (
          <div className="clinic-empty">Aucune radiographie pour le moment.</div>
        ) : (
          <table className="clinic-table">
            <thead>
              <tr><th>Patient</th><th>Type</th><th>Date</th><th>Statut</th><th></th></tr>
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
                    <td>
                      <Link to={`/analysis/${r.id}`} className="clinic-btn clinic-btn-ghost">
                        {s.text === 'À valider' ? 'Valider' : 'Ouvrir'}
                      </Link>
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
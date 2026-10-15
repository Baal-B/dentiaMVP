import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { fmtDate, fmtDateTime } from '../../lib/format'
import { KINDS, statusLabel, APPT_STATUS, REPORT_STATUS } from '../../lib/labels'
import AssistantPanel from '../analysis/AssistantPanel'

function ageOf(birth) {
  if (!birth) return null
  const [y, m, d] = birth.split('-').map(Number)
  const now = new Date()
  let age = now.getFullYear() - y
  if (now < new Date(now.getFullYear(), m - 1, d)) age--
  return age
}

export default function PatientFile() {
  const { id } = useParams()
  const [patient, setPatient] = useState(null)
  const [radiographs, setRadiographs] = useState([])
  const [analyses, setAnalyses] = useState({})
  const [thumbs, setThumbs] = useState({})
  const [appts, setAppts] = useState([])
  const [reports, setReports] = useState([])
  const [queries, setQueries] = useState([])
  const [openQuery, setOpenQuery] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState(null) // null = not editing
  const [saving, setSaving] = useState(false)

  async function load() {
    const { data: p, error: e } = await supabase
      .from('patients').select('*').eq('id', id).maybeSingle()
    if (e) { setError(e.message); setLoading(false); return }
    if (!p) { setLoading(false); return } // not found, or not yours (RLS)
    setPatient(p)

    const [r, a, rp, q] = await Promise.all([
      supabase.from('radiographs')
        .select('id, kind, taken_at, created_at, storage_path, symptoms')
        .eq('patient_id', id).order('created_at', { ascending: false }),
      supabase.from('appointments')
        .select('id, starts_at, status, reason')
        .eq('patient_id', id).order('starts_at', { ascending: false }).limit(8),
      supabase.from('reports')
        .select('id, title, status, created_at, signed_at')
        .eq('patient_id', id).order('created_at', { ascending: false }),
      supabase.from('assistant_queries')
        .select('id, question, answer, citations, insufficient_evidence, created_at')
        .eq('patient_id', id).is('radiograph_id', null).order('created_at', { ascending: false }),
    ])

    const failed = [r, a, rp, q].find((x) => x.error)
    if (failed) { setError(failed.error.message); setLoading(false); return }

    setRadiographs(r.data)
    setAppts(a.data)
    setReports(rp.data)
    setQueries(q.data)

    if (r.data.length) {
      const [an, signed] = await Promise.all([
        supabase.from('analyses')
          .select('radiograph_id, status, validation_status, created_at')
          .in('radiograph_id', r.data.map((x) => x.id))
          .order('created_at'),
        supabase.storage.from('radiographs')
          .createSignedUrls(r.data.map((x) => x.storage_path), 3600),
      ])
      // oldest -> newest, so the newest analysis wins
      setAnalyses(Object.fromEntries((an.data ?? []).map((x) => [x.radiograph_id, x])))
      setThumbs(Object.fromEntries((signed.data ?? []).map((s) => [s.path, s.signedUrl])))
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  function startEdit() {
    setError('')
    setDraft({
      first_name: patient.first_name,
      last_name: patient.last_name,
      birth_date: patient.birth_date ?? '',
      sex: patient.sex ?? '',
      phone: patient.phone ?? '',
      email: patient.email ?? '',
      medical_history: patient.medical_history ?? '',
    })
  }

  async function saveEdit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    const { error } = await supabase.from('patients').update({
      first_name: draft.first_name.trim(),
      last_name: draft.last_name.trim(),
      birth_date: draft.birth_date || null,
      sex: draft.sex || null,
      phone: draft.phone.trim() || null,
      email: draft.email.trim() || null,
      medical_history: draft.medical_history,
    }).eq('id', id)
    setSaving(false)
    if (error) return setError(error.message)
    setDraft(null)
    load()
  }

  const setD = (k) => (e) => setDraft({ ...draft, [k]: e.target.value })

  if (loading) return <div className="clinic-loading">Chargement…</div>
  if (!patient) {
    return (
      <div className="clinic-empty">
        Patient introuvable. <Link to="/patients">Retour à la liste</Link>
      </div>
    )
  }

  const age = ageOf(patient.birth_date)
  const openQ = queries.find((q) => q.id === openQuery)

  return (
    <>
      <Link to="/patients" className="clinic-back">
        <ArrowLeft size={18} /> Patients
      </Link>

      <div className="clinic-file-head">
        <div>
          <h1 className="clinic-page-title" style={{ marginBottom: 2 }}>
            {patient.last_name} {patient.first_name}
          </h1>
          <p className="clinic-page-sub" style={{ marginBottom: 0 }}>
            {[age != null && `${age} ans`, patient.sex && { F: 'Femme', M: 'Homme', other: 'Autre' }[patient.sex]]
              .filter(Boolean).join(' · ') || 'Informations incomplètes'}
          </p>
        </div>
        <div className="clinic-actions">
          <Link to={`/analysis?patient=${id}`} className="clinic-btn clinic-btn-primary">Nouvelle analyse</Link>
          <Link to={`/appointments?patient=${id}`} className="clinic-btn clinic-btn-ghost">Nouveau rendez-vous</Link>
          {!draft && <button className="clinic-btn clinic-btn-ghost" onClick={startEdit}>Modifier</button>}
        </div>
      </div>

      {error && <p className="clinic-error">{error}</p>}

      {/* ---------- Informations ---------- */}
      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Informations</h2>
        </div>
        <div className="clinic-card-body">
          {draft ? (
            <form onSubmit={saveEdit} className="clinic-form-grid">
              <div className="clinic-field clinic-col-3">
                <label htmlFor="e_first">Prénom</label>
                <input id="e_first" className="clinic-input" value={draft.first_name} onChange={setD('first_name')} required />
              </div>
              <div className="clinic-field clinic-col-3">
                <label htmlFor="e_last">Nom</label>
                <input id="e_last" className="clinic-input" value={draft.last_name} onChange={setD('last_name')} required />
              </div>
              <div className="clinic-field clinic-col-3">
                <label htmlFor="e_birth">Naissance</label>
                <input id="e_birth" className="clinic-input" type="date" value={draft.birth_date} onChange={setD('birth_date')} />
              </div>
              <div className="clinic-field clinic-col-3">
                <label htmlFor="e_sex">Sexe</label>
                <select id="e_sex" className="clinic-input" value={draft.sex} onChange={setD('sex')}>
                  <option value="">—</option>
                  <option value="F">F</option>
                  <option value="M">M</option>
                  <option value="other">Autre</option>
                </select>
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="e_phone">Téléphone</label>
                <input id="e_phone" className="clinic-input" value={draft.phone} onChange={setD('phone')} />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="e_email">E-mail</label>
                <input id="e_email" className="clinic-input" type="email" value={draft.email} onChange={setD('email')} />
              </div>
              <div className="clinic-field clinic-col-12">
                <label htmlFor="e_hist">Antécédents médicaux (allergies, pathologies, traitements)</label>
                <textarea id="e_hist" className="clinic-input" value={draft.medical_history} onChange={setD('medical_history')} />
              </div>
              <div className="clinic-col-12" style={{ display: 'flex', gap: 10 }}>
                <button className="clinic-btn clinic-btn-primary" disabled={saving}>
                  {saving ? 'Enregistrement…' : 'Enregistrer'}
                </button>
                <button type="button" className="clinic-btn clinic-btn-ghost" onClick={() => setDraft(null)}>
                  Annuler
                </button>
              </div>
            </form>
          ) : (
            <dl className="clinic-info">
              <div><dt>Naissance</dt><dd>{patient.birth_date ? fmtDate(patient.birth_date) : '—'}</dd></div>
              <div><dt>Téléphone</dt><dd>{patient.phone || '—'}</dd></div>
              <div><dt>E-mail</dt><dd>{patient.email || '—'}</dd></div>
              <div className="wide">
                <dt>Antécédents médicaux</dt>
                <dd style={{ whiteSpace: 'pre-wrap' }}>{patient.medical_history || 'Non renseignés'}</dd>
              </div>
            </dl>
          )}
        </div>
      </section>

      {/* ---------- Radiographies ---------- */}
      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">
            Radiographies <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>({radiographs.length})</span>
          </h2>
        </div>
        {radiographs.length === 0 ? (
          <div className="clinic-empty">
            Aucune radiographie pour ce patient.<br />
            <Link to={`/analysis?patient=${id}`}>Lancer une première analyse</Link>
          </div>
        ) : (
          <div className="clinic-card-body clinic-thumbs">
            {radiographs.map((r) => {
              const s = statusLabel(analyses[r.id])
              return (
                <Link key={r.id} to={`/analysis/${r.id}`} className="clinic-thumb">
                  {thumbs[r.storage_path] ? (
                    <img src={thumbs[r.storage_path]} alt="" loading="lazy" />
                  ) : (
                    <div className="clinic-thumb-empty">Aperçu indisponible</div>
                  )}
                  <div className="clinic-thumb-meta">
                    <strong>{KINDS[r.kind]}</strong>
                    <span style={{ color: 'var(--clinic-muted)' }}>{fmtDate(r.taken_at ?? r.created_at)}</span>
                    <span className={`clinic-pill ${s.cls}`}>{s.text}</span>
                  </div>
                </Link>
              )
            })}
          </div>
        )}
      </section>

      {/* ---------- Rendez-vous + Rapports ---------- */}
      <div className="clinic-two-col">
        <section className="clinic-card">
          <div className="clinic-card-header">
            <h2 className="clinic-card-title">Rendez-vous</h2>
            <Link to="/appointments" className="clinic-btn clinic-btn-ghost">Agenda</Link>
          </div>
          {appts.length === 0 ? (
            <div className="clinic-empty">Aucun rendez-vous.</div>
          ) : (
            <table className="clinic-table">
              <tbody>
                {appts.map((a) => {
                  const s = APPT_STATUS[a.status]
                  return (
                    <tr key={a.id}>
                      <td>{fmtDateTime(a.starts_at)}</td>
                      <td style={{ color: 'var(--clinic-muted)' }}>{a.reason || '—'}</td>
                      <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>

        <section className="clinic-card">
          <div className="clinic-card-header">
            <h2 className="clinic-card-title">Rapports</h2>
          </div>
          {reports.length === 0 ? (
            <div className="clinic-empty">
              Aucun rapport.<br />
              <span style={{ fontSize: 14 }}>La génération de rapports arrive à l'étape suivante.</span>
            </div>
          ) : (
            <table className="clinic-table">
              <tbody>
                {reports.map((r) => {
                  const s = REPORT_STATUS[r.status]
                  return (
                    <tr key={r.id}>
                      <td className="clinic-patient-name">{r.title || 'Sans titre'}</td>
                      <td>{fmtDate(r.signed_at ?? r.created_at)}</td>
                      <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {/* ---------- Recherches sans radiographie ---------- */}
      {queries.length > 0 && (
        <section className="clinic-card" style={{ marginTop: 24 }}>
          <div className="clinic-card-header">
            <h2 className="clinic-card-title">Recherches bibliographiques (sans radiographie)</h2>
          </div>
          <ul className="clinic-finding-list" style={{ maxHeight: 'none' }}>
            {queries.map((q) => (
              <li
                key={q.id}
                className={'clinic-finding' + (q.id === openQuery ? ' selected' : '')}
                onClick={() => setOpenQuery(q.id === openQuery ? null : q.id)}
              >
                <strong>{q.question}</strong>
                <span style={{ color: 'var(--clinic-muted)', fontSize: 15 }}>
                  {fmtDate(q.created_at)} ·{' '}
                  {q.insufficient_evidence ? 'pas assez de preuves' : `${q.citations?.length ?? 0} source(s)`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {openQ && <AssistantPanel queries={[openQ]} />}
    </>
  )
}
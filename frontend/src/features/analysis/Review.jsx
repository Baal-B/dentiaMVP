import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { buildReport } from '../../lib/report'
import { ArrowLeft } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { api } from '../../lib/api'
import { fmtDate, fullName } from '../../lib/format'
import { labelFr, pct } from '../../lib/findings'
import FindingsViewer from './FindingsViewer'
import AssistantPanel from './AssistantPanel'

const KINDS = { panoramic: 'Panoramique', periapical: 'Rétro-alvéolaire', bitewing: 'Bite-wing' }

export default function Review() {
  const { id } = useParams()
  const { user } = useAuth()
const navigate = useNavigate()
const [report, setReport] = useState(null)
  const [rg, setRg] = useState(null)
  const [patient, setPatient] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [imageUrl, setImageUrl] = useState('')
  const [queries, setQueries] = useState([])
  const [decisions, setDecisions] = useState({})
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  async function load() {
    const { data: r, error: e } = await supabase
      .from('radiographs')
      .select('id, patient_id, kind, taken_at, symptoms, storage_path, created_at')
      .eq('id', id)
      .maybeSingle()
    if (e) { setError(e.message); setLoading(false); return }
    if (!r) { setLoading(false); return }
    setRg(r)

    const [p, a, q, signed] = await Promise.all([
      supabase.from('patients').select('id, first_name, last_name').eq('id', r.patient_id).maybeSingle(),
      supabase.from('analyses')
        .select('id, status, findings, model_info, validation_status, validated_findings, error, created_at')
        .eq('radiograph_id', id).order('created_at', { ascending: false }).limit(1),
      supabase.from('assistant_queries')
        .select('id, question, answer, citations, insufficient_evidence, created_at')
        .eq('radiograph_id', id).order('created_at', { ascending: false }),
      supabase.storage.from('radiographs').createSignedUrl(r.storage_path, 3600),
    ])

    setPatient(p.data)
    const an = a.data?.[0] ?? null
    setAnalysis(an)
    if (an) {
  const { data: rep } = await supabase
    .from('reports').select('id, status').eq('analysis_id', an.id).limit(1)
  setReport(rep?.[0] ?? null)
} else {
  setReport(null)
}
    setDecisions(
      an?.validated_findings
        ? Object.fromEntries(an.validated_findings.map((f) => [f.id, f.decision]))
        : {}
    )
    setQueries(q.data ?? [])
    setImageUrl(signed.data?.signedUrl ?? '')
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  async function runAnalysis() {
    setError('')
    setBusy('analysis')
    try {
      await api('/analyses', { method: 'POST', body: JSON.stringify({ radiograph_id: id }) })
    } catch (e) {
      setError(e.message)
    }
    await load()
    setBusy('')
  }

  async function askAssistant() {
    setError('')
    setBusy('assistant')
    try {
      await api('/assistant', {
        method: 'POST',
        body: JSON.stringify({ question: rg.symptoms, patient_id: rg.patient_id, radiograph_id: id }),
      })
    } catch (e) {
      setError(e.message)
    }
    await load()
    setBusy('')
  }

  async function createReport() {
  setBusy('report')
  setError('')
  const { content, citations } = buildReport({ radiograph: rg, analysis, queries })
  const { data, error } = await supabase
    .from('reports')
    .insert({
      doctor_id: user.id,
      patient_id: rg.patient_id,
      analysis_id: analysis.id,
      title: `Rapport radiologique — ${fullName(patient)}`,
      content,
      citations,
    })
    .select('id')
    .single()
  setBusy('')
  if (error) return setError(error.message)
  navigate(`/reports/${data.id}`)
}

  async function save(status) {
    setBusy('save')
    setError('')
    const payload =
      status === 'validated'
        ? {
            validation_status: 'validated',
            validated_findings: findings.map((f) => ({ ...f, decision: decisions[f.id] })),
          }
        : { validation_status: 'rejected' }
    const { error } = await supabase
      .from('analyses')
      .update(payload)
      .eq('id', analysis.id)
      .eq('validation_status', 'pending')
    if (error) setError(error.message)
    await load()
    setBusy('')
  }

  const decide = (fid, value) => setDecisions((d) => ({ ...d, [fid]: value }))

  if (loading) return <div className="clinic-loading">Chargement…</div>
  if (!rg) return <div className="clinic-empty">Radiographie introuvable.</div>

  const completed = analysis?.status === 'completed'
  const findings = completed ? analysis.findings ?? [] : []
  const readOnly = analysis?.validation_status !== 'pending'
  const allDecided = findings.every((f) => decisions[f.id])
  const decidedCount = findings.filter((f) => decisions[f.id]).length

  return (
    <>
      <Link to="/analysis" className="clinic-back">
        <ArrowLeft size={18} /> Retour aux analyses
      </Link>
<h1 className="clinic-page-title">
  <Link to={`/patients/${rg.patient_id}`} className="clinic-link-name">{fullName(patient)}</Link>
</h1>      <p className="clinic-page-sub">
        {KINDS[rg.kind]} · {fmtDate(rg.taken_at ?? rg.created_at)}
      </p>

      {rg.symptoms && (
        <div className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-body">
            <strong>Symptômes / motif :</strong> {rg.symptoms}
          </div>
        </div>
      )}

      {error && <p className="clinic-error">{error}</p>}

      {analysis?.model_info?.mock && (
        <div className="clinic-notice">
          <strong>Résultat simulé.</strong>
          <span>Le service de vision est en mode démo : ces zones sont aléatoires, pas une vraie analyse.</span>
        </div>
      )}

      {!analysis || analysis.status === 'failed' ? (
        <section className="clinic-card">
          <div className="clinic-card-body">
            <p style={{ marginTop: 0 }}>
              {analysis?.status === 'failed'
                ? "L'analyse a échoué. Vérifiez que le service de vision est lancé, puis réessayez."
                : "Cette radiographie n'a pas encore été analysée."}
            </p>
            <button className="clinic-btn clinic-btn-primary" onClick={runAnalysis} disabled={busy === 'analysis'}>
              {busy === 'analysis' ? 'Analyse en cours…' : "Lancer l'analyse"}
            </button>
          </div>
        </section>
      ) : analysis.status === 'pending' ? (
        <section className="clinic-card">
          <div className="clinic-card-body">
            <p style={{ marginTop: 0 }}>Analyse en cours…</p>
            <button className="clinic-btn clinic-btn-ghost" onClick={load}>Actualiser</button>
          </div>
        </section>
      ) : (
        <div className="clinic-review">
          <div>
            {imageUrl ? (
              <FindingsViewer
                url={imageUrl}
                findings={findings}
                decisions={decisions}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            ) : (
              <p className="clinic-error">Impossible de charger l'image.</p>
            )}
          </div>

          <aside className="clinic-card clinic-findings">
            <div className="clinic-card-header">
              <h2 className="clinic-card-title">
                Résultats <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>({findings.length})</span>
              </h2>
              {!readOnly && findings.length > 0 && (
                <button
                  className="clinic-btn clinic-btn-ghost"
                  onClick={() => setDecisions(Object.fromEntries(findings.map((f) => [f.id, 'accepted'])))}
                >
                  Tout accepter
                </button>
              )}
            </div>

            {findings.length === 0 ? (
              <div className="clinic-card-body">
                <p style={{ marginTop: 0 }}>Le modèle n'a rien détecté.</p>
                <p style={{ color: 'var(--clinic-muted)', marginBottom: 0 }}>
                  Cela ne prouve pas l'absence de pathologie : examinez l'image vous-même.
                </p>
              </div>
            ) : (
              <ul className="clinic-finding-list">
                {findings.map((f) => {
                  const d = decisions[f.id]
                  return (
                    <li
                      key={f.id}
                      className={'clinic-finding' + (f.id === selectedId ? ' selected' : '')}
                      onClick={() => setSelectedId(f.id)}
                    >
                      <div>
                        <strong>{f.id}. {labelFr(f.label)}</strong>
                        {f.depth === 'possibly deep' && ' (possiblement profonde)'}
                      </div>
                      <div style={{ color: 'var(--clinic-muted)', fontSize: 15 }}>
                        Confiance {pct(f.confidence)} ·{' '}
                        {f.tooth_fdi ? `dent ${f.tooth_fdi} (estimée)` : 'dent non identifiée'}
                      </div>
                      {f.needs_review && (
                        <span className="clinic-pill danger" style={{ marginTop: 6 }}>
                          Confiance faible : à examiner
                        </span>
                      )}
                      {readOnly ? (
  <>
    <p
      className={analysis.validation_status === 'validated' ? 'clinic-success' : 'clinic-error'}
      style={{ margin: 0 }}
    >
      {analysis.validation_status === 'validated' ? 'Revue validée.' : 'Analyse rejetée.'}
    </p>
    {analysis.validation_status === 'validated' &&
      (report ? (
        <Link
          to={`/reports/${report.id}`}
          className="clinic-btn clinic-btn-primary clinic-btn-block"
          style={{ marginTop: 12 }}
        >
          {report.status === 'signed' ? 'Voir le rapport signé' : 'Ouvrir le brouillon du rapport'}
        </Link>
      ) : (
        <button
          className="clinic-btn clinic-btn-primary clinic-btn-block"
          style={{ marginTop: 12 }}
          onClick={createReport}
          disabled={busy === 'report'}
        >
          {busy === 'report' ? 'Création…' : 'Générer le rapport'}
        </button>
      ))}
  </>
) : (
                        <div className="clinic-decide">
                          <button
                            className={'clinic-btn clinic-btn-ghost' + (d === 'accepted' ? ' on-accept' : '')}
                            onClick={(e) => { e.stopPropagation(); decide(f.id, 'accepted') }}
                          >
                            Accepter
                          </button>
                          <button
                            className={'clinic-btn clinic-btn-ghost' + (d === 'rejected' ? ' on-reject' : '')}
                            onClick={(e) => { e.stopPropagation(); decide(f.id, 'rejected') }}
                          >
                            Rejeter
                          </button>
                        </div>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            <div className="clinic-card-body">
              {readOnly ? (
                <p className={analysis.validation_status === 'validated' ? 'clinic-success' : 'clinic-error'} style={{ margin: 0 }}>
                  {analysis.validation_status === 'validated' ? 'Revue validée.' : 'Analyse rejetée.'}
                </p>
              ) : (
                <div style={{ display: 'grid', gap: 10 }}>
                  <button
                    className="clinic-btn clinic-btn-primary clinic-btn-block"
                    disabled={!allDecided || busy === 'save'}
                    onClick={() => save('validated')}
                  >
                    {findings.length === 0
                      ? 'Marquer comme revue'
                      : allDecided
                        ? 'Valider la revue'
                        : `Valider (${decidedCount}/${findings.length} décidés)`}
                  </button>
                  <button
                    className="clinic-btn clinic-btn-ghost clinic-btn-block"
                    disabled={busy === 'save'}
                    onClick={() => save('rejected')}
                  >
                    Rejeter toute l'analyse
                  </button>
                </div>
              )}
              {analysis.model_info?.disclaimer && (
                <p style={{ color: 'var(--clinic-muted)', fontSize: 13, margin: '14px 0 0' }}>
                  {analysis.model_info.disclaimer}
                </p>
              )}
            </div>
          </aside>
        </div>
      )}

      {rg.symptoms && queries.length === 0 && (
        <section className="clinic-card" style={{ marginTop: 24 }}>
          <div className="clinic-card-body">
            <p style={{ marginTop: 0 }}>Aucune recherche bibliographique pour ces symptômes.</p>
            <button className="clinic-btn clinic-btn-ghost" onClick={askAssistant} disabled={busy === 'assistant'}>
              {busy === 'assistant' ? 'Recherche…' : 'Rechercher dans la littérature'}
            </button>
          </div>
        </section>
      )}
      <AssistantPanel queries={queries} />
    </>
  )
}
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Printer } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDate, fullName } from '../../lib/format'
import { KINDS } from '../../lib/labels'
import { labelFr, pct } from '../../lib/findings'
import { REPORT_DISCLAIMER } from '../../lib/report'

const snapshot = (title, content) => JSON.stringify([title, content])

function Section({ title, hint, value, onChange, readOnly }) {
  return (
    <section className="clinic-card report-block">
      <div className="clinic-card-header">
        <h2 className="clinic-card-title">{title}</h2>
      </div>
      <div className="clinic-card-body">
        {readOnly ? (
          <p className="report-text">{value || '—'}</p>
        ) : (
          <textarea
            className="clinic-input"
            placeholder={hint}
            value={value}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      </div>
    </section>
  )
}

export default function ReportEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, profile } = useAuth()
  const [report, setReport] = useState(null)
  const [patient, setPatient] = useState(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState(null)
  const [saved, setSaved] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const dirty = !!content && snapshot(title, content) !== saved

  async function load() {
    const { data: r, error: e } = await supabase.from('reports').select('*').eq('id', id).maybeSingle()
    if (e) { setError(e.message); setLoading(false); return }
    if (!r) { setLoading(false); return }
    setReport(r)
    setTitle(r.title)
    setContent(r.content)
    setSaved(snapshot(r.title, r.content))
    const { data: p } = await supabase
      .from('patients').select('id, first_name, last_name').eq('id', r.patient_id).maybeSingle()
    setPatient(p)
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  // warn before leaving with unsaved changes
  useEffect(() => {
    if (!dirty) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const setField = (k) => (v) => { setNotice(''); setContent((c) => ({ ...c, [k]: v })) }

  async function save() {
    setBusy('save'); setError(''); setNotice('')
    const { data, error } = await supabase
      .from('reports')
      .update({ title, content, updated_at: new Date().toISOString() })
      .eq('id', id).eq('status', 'draft')
      .select('id')
    setBusy('')
    if (error) return setError(error.message)
    if (!data?.length) return setError("Enregistrement refusé : le rapport n'est plus un brouillon.")
    setSaved(snapshot(title, content))
    setNotice('Brouillon enregistré.')
  }

  async function sign() {
    const mock = content.meta?.mock_vision || content.meta?.mock_sources
    if (mock && !window.confirm('Ce rapport contient des résultats SIMULÉS (mode démo). Le signer quand même ?')) return
    if (!window.confirm('Signer ce rapport ? Il ne pourra plus être modifié ni supprimé.')) return

    setBusy('sign'); setError('')
    const signedContent = {
      ...content,
      meta: { ...content.meta, signed_by: profile?.full_name || user.email },
    }
    const { data, error } = await supabase
      .from('reports')
      .update({
        title,
        content: signedContent,
        status: 'signed',
        signed_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq('id', id).eq('status', 'draft')
      .select('id')
    setBusy('')
    if (error) return setError(error.message)
    if (!data?.length) return setError('Signature refusée.')
    setNotice('')
    load()
  }

  async function remove() {
    if (!window.confirm('Supprimer ce brouillon ? Cette action est définitive.')) return
    setBusy('delete'); setError('')
    const { error } = await supabase.from('reports').delete().eq('id', id).eq('status', 'draft')
    setBusy('')
    if (error) return setError(error.message)
    navigate(report ? `/patients/${report.patient_id}` : '/reports')
  }

  if (loading) return <div className="clinic-loading">Chargement…</div>
  if (!report) return <div className="clinic-empty">Rapport introuvable. <Link to="/reports">Retour</Link></div>

  const signed = report.status === 'signed'
  const meta = content.meta ?? {}
  const citations = report.citations ?? []

  return (
    <div className="clinic-report">
      <Link to={`/patients/${report.patient_id}`} className="clinic-back no-print">
        <ArrowLeft size={18} /> Dossier de {fullName(patient)}
      </Link>

      <div className="clinic-file-head">
        <div style={{ flex: 1, minWidth: 260 }}>
          {signed ? (
            <h1 className="clinic-page-title" style={{ marginBottom: 2 }}>{title}</h1>
          ) : (
            <input
              className="clinic-input report-title-input"
              value={title}
              onChange={(e) => { setNotice(''); setTitle(e.target.value) }}
              aria-label="Titre du rapport"
            />
          )}
          <p className="clinic-page-sub" style={{ margin: '6px 0 0' }}>
            {fullName(patient)} ·{' '}
            <span className={'clinic-pill ' + (signed ? 'ok' : 'info')}>{signed ? 'Signé' : 'Brouillon'}</span>
            {dirty && <span style={{ marginLeft: 10, color: 'var(--clinic-danger)' }}>Modifications non enregistrées</span>}
          </p>
        </div>
        <div className="clinic-actions no-print">
          {signed ? (
            <button className="clinic-btn clinic-btn-ghost" onClick={() => window.print()}>
              <Printer size={18} /> Imprimer / PDF
            </button>
          ) : (
            <>
              <button className="clinic-btn clinic-btn-ghost" onClick={save} disabled={!dirty || busy === 'save'}>
                {busy === 'save' ? 'Enregistrement…' : 'Enregistrer'}
              </button>
              <button className="clinic-btn clinic-btn-primary" onClick={sign} disabled={busy === 'sign'}>
                {busy === 'sign' ? 'Signature…' : 'Signer'}
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="clinic-error">{error}</p>}
      {notice && <p className="clinic-success">{notice}</p>}

      {(meta.mock_vision || meta.mock_sources) && (
        <div className="clinic-notice">
          <strong>Contenu simulé.</strong>
          <span>
            {meta.mock_vision && 'Les zones détectées proviennent du mode démo. '}
            {meta.mock_sources && 'Les sources sont des extraits fictifs. '}
            Ne pas utiliser en situation réelle.
          </span>
        </div>
      )}

      {signed && (
        <div className="clinic-success" style={{ margin: '0 0 20px' }}>
          Signé le {fmtDate(report.signed_at)} par {meta.signed_by || 'le praticien'}.
        </div>
      )}

      <Section
        title="Motif de consultation / symptômes"
        hint="Symptômes rapportés par le patient"
        value={content.motif}
        onChange={setField('motif')}
        readOnly={signed}
      />

      <section className="clinic-card report-block">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">
            Résultats validés
            <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>
              {' '}· {KINDS[content.radiograph?.kind] ?? 'Radiographie'}
              {content.radiograph?.taken_at ? ` du ${fmtDate(content.radiograph.taken_at)}` : ''}
            </span>
          </h2>
          {content.radiograph?.id && (
            <Link to={`/analysis/${content.radiograph.id}`} className="clinic-btn clinic-btn-ghost no-print">
              Voir l'image
            </Link>
          )}
        </div>
        {content.findings.length === 0 ? (
          <div className="clinic-empty">Aucune zone acceptée par le praticien.</div>
        ) : (
          <table className="clinic-table">
            <thead>
              <tr><th>#</th><th>Résultat</th><th>Dent</th><th>Confiance IA</th></tr>
            </thead>
            <tbody>
              {content.findings.map((f) => (
                <tr key={f.id}>
                  <td>{f.id}</td>
                  <td className="clinic-patient-name">
                    {labelFr(f.label)}{f.depth === 'possibly deep' && ' (possiblement profonde)'}
                  </td>
                  <td>{f.tooth_fdi ? `${f.tooth_fdi} (estimée)` : '—'}</td>
                  <td>{pct(f.confidence)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {content.rejected_count > 0 && (
          <div className="clinic-card-body" style={{ color: 'var(--clinic-muted)', fontSize: 15 }}>
            {content.rejected_count} zone(s) proposée(s) par l'IA ont été rejetées par le praticien.
          </div>
        )}
      </section>

      <Section
        title="Observations cliniques"
        hint="Examen clinique, constatations, interprétation de l'image…"
        value={content.observations}
        onChange={setField('observations')}
        readOnly={signed}
      />
      <Section
        title="Diagnostic différentiel"
        hint="À rédiger par le praticien."
        value={content.differential}
        onChange={setField('differential')}
        readOnly={signed}
      />
      <Section
        title="Plan de traitement proposé"
        hint="À rédiger par le praticien."
        value={content.plan}
        onChange={setField('plan')}
        readOnly={signed}
      />

      <section className="clinic-card report-block">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Sources</h2>
        </div>
        <div className="clinic-card-body">
          {citations.length === 0 ? (
            <p style={{ margin: 0, color: 'var(--clinic-muted)' }}>
              Aucune source associée à ce rapport.
            </p>
          ) : (
            <ol className="clinic-sources">
              {citations.map((c) => (
                <li key={c.n}>
                  <div>
                    <strong>[{c.n}]</strong> {c.title}
                    <span style={{ color: 'var(--clinic-muted)' }}> — {c.journal}, {c.year}</span>
                    {c.doi && <span style={{ color: 'var(--clinic-muted)' }}> · DOI {c.doi}</span>}
                  </div>
                  <blockquote>{c.passage}</blockquote>
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>

      <p style={{ color: 'var(--clinic-muted)', fontSize: 14 }}>{REPORT_DISCLAIMER}</p>

      {!signed && (
        <button className="clinic-btn clinic-btn-ghost no-print" onClick={remove} disabled={busy === 'delete'}>
          Supprimer ce brouillon
        </button>
      )}
    </div>
  )
}
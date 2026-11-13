import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Printer, Trash2 } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDate, fullName } from '../../lib/format'
import { allergyWarnings, norm } from '../../lib/rx'
import MedSearch from './MedSearch'


// typing helpers only: they contain no amounts and no clinical advice
const FREQ = ['matin et soir', 'matin, midi et soir', 'pendant les repas', 'en cas de douleur', 'au coucher']
const DURATIONS = ['3 jours', '5 jours', '7 jours', '10 jours']

const snapshot = (c) => JSON.stringify(c)
const newLine = (m = {}) => ({
  key: crypto.randomUUID(),
  name: m.name ?? '', form: m.form ?? '', ingredients: m.ingredients ?? '',
  posology: m.posology ?? '', duration: m.duration ?? '', note: m.note ?? '',
})
const normalize = (c) => ({
  lines: (c?.lines ?? []).map((l) => ({ ...newLine(), ...l })),
  notes: c?.notes ?? '',
  meta: c?.meta ?? {},
})

function Sheet({ content, signedAt }) {
  const m = content.meta ?? {}
  const pr = m.prescriber ?? {}
  const pa = m.patient ?? {}
  return (
    <section className="clinic-card rx-sheet">
      {pr.practice_name && <div className="rx-cabinet">{pr.practice_name}</div>}

      <header className="rx-head">
        <div className="rx-col">
          <strong className="rx-doctor">{pr.full_name || pr.name}</strong>
          {pr.title_fr && <div>{pr.title_fr}</div>}
          {pr.extra_fr && <div className="rx-small">{pr.extra_fr}</div>}
        </div>
        <div className="rx-col rx-ar" dir="rtl" lang="ar">
          <strong className="rx-doctor">{pr.name_ar}</strong>
          {pr.title_ar && <div>{pr.title_ar}</div>}
          {pr.extra_ar && <div className="rx-small">{pr.extra_ar}</div>}
        </div>
      </header>

      <h2 className="rx-title">Ordonnance</h2>

      <div className="rx-meta">
  <div>Nom et prénom : <strong>{pa.name}</strong>{pa.birth_date ? `, né(e) le ${fmtDate(pa.birth_date)}` : ''}</div>
</div>

      <ol className="rx-lines">
        {content.lines.map((l) => (
          <li key={l.key}>
            <strong>{l.name}</strong>
            {l.form && !norm(l.name).includes(norm(l.form)) && <span className="rx-muted"> ({l.form})</span>}
            <div>{[l.posology, l.duration && `pendant ${l.duration}`].filter(Boolean).join(', ')}</div>
            {l.note && <div className="rx-muted">{l.note}</div>}
          </li>
        ))}
      </ol>
      {content.notes && <p style={{ whiteSpace: 'pre-wrap' }}>{content.notes}</p>}

<div className="rx-sign">
  Signature et cachet
  <div className="rx-sign-date">Le {fmtDate(signedAt)}</div>
</div>      <footer className="rx-foot">
        <div className="rx-foot-cols">
          <div style={{ whiteSpace: 'pre-line' }}>{pr.practice_address}</div>
          <div dir="rtl" lang="ar" style={{ whiteSpace: 'pre-line' }}>{pr.practice_address_ar}</div>
        </div>
        <div className="rx-foot-line">
          {[pr.practice_phone && `Tél. ${pr.practice_phone}`, pr.practice_email].filter(Boolean).join('  ·  ')}
        </div>
      </footer>
    </section>
  )
}

export default function PrescriptionEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [rx, setRx] = useState(null)
  const [patient, setPatient] = useState(null)
  const [pro, setPro] = useState(null)
  const [templates, setTemplates] = useState([])
  const [content, setContent] = useState(null)
  const [saved, setSaved] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const dirty = !!content && snapshot(content) !== saved

  async function load() {
    const { data: r, error: e } = await supabase.from('prescriptions').select('*').eq('id', id).maybeSingle()
    if (e) { setError(e.message); setLoading(false); return }
    if (!r) { setLoading(false); return }
    const c = normalize(r.content)
    setRx(r); setContent(c); setSaved(snapshot(c))

    const [p, t, pf] = await Promise.all([
      supabase.from('patients').select('id, first_name, last_name, birth_date, medical_history')
        .eq('id', r.patient_id).maybeSingle(),
      supabase.from('rx_templates').select('id, name, lines').order('name'),
      supabase.from('profiles').select('*').eq('id', user.id).single(),
    ])
    setPatient(p.data); setTemplates(t.data ?? []); setPro(pf.data)
    setLoading(false)
  }

  useEffect(() => { load() }, [id])

  useEffect(() => {
    if (!dirty) return
    const handler = (e) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const warnings = useMemo(
    () => (patient && content ? allergyWarnings(patient.medical_history, content.lines) : []),
    [patient, content]
  )

  const edit = (fn) => { setNotice(''); setContent((c) => fn(c)) }
  const setLine = (i, patch) =>
    edit((c) => ({ ...c, lines: c.lines.map((l, j) => (j === i ? { ...l, ...patch } : l)) }))
  const removeLine = (i) => edit((c) => ({ ...c, lines: c.lines.filter((_, j) => j !== i) }))
  const addMed = (m) => edit((c) => ({ ...c, lines: [...c.lines, newLine(m)] }))
  const addTemplate = (t) => edit((c) => ({ ...c, lines: [...c.lines, ...t.lines.map((l) => newLine(l))] }))

  async function saveTemplate() {
    const name = window.prompt('Nom du modèle (ex : après extraction)')
    if (!name?.trim()) return
    const lines = content.lines.map(({ name, form, ingredients, posology, duration, note }) =>
      ({ name, form, ingredients, posology, duration, note }))
    const { data, error } = await supabase
      .from('rx_templates').insert({ doctor_id: user.id, name: name.trim(), lines }).select('id, name, lines').single()
    if (error) return setError(error.message)
    setTemplates((t) => [...t, data].sort((a, b) => a.name.localeCompare(b.name)))
    setNotice('Modèle enregistré.')
  }

  async function deleteTemplate(t) {
    if (!window.confirm(`Supprimer le modèle « ${t.name} » ?`)) return
    const { error } = await supabase.from('rx_templates').delete().eq('id', t.id)
    if (error) return setError(error.message)
    setTemplates((list) => list.filter((x) => x.id !== t.id))
  }

  async function save() {
    setBusy('save'); setError(''); setNotice('')
    const { data, error } = await supabase
      .from('prescriptions').update({ content }).eq('id', id).eq('status', 'draft').select('id')
    setBusy('')
    if (error) return setError(error.message)
    if (!data?.length) return setError("Enregistrement refusé : l'ordonnance n'est plus un brouillon.")
    setSaved(snapshot(content))
    setNotice('Brouillon enregistré.')
  }

  async function sign() {
    setError('')
    if (content.lines.length === 0) return setError('Ajoutez au moins un médicament.')
    if (content.lines.some((l) => !l.name.trim())) return setError("Une ligne n'a pas de nom de médicament.")
    if (!pro?.full_name?.trim() || pro.full_name.includes('@'))
      return setError('Renseignez votre nom dans Paramètres avant de signer.')
    
    if (warnings.length &&
        !window.confirm('Des alertes sont affichées sur cette ordonnance. Signer quand même ?')) return
    if (!window.confirm('Signer cette ordonnance ? Elle ne pourra plus être modifiée ni supprimée.')) return

    setBusy('sign')
    const signedContent = {
      ...content,
      meta: {
        prescriber: { ...pro },
        patient: { name: fullName(patient), birth_date: patient.birth_date },
        signed_by: pro.full_name,
      },
    }
    const { data, error } = await supabase
      .from('prescriptions')
      .update({ content: signedContent, status: 'signed', signed_at: new Date().toISOString() })
      .eq('id', id).eq('status', 'draft').select('id')
    setBusy('')
    if (error) return setError(error.message)
    if (!data?.length) return setError('Signature refusée.')
    load()
  }

  async function remove() {
    if (!window.confirm('Supprimer ce brouillon ? Cette action est définitive.')) return
    const { error } = await supabase.from('prescriptions').delete().eq('id', id).eq('status', 'draft')
    if (error) return setError(error.message)
    navigate(`/patients/${rx.patient_id}`)
  }

  if (loading) return <div className="clinic-loading">Chargement…</div>
  if (!rx) return <div className="clinic-empty">Ordonnance introuvable. <Link to="/prescriptions">Retour</Link></div>

  const signed = rx.status === 'signed'

  return (
    <div className="clinic-report">
      <Link to={`/patients/${rx.patient_id}`} className="clinic-back no-print">
        <ArrowLeft size={18} /> Dossier de {fullName(patient)}
      </Link>

      <div className="clinic-file-head no-print">
        <div>
          <h1 className="clinic-page-title" style={{ marginBottom: 2 }}>Ordonnance</h1>
          <p className="clinic-page-sub" style={{ margin: 0 }}>
            {fullName(patient)} ·{' '}
            <span className={'clinic-pill ' + (signed ? 'ok' : 'info')}>{signed ? 'Signée' : 'Brouillon'}</span>
            {dirty && <span style={{ marginLeft: 10, color: 'var(--clinic-danger)' }}>Modifications non enregistrées</span>}
          </p>
        </div>
        <div className="clinic-actions">
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

      {error && <p className="clinic-error no-print">{error}</p>}
      {notice && <p className="clinic-success no-print">{notice}</p>}

      {signed ? (
        <Sheet content={content} signedAt={rx.signed_at} />
      ) : (
        <>
          {warnings.length > 0 && (
            <div className="clinic-warn">
              <strong>À vérifier avant de signer</strong>
              <ul>{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              <small>Aide non exhaustive, basée sur le texte des antécédents. Elle ne remplace pas votre vérification.</small>
            </div>
          )}

          <section className="clinic-card report-block">
            <div className="clinic-card-header"><h2 className="clinic-card-title">Médicaments</h2></div>
            <div className="clinic-card-body">
              <MedSearch onPick={addMed} />

              {templates.length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <small style={{ color: 'var(--clinic-muted)' }}>Mes modèles (cliquer pour ajouter)</small>
                  <div className="rx-chips">
                    {templates.map((t) => (
                      <span key={t.id} className="rx-chip rx-tpl">
                        <button type="button" onClick={() => addTemplate(t)}>{t.name}</button>
                        <button type="button" onClick={() => deleteTemplate(t)} aria-label="Supprimer le modèle">×</button>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {content.lines.length === 0 ? (
                <p style={{ color: 'var(--clinic-muted)', marginBottom: 0 }}>
                  Aucun médicament. Cherchez-en un ci-dessus ou ajoutez un de vos modèles.
                </p>
              ) : (
                content.lines.map((l, i) => (
                  <div className="rx-line" key={l.key}>
                    <div className="rx-line-head">
                      <strong>{i + 1}.</strong>
                      <input className="clinic-input" value={l.name} placeholder="Médicament"
                        aria-label="Médicament" onChange={(e) => setLine(i, { name: e.target.value })} />
                      <button type="button" className="clinic-btn clinic-btn-ghost" aria-label="Retirer la ligne"
                        onClick={() => removeLine(i)}><Trash2 size={18} /></button>
                    </div>
                    {l.form && <small className="rx-muted">{l.form}</small>}
                    <div className="rx-grid">
                      <div className="clinic-field">
                        <label htmlFor={`pos-${l.key}`}>Posologie</label>
                        <input id={`pos-${l.key}`} className="clinic-input" value={l.posology}
                          onChange={(e) => setLine(i, { posology: e.target.value })} />
                        <div className="rx-chips">
                          {FREQ.map((f) => (
                            <button type="button" key={f} className="rx-chip"
                              onClick={() => setLine(i, { posology: `${l.posology} ${f}`.trim() })}>{f}</button>
                          ))}
                        </div>
                      </div>
                      <div className="clinic-field">
                        <label htmlFor={`dur-${l.key}`}>Durée</label>
                        <input id={`dur-${l.key}`} className="clinic-input" value={l.duration}
                          onChange={(e) => setLine(i, { duration: e.target.value })} />
                        <div className="rx-chips">
                          {DURATIONS.map((d) => (
                            <button type="button" key={d} className="rx-chip"
                              onClick={() => setLine(i, { duration: d })}>{d}</button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <input className="clinic-input" value={l.note} placeholder="Remarque (facultatif)"
                      aria-label="Remarque" onChange={(e) => setLine(i, { note: e.target.value })} />
                  </div>
                ))
              )}

              {content.lines.length > 0 && (
                <button type="button" className="clinic-btn clinic-btn-ghost" style={{ marginTop: 14 }} onClick={saveTemplate}>
                  Enregistrer comme modèle
                </button>
              )}
            </div>
          </section>

          <section className="clinic-card report-block">
            <div className="clinic-card-header"><h2 className="clinic-card-title">Conseils / remarques</h2></div>
            <div className="clinic-card-body">
              <textarea className="clinic-input" value={content.notes}
                placeholder="Ex : conseils post-opératoires, prochain rendez-vous…"
                onChange={(e) => edit((c) => ({ ...c, notes: e.target.value }))} />
            </div>
          </section>

          <p style={{ color: 'var(--clinic-muted)', fontSize: 14 }}>
            Ordonnance établie sous la responsabilité du praticien. L'application ne suggère aucun médicament ni aucune posologie.
          </p>
          <button className="clinic-btn clinic-btn-ghost" onClick={remove}>Supprimer ce brouillon</button>
        </>
      )}
    </div>
  )
}
import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { supabase } from '../../lib/supabase'
import { api } from '../../lib/api'
import { fmtDateTime } from '../../lib/format'
import Pager from '../../components/Pager'
import { usePager } from '../../lib/usePager'

const STATUS = {
  running: { text: 'En cours', cls: 'info' },
  completed: { text: 'Terminée', cls: 'ok' },
  stopped: { text: 'Limite de pas', cls: '' },
  failed: { text: 'Échec', cls: 'danger' },
}
const ACTION = {
  search_pubmed: 'Recherche PubMed', review: "Revue d'un article", rate: 'Évaluation', notify: 'Notification',
  finish: 'Fin', read_source: "Lecture d'une source d'événements", error: 'Erreur',
}
const DETAILS_KEY = 'dentia.agent.details'

function Step({ s }) {
  const obs = typeof s.observation === 'string' ? s.observation : JSON.stringify(s.observation ?? '')
  return (
    <li className="agent-step">
      <div>
        <strong>{s.n}. {ACTION[s.action] ?? s.action}</strong>
        {s.args && Object.keys(s.args).length > 0 && <code className="agent-args">{JSON.stringify(s.args)}</code>}
      </div>
      {s.thought && <small className="rx-muted">« {s.thought} »</small>}
      <code className="agent-obs">{obs.length > 420 ? obs.slice(0, 420) + '…' : obs}</code>
    </li>
  )
}

export default function AgentJournal() {
  const [runs, setRuns] = useState([])
  const [open, setOpen] = useState(null)
  const [dry, setDry] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [details, setDetails] = useState(() => {
    try { return localStorage.getItem(DETAILS_KEY) === '1' } catch { return false }
  })
  const wasRunning = useRef(false)
  const pager = usePager(runs, 5)

  async function load() {
    const { data, error } = await supabase.from('agent_runs')
      .select('id, status, summary, goal, model, steps, notified, dry_run, created_at, finished_at')
      .eq('agent', 'watch').order('created_at', { ascending: false }).limit(30)
    if (error) setError(error.message)
    else setRuns(data)
  }

  const running = runs.some((r) => r.status === 'running')
  useEffect(() => { load() }, [])
  useEffect(() => {
    if (!running && wasRunning.current) window.dispatchEvent(new Event('notifs-changed'))   // refresh the counters
    wasRunning.current = running
    // fast while a run is going, slow otherwise (also catches the daily automatic run)
    const t = setInterval(load, running ? 3000 : 20000)
    return () => clearInterval(t)
  }, [running])

  function toggleDetails() {
    const next = !details
    setDetails(next)
    try { localStorage.setItem(DETAILS_KEY, next ? '1' : '0') } catch { /* storage may be blocked */ }
  }

  async function start() {
    setBusy(true); setError('')
    try {
      const { run_id } = await api('/agent/watch/run', { method: 'POST', body: JSON.stringify({ dry_run: dry }) })
      setOpen(run_id)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const last = runs.find((r) => !r.dry_run && r.status !== 'running')

  return (
    <section className="clinic-card" style={{ marginTop: 24 }}>
      <div className="clinic-card-header">
        <h2 className="clinic-card-title">Veille automatique</h2>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          {running && <span className="agent-live"><span className="agent-spinner" />Analyse en cours…</span>}
          <button className="clinic-btn clinic-btn-primary" onClick={start} disabled={busy || running}>
            {running ? 'Veille en cours…' : 'Lancer la veille'}
          </button>
        </div>
      </div>

      <div className="clinic-card-body" style={{ paddingBottom: details ? 0 : undefined }}>
        <p style={{ margin: 0, color: 'var(--clinic-muted)' }}>
          Chaque jour, l'agent cherche les nouvelles publications et les congrès qui vous concernent
          (réglages dans Paramètres).
        </p>
        {!running && last && (
          <p style={{ margin: '8px 0 0', color: 'var(--clinic-muted)' }}>
            Dernière veille : {fmtDateTime(last.finished_at || last.created_at)} ·{' '}
            {last.status === 'failed' ? 'échec, réessayez plus tard' : `${last.notified} notification(s)`}
          </p>
        )}
        {error && <p className="clinic-error">{error}</p>}
        <button className="clinic-btn clinic-btn-ghost" style={{ marginTop: 12 }} onClick={toggleDetails}
                aria-expanded={details}>
          {details ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          {details ? "Masquer le détail de l'agent" : "Afficher le détail de l'agent"}
        </button>
      </div>

      {details && (
        <>
          <div className="clinic-card-body" style={{ paddingBottom: 0 }}>
            <p style={{ margin: '0 0 10px', color: 'var(--clinic-muted)' }}>
              L'agent choisit lui-même ses recherches selon vos centres d'intérêt, évalue les nouveaux articles puis
              vous notifie des plus utiles. Chaque étape de son raisonnement est consignée ci-dessous. Il n'a accès à
              aucune donnée patient.
            </p>
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={dry} onChange={(e) => setDry(e.target.checked)} />
              Simulation (n'écrit rien)
            </label>
          </div>

          {runs.length === 0 ? (
            <div className="clinic-empty">Aucune exécution pour le moment.</div>
          ) : (
            <>
              <ul className="agent-runs">
                {pager.slice.map((r) => {
                  const s = STATUS[r.status]
                  return (
                    <li key={r.id} className="agent-run">
                      <div className="agent-run-head" onClick={() => setOpen(open === r.id ? null : r.id)}>
                        <span>{fmtDateTime(r.created_at)}{r.dry_run && ' · simulation'}</span>
                        <span><span className={`clinic-pill ${s.cls}`}>{s.text}</span> · {r.steps?.length ?? 0} pas</span>
                      </div>
                      {r.summary && <div className="rx-muted">{r.summary}</div>}
                      {open === r.id && (
                        <>
                          <ol className="agent-steps">{(r.steps ?? []).map((st) => <Step key={st.n} s={st} />)}</ol>
                          <small className="rx-muted">Modèle : {r.model || '—'}</small>
                        </>
                      )}
                    </li>
                  )
                })}
              </ul>
              <Pager pager={pager} />
            </>
          )}
        </>
      )}
    </section>
  )
}
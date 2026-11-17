import { useEffect, useRef, useState } from 'react'
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
const ACTION = { search_pubmed: 'Recherche PubMed', review: "Revue d'un article", rate: 'Évaluation', notify: 'Notification', finish: 'Fin', error: 'Erreur' }
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
  const [dry, setDry] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
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
    if (!running) {
      if (wasRunning.current) window.dispatchEvent(new Event('notifs-changed'))   // refresh the bell
      wasRunning.current = false
      return
    }
    wasRunning.current = true
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [running])

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

  return (
    <section className="clinic-card" style={{ marginTop: 24 }}>
      <div className="clinic-card-header">
        <h2 className="clinic-card-title">Agent de veille</h2>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input type="checkbox" checked={dry} onChange={(e) => setDry(e.target.checked)} />
            Simulation (n'écrit rien)
          </label>
          <button className="clinic-btn clinic-btn-primary" onClick={start} disabled={busy || running}>
            {running ? 'En cours…' : 'Lancer la veille'}
          </button>
        </div>
      </div>
      <div className="clinic-card-body" style={{ paddingBottom: 0 }}>
        <p style={{ margin: 0, color: 'var(--clinic-muted)' }}>
          L'agent choisit lui-même ses recherches selon vos centres d'intérêt, évalue les nouveaux articles puis vous
          notifie des plus utiles. Chaque étape de son raisonnement est consignée ci-dessous. Il n'a accès à aucune
          donnée patient.
        </p>
        {error && <p className="clinic-error">{error}</p>}
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
    </section>
  )
}
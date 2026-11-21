import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { api } from '../../lib/api'
import { fmtDate } from '../../lib/format'
import { useTopK } from '../../lib/topk'
import TopKSelect from '../analysis/TopKSelect'
import AssistantPanel from '../analysis/AssistantPanel'

export default function Assistant() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useTopK()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [current, setCurrent] = useState(null)
  const [history, setHistory] = useState([])

  async function loadHistory() {
    const { data, error } = await supabase
      .from('assistant_queries')
      .select('id, question, answer, citations, insufficient_evidence, llm_model, created_at')
      .is('patient_id', null)
      .order('created_at', { ascending: false })
      .limit(15)
    if (!error) setHistory(data)
  }
  useEffect(() => { loadHistory() }, [])

  async function ask(e) {
    e.preventDefault()
    const q = question.trim()
    if (q.length < 3 || busy) return
    setBusy(true)
    setError('')
    try {
      const saved = await api('/assistant', {
        method: 'POST',
        body: JSON.stringify({ question: q, top_k: topK }),
      })
      setCurrent(saved)
      setQuestion('')
      loadHistory()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1 className="clinic-page-title">Assistant clinique</h1>
      <p className="clinic-page-sub">
        Posez une question de pratique clinique : la réponse s'appuie uniquement sur les articles de la base,
        avec les sources citées. N'écrivez pas d'informations permettant d'identifier un patient.
      </p>

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-body">
          <form onSubmit={ask} className="clinic-form-grid">
            <div className="clinic-field clinic-col-12">
              <label htmlFor="q">Votre question</label>
              <textarea id="q" className="clinic-input" rows={3} maxLength={2000}
                placeholder="Ex. : Quelle est l'efficacité de l'amoxicilline avant la pose d'implants ?"
                value={question} onChange={(e) => setQuestion(e.target.value)} />
            </div>
            <div className="clinic-col-6">
              <TopKSelect value={topK} onChange={setTopK} />
            </div>
            <div className="clinic-col-6 clinic-form-submit">
              <button className="clinic-btn clinic-btn-primary" disabled={busy || question.trim().length < 3}>
                {busy ? 'Recherche en cours…' : 'Rechercher dans la littérature'}
              </button>
            </div>
          </form>
          {error && <p className="clinic-error">{error}</p>}
        </div>
      </section>

      {current && <AssistantPanel queries={[current]} />}

      {history.length > 0 && (
        <section className="clinic-card" style={{ marginTop: 24 }}>
          <div className="clinic-card-header">
            <h2 className="clinic-card-title">Questions récentes</h2>
          </div>
          <ul className="clinic-finding-list" style={{ maxHeight: 'none' }}>
            {history.map((h) => (
              <li key={h.id}
                className={'clinic-finding' + (current?.id === h.id ? ' selected' : '')}
                onClick={() => setCurrent(h)}>
                <strong>{h.question}</strong>
                <span style={{ color: 'var(--clinic-muted)', fontSize: 15 }}>
                  {fmtDate(h.created_at)} ·{' '}
                  {h.insufficient_evidence ? 'pas assez de preuves' : `${h.citations?.length ?? 0} source(s)`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
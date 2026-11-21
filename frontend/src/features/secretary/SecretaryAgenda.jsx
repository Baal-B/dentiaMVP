import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { APPT_STATUS } from '../../lib/labels'
import Pager from '../../components/Pager'
import { usePager } from '../../lib/usePager'
import { displayStatus, isPast } from '../../lib/apptStatus'

const day = (iso) => new Date(iso).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })
const hm = (iso) => new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

export default function SecretaryAgenda() {
  const [appts, setAppts] = useState([])
  const [patients, setPatients] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const pager = usePager(appts, 15)

  async function load() {
    const from = new Date(); from.setHours(0, 0, 0, 0)
    const to = new Date(from.getTime() + 30 * 86400000)
    const [a, p] = await Promise.all([
      supabase.from('appointments')
        .select('id, patient_id, starts_at, ends_at, status, reason')   // not "notes"
        .gte('starts_at', from.toISOString()).lt('starts_at', to.toISOString()).order('starts_at'),
      supabase.from('patients_basic').select('id, first_name, last_name, phone').limit(1000),
    ])
    const err = a.error || p.error
    if (err) setError(err.message)
    else { setAppts(a.data); setPatients(Object.fromEntries(p.data.map((x) => [x.id, x]))) }
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  async function setStatus(a, status, question) {
    if (!window.confirm(question)) return
    const { error } = await supabase.from('appointments').update({ status }).eq('id', a.id)
    if (error) return setError(error.message)
    load()
  }

  // group the visible page by day
  const groups = []
  for (const a of pager.slice) {
    const d = day(a.starts_at)
    if (!groups.length || groups[groups.length - 1].d !== d) groups.push({ d, items: [] })
    groups[groups.length - 1].items.push(a)
  }

  return (
    <>
      <h1 className="clinic-page-title">Agenda</h1>
      <p className="clinic-page-sub">Les 30 prochains jours.</p>
      {error && <p className="clinic-error">{error}</p>}
      {loading ? (
        <div className="clinic-loading">Chargement…</div>
      ) : appts.length === 0 ? (
        <div className="clinic-empty">Aucun rendez-vous à venir.</div>
      ) : (
        <>
          {groups.map((g) => (
            <section className="clinic-card" style={{ marginBottom: 16 }} key={g.d}>
              <div className="clinic-card-header">
                <h2 className="clinic-card-title" style={{ textTransform: 'capitalize' }}>{g.d}</h2>
              </div>
              <table className="clinic-table">
                <tbody>
                  {g.items.map((a) => {
                    const p = patients[a.patient_id]
                    const s = displayStatus(a, APPT_STATUS)
                    return (
                      <tr key={a.id}>
                        <td>{hm(a.starts_at)} – {hm(a.ends_at)}</td>
                        <td className="clinic-patient-name">{p ? `${p.last_name} ${p.first_name}` : '—'}</td>
                        <td className="rx-muted">{p?.phone || ''}</td>
                        <td className="rx-muted">{a.reason || '—'}</td>
                        <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
                        <td>
                          {a.status === 'scheduled' && (
                            <>
                              <button className="clinic-btn clinic-btn-ghost"
                                onClick={() => setStatus(a, 'cancelled', 'Annuler ce rendez-vous ?')}>Annuler</button>
                              <button className="clinic-btn clinic-btn-ghost"
                                onClick={() => setStatus(a, 'no_show', 'Marquer le patient comme absent ?')}>Absent</button>
                            </>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </section>
          ))}
          <Pager pager={pager} />
        </>
      )}
    </>
  )
}
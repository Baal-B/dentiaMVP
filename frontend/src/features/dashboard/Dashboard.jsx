import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { fmtDateTime, fullName } from '../../lib/format'

function todayRange() {
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  const end = new Date(start)
  end.setDate(end.getDate() + 1)
  return [start.toISOString(), end.toISOString()]
}

const head = { count: 'exact', head: true }

export default function Dashboard() {
  const { profile } = useAuth()
  const [stats, setStats] = useState(null)
  const [upcoming, setUpcoming] = useState([])
  const [names, setNames] = useState({})
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      const [start, end] = todayRange()
      const results = await Promise.all([
        supabase.from('patients').select('*', head),
        supabase.from('appointments').select('*', head)
          .eq('status', 'scheduled').gte('starts_at', start).lt('starts_at', end),
        supabase.from('radiographs').select('*', head),
        supabase.from('analyses').select('*', head)
          .eq('status', 'completed').eq('validation_status', 'pending'),
        supabase.from('appointments')
          .select('id, starts_at, reason, patient_id')
          .eq('status', 'scheduled').gte('starts_at', new Date().toISOString())
          .order('starts_at').limit(5),
      ])

      const failed = results.find((r) => r.error)
      if (failed) return setError(failed.error.message)

      const [patients, today, radiographs, toValidate, next] = results
      setStats({
        patients: patients.count,
        today: today.count,
        radiographs: radiographs.count,
        toValidate: toValidate.count,
      })
      setUpcoming(next.data)

      const ids = [...new Set(next.data.map((a) => a.patient_id))]
      if (ids.length) {
        const { data } = await supabase
          .from('patients').select('id, first_name, last_name').in('id', ids)
        setNames(Object.fromEntries((data ?? []).map((p) => [p.id, p])))
      }
    }
    load()
  }, [])

  const firstName = profile?.full_name?.split(' ')[0]

  return (
    <>
      <h1 className="clinic-page-title">Bonjour{firstName ? `, ${firstName}` : ''}</h1>
      <p className="clinic-page-sub">Voici l'aperçu de votre activité.</p>

      <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
        <Link to="/analysis" className="clinic-btn clinic-btn-primary">Nouvelle analyse</Link>
        <Link to="/appointments" className="clinic-btn clinic-btn-ghost">Nouveau rendez-vous</Link>
      </div>

      {error && <p className="clinic-error">{error}</p>}

      <div className="clinic-stats">
        <Link to="/patients" className="clinic-card clinic-stat">
          <div className="clinic-stat-label">Patients</div>
          <div className="clinic-stat-value">{stats?.patients ?? '…'}</div>
        </Link>
        <Link to="/appointments" className="clinic-card clinic-stat">
          <div className="clinic-stat-label">Rendez-vous aujourd'hui</div>
          <div className="clinic-stat-value">{stats?.today ?? '…'}</div>
        </Link>
        <Link to="/analysis" className="clinic-card clinic-stat">
          <div className="clinic-stat-label">Radiographies</div>
          <div className="clinic-stat-value">{stats?.radiographs ?? '…'}</div>
        </Link>
        <Link to="/analysis" className="clinic-card clinic-stat">
          <div className="clinic-stat-label">Analyses à valider</div>
          <div className="clinic-stat-value">{stats?.toValidate ?? '…'}</div>
        </Link>
      </div>

      <section className="clinic-card">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Prochains rendez-vous</h2>
          <Link to="/appointments" className="clinic-btn clinic-btn-ghost">Voir tout</Link>
        </div>
        {upcoming.length === 0 ? (
          <div className="clinic-empty">Aucun rendez-vous à venir.</div>
        ) : (
          <table className="clinic-table">
            <tbody>
              {upcoming.map((a) => (
                <tr key={a.id}>
                  <td className="clinic-patient-name">{fullName(names[a.patient_id])}</td>
                  <td>{fmtDateTime(a.starts_at)}</td>
                  <td style={{ color: 'var(--clinic-muted)' }}>{a.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
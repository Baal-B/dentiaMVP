import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { fmtDate, fullName } from '../../lib/format'
import { REPORT_STATUS } from '../../lib/labels'

export default function Reports() {
  const [reports, setReports] = useState([])
  const [names, setNames] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      const { data, error } = await supabase
        .from('reports')
        .select('id, patient_id, title, status, created_at, signed_at')
        .order('created_at', { ascending: false })
        .limit(100)
      if (error) { setError(error.message); setLoading(false); return }
      setReports(data)
      const ids = [...new Set(data.map((r) => r.patient_id))]
      if (ids.length) {
        const { data: p } = await supabase
          .from('patients').select('id, first_name, last_name').in('id', ids)
        setNames(Object.fromEntries((p ?? []).map((x) => [x.id, x])))
      }
      setLoading(false)
    }
    load()
  }, [])

  return (
    <>
      <h1 className="clinic-page-title">Rapports</h1>
      <p className="clinic-page-sub">
        Les rapports se créent depuis une analyse validée.
      </p>
      {error && <p className="clinic-error">{error}</p>}
      <section className="clinic-card">
        {loading ? (
          <div className="clinic-loading">Chargement…</div>
        ) : reports.length === 0 ? (
          <div className="clinic-empty">
            Aucun rapport pour le moment.<br />
            <Link to="/analysis">Lancer une analyse</Link>, la valider, puis générer le rapport.
          </div>
        ) : (
          <table className="clinic-table">
            <thead>
              <tr><th>Rapport</th><th>Patient</th><th>Date</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {reports.map((r) => {
                const s = REPORT_STATUS[r.status]
                return (
                  <tr key={r.id}>
                    <td className="clinic-patient-name">
                      <Link to={`/reports/${r.id}`} className="clinic-link-name">{r.title || 'Sans titre'}</Link>
                    </td>
                    <td>{fullName(names[r.patient_id])}</td>
                    <td>{fmtDate(r.signed_at ?? r.created_at)}</td>
                    <td><span className={`clinic-pill ${s.cls}`}>{s.text}</span></td>
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
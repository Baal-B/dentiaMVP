import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export default function Cabinets() {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [data, setData] = useState({ items: [], total: 0, page_size: 12 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    const timer = setTimeout(() => {
      fetch(`${API}/public/doctors?q=${encodeURIComponent(q)}&page=${page}`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((d) => { setData(d); setError('') })
        .catch(() => setError('Impossible de charger les cabinets. Réessayez plus tard.'))
        .finally(() => setLoading(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [q, page])

  const pages = Math.max(1, Math.ceil(data.total / data.page_size))

  return (
    <div className="public-wrap wide">
      <h1 className="clinic-page-title">Trouver un cabinet dentaire</h1>
      <p className="clinic-page-sub">
        Choisissez un cabinet et envoyez une demande de rendez-vous. Le cabinet vous rappellera pour fixer l'heure.
      </p>

      <input className="clinic-input" placeholder="Ville, nom du praticien ou du cabinet…" value={q}
        onChange={(e) => { setQ(e.target.value); setPage(0) }} aria-label="Rechercher un cabinet" />

      {error && <p className="clinic-error">{error}</p>}

      {loading ? (
        <div className="clinic-loading">Chargement…</div>
      ) : data.items.length === 0 ? (
        <div className="clinic-empty" style={{ marginTop: 20 }}>Aucun cabinet trouvé.</div>
      ) : (
        <>
          <p style={{ color: 'var(--clinic-muted)' }}>{data.total} cabinet(s)</p>
          <div className="cab-grid">
            {data.items.map((c) => (
              <article className="clinic-card cab-card" key={c.booking_slug}>
                <div className="cab-names">
                  <div>
                    <strong>{c.full_name}</strong>
                    {c.title_fr && <div className="rx-muted">{c.title_fr}</div>}
                  </div>
                  {c.name_ar && (
                    <div dir="rtl" lang="ar" style={{ textAlign: 'right' }}>
                      <strong>{c.name_ar}</strong>
                      {c.title_ar && <div className="rx-muted">{c.title_ar}</div>}
                    </div>
                  )}
                </div>
                {c.practice_name && <div>{c.practice_name}</div>}
                <div className="rx-muted" style={{ whiteSpace: 'pre-line' }}>
                  {[c.practice_city, c.practice_address].filter(Boolean).join('\n')}
                </div>
                {c.practice_phone && <div>Tél. {c.practice_phone}</div>}
                <Link to={`/reserver/${c.booking_slug}`} className="clinic-btn clinic-btn-primary">
                  Demander un rendez-vous
                </Link>
              </article>
            ))}
          </div>
          {pages > 1 && (
            <div className="clinic-pager">
              <button type="button" className="clinic-btn clinic-btn-ghost" disabled={page === 0}
                onClick={() => setPage(page - 1)}>Précédent</button>
              <span>Page {page + 1} / {pages}</span>
              <button type="button" className="clinic-btn clinic-btn-ghost" disabled={page >= pages - 1}
                onClick={() => setPage(page + 1)}>Suivant</button>
            </div>
          )}
        </>
      )}

      <p style={{ marginTop: 32, color: 'var(--clinic-muted)', fontSize: 14 }}>
        Cette page sert uniquement à envoyer une demande. En cas d'urgence, appelez directement le cabinet ou les urgences.{' '}
        <Link to="/login">Espace professionnel</Link>
      </p>
    </div>
  )
}
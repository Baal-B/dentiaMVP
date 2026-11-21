import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, MapPin, Phone, CalendarCheck, PhoneCall, ShieldCheck } from 'lucide-react'
import logo from '../../assets/logo.png'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const initials = (name) =>
  (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0].toUpperCase()).join('')

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
      <header className="cab-hero">
        <img src={logo} alt="DentIA" className="cab-hero-logo" />
        <h1>Prenez soin de votre sourire</h1>
        <p>Trouvez un cabinet dentaire près de chez vous et envoyez votre demande de rendez-vous en quelques clics.</p>
        <div className="cab-search">
          <Search size={20} aria-hidden="true" />
          <input placeholder="Ville, nom du praticien ou du cabinet…" value={q}
            onChange={(e) => { setQ(e.target.value); setPage(0) }} aria-label="Rechercher un cabinet" />
        </div>
      </header>

      <ul className="cab-steps">
        <li>
          <MapPin size={22} aria-hidden="true" />
          <div><strong>1. Choisissez un cabinet</strong><span>Par ville ou par nom de praticien.</span></div>
        </li>
        <li>
          <CalendarCheck size={22} aria-hidden="true" />
          <div><strong>2. Envoyez votre demande</strong><span>Sans créer de compte, en 2 minutes.</span></div>
        </li>
        <li>
          <PhoneCall size={22} aria-hidden="true" />
          <div><strong>3. Le cabinet vous rappelle</strong><span>Pour confirmer le jour et l'heure.</span></div>
        </li>
      </ul>

      {error && <p className="clinic-error">{error}</p>}

      {loading ? (
        <div className="clinic-loading">Chargement…</div>
      ) : data.items.length === 0 ? (
        <div className="clinic-empty" style={{ marginTop: 20 }}>
          Aucun cabinet trouvé. Essayez une autre ville ou un autre nom.
        </div>
      ) : (
        <>
          <p className="cab-count">{data.total} cabinet{data.total > 1 ? 's' : ''} disponible{data.total > 1 ? 's' : ''}</p>
          <div className="cab-grid">
            {data.items.map((c) => (
              <article className="clinic-card cab-card" key={c.booking_slug}>
                <div className="cab-head">
                  <div className="cab-avatar" aria-hidden="true">{initials(c.full_name)}</div>
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
                </div>

                {c.practice_name && <div className="cab-practice">{c.practice_name}</div>}

                {(c.practice_city || c.practice_address) && (
                  <div className="cab-line">
                    <MapPin size={16} aria-hidden="true" />
                    <span style={{ whiteSpace: 'pre-line' }}>
                      {[c.practice_city, c.practice_address].filter(Boolean).join('\n')}
                    </span>
                  </div>
                )}
                {c.practice_phone && (
                  <div className="cab-line">
                    <Phone size={16} aria-hidden="true" />
                    <span>{c.practice_phone}</span>
                  </div>
                )}

                <Link to={`/reserver/${c.booking_slug}`} className="clinic-btn clinic-btn-primary cab-cta">
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

      <div className="cab-reassure">
        <ShieldCheck size={20} aria-hidden="true" />
        <p>
          Vos coordonnées sont transmises uniquement au cabinet choisi. Cette page sert à envoyer une demande :
          en cas d'urgence, appelez directement le cabinet ou les urgences.{' '}
          <Link to="/login">Espace professionnel</Link>
        </p>
      </div>
    </div>
  )
}
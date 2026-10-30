import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { fmtDateTime } from '../../lib/format'

export default function Notifications() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    const { data, error } = await supabase
      .from('notifications')
      .select('id, kind, title, body, link, read_at, created_at')
      .order('created_at', { ascending: false })
      .limit(100)
    if (error) setError(error.message)
    else setItems(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const changed = () => window.dispatchEvent(new Event('notifs-changed'))

  async function markRead(id) {
    const now = new Date().toISOString()
    setItems((list) => list.map((n) => (n.id === id && !n.read_at ? { ...n, read_at: now } : n)))
    await supabase.from('notifications').update({ read_at: now }).eq('id', id).is('read_at', null)
    changed()
  }

  async function markAll() {
    const { error } = await supabase
      .from('notifications').update({ read_at: new Date().toISOString() }).is('read_at', null)
    if (error) return setError(error.message)
    await load()
    changed()
  }

  const unread = items.filter((n) => !n.read_at).length

  return (
    <>
      <h1 className="clinic-page-title">Notifications</h1>
      <p className="clinic-page-sub">
        Nouvelles publications correspondant à vos centres d'intérêt.{' '}
        <Link to="/settings">Modifier mes centres d'intérêt</Link>
      </p>
      {error && <p className="clinic-error">{error}</p>}

      <section className="clinic-card">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">
            Boîte de réception{unread > 0 && <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}> ({unread} non lues)</span>}
          </h2>
          {unread > 0 && (
            <button className="clinic-btn clinic-btn-ghost" onClick={markAll}>Tout marquer comme lu</button>
          )}
        </div>

        {loading ? (
          <div className="clinic-loading">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="clinic-empty">
            Aucune notification pour le moment.<br />
            <Link to="/settings">Choisissez vos centres d'intérêt</Link> pour recevoir les nouveaux articles.
          </div>
        ) : (
          <ul className="clinic-notif-list">
            {items.map((n) => (
              <li
                key={n.id}
                className={'clinic-notif' + (n.read_at ? '' : ' unread')}
                onClick={() => !n.read_at && markRead(n.id)}
              >
                {n.link ? (
                  <a href={n.link} target="_blank" rel="noopener noreferrer" onClick={() => markRead(n.id)}>
                    <strong>{n.title}</strong>
                  </a>
                ) : (
                  <strong>{n.title}</strong>
                )}
                {n.body && <span style={{ color: 'var(--clinic-muted)' }}>{n.body}</span>}
                <small style={{ color: 'var(--clinic-muted)' }}>{fmtDateTime(n.created_at)}</small>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  )
}
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'

const EMPTY = { full_name: '', email: '', password: '' }

function randomPassword() {
  const alphabet = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  const bytes = crypto.getRandomValues(new Uint8Array(12))
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

export default function Team() {
  const [list, setList] = useState([])
  const [form, setForm] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = () => api('/secretaries').then(setList).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function create(e) {
    e.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const s = await api('/secretaries', { method: 'POST', body: JSON.stringify(form) })
      setNotice(`Compte créé. Communiquez à ${s.full_name} : ${s.email} / ${form.password}`)
      setForm(EMPTY)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(s) {
    if (!window.confirm(`Supprimer le compte de ${s.full_name} ?`)) return
    setError(''); setNotice('')
    try {
      await api(`/secretaries/${s.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="clinic-card" style={{ marginBottom: 24 }}>
      <div className="clinic-card-header"><h2 className="clinic-card-title">Mon équipe</h2></div>
      <div className="clinic-card-body">
        <p style={{ marginTop: 0, color: 'var(--clinic-muted)' }}>
          Le secrétariat gère les demandes, l'agenda et les coordonnées des patients. Il n'a accès ni aux
          dossiers médicaux, ni aux radiographies, ni aux rapports, ni aux ordonnances.
        </p>

        {list.length > 0 && (
          <table className="clinic-table" style={{ marginBottom: 20 }}>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td className="clinic-patient-name">{s.full_name}</td>
                  <td>{s.email ?? '—'}</td>
                  <td><button type="button" className="clinic-btn clinic-btn-ghost" onClick={() => remove(s)}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <form onSubmit={create} className="clinic-form-grid">
          <div className="clinic-field clinic-col-6">
            <label htmlFor="t_name">Nom</label>
            <input id="t_name" className="clinic-input" value={form.full_name} onChange={set('full_name')} required minLength={2} />
          </div>
          <div className="clinic-field clinic-col-6">
            <label htmlFor="t_email">E-mail (identifiant de connexion)</label>
            <input id="t_email" className="clinic-input" type="email" value={form.email} onChange={set('email')} required />
          </div>
          <div className="clinic-field clinic-col-12">
            <label htmlFor="t_pw">Mot de passe initial (10 caractères minimum)</label>
            <div style={{ display: 'flex', gap: 10 }}>
              <input id="t_pw" className="clinic-input" value={form.password} onChange={set('password')}
                required minLength={10} autoComplete="off" />
              <button type="button" className="clinic-btn clinic-btn-ghost"
                onClick={() => setForm({ ...form, password: randomPassword() })}>Générer</button>
            </div>
          </div>
          <div className="clinic-col-12">
            <button className="clinic-btn clinic-btn-primary" disabled={busy}>{busy ? 'Création…' : 'Créer le compte'}</button>
          </div>
        </form>
        {error && <p className="clinic-error">{error}</p>}
        {notice && <p className="clinic-success">{notice}</p>}
      </div>
    </section>
  )
}
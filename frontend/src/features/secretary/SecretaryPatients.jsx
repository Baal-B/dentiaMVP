import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useActingId } from './useActingId'
import { fmtDate } from '../../lib/format'
import { norm } from '../../lib/rx'
import Pager from '../../components/Pager'
import { usePager } from '../../lib/usePager'

const EMPTY = { first_name: '', last_name: '', birth_date: '', sex: '', phone: '', email: '' }

export default function SecretaryPatients() {
  const actingId = useActingId()
  const [list, setList] = useState([])
  const [q, setQ] = useState('')
  const [form, setForm] = useState(EMPTY)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const shown = list.filter((p) => norm(`${p.last_name} ${p.first_name} ${p.phone ?? ''}`).includes(norm(q).trim()))
  const pager = usePager(shown, 10)

  async function load() {
    const { data, error } = await supabase.from('patients_basic')
      .select('id, first_name, last_name, birth_date, sex, phone, email').order('last_name').limit(1000)
    if (error) setError(error.message)
    else setList(data)
    setLoading(false)
  }
  useEffect(() => { load() }, [])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function add(e) {
    e.preventDefault()
    setBusy(true); setError('')
    const { error } = await supabase.from('patients_basic').insert({
      doctor_id: actingId,
      first_name: form.first_name.trim(), last_name: form.last_name.trim(),
      birth_date: form.birth_date || null, sex: form.sex || null,
      phone: form.phone.trim() || null, email: form.email.trim() || null,
    })
    setBusy(false)
    if (error) return setError(error.message)
    setForm(EMPTY); setAdding(false); load()
  }

  return (
    <>
      <h1 className="clinic-page-title">Patients</h1>
      <p className="clinic-page-sub">Coordonnées uniquement. Le dossier médical est réservé au praticien.</p>
      {error && <p className="clinic-error">{error}</p>}

      <section className="clinic-card" style={{ marginBottom: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Nouveau patient</h2>
          <button className="clinic-btn clinic-btn-ghost" onClick={() => setAdding(!adding)}>
            {adding ? 'Fermer' : 'Ajouter'}
          </button>
        </div>
        {adding && (
          <div className="clinic-card-body">
            <form onSubmit={add} className="clinic-form-grid">
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_first">Prénom</label>
                <input id="p_first" className="clinic-input" value={form.first_name} onChange={set('first_name')} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_last">Nom</label>
                <input id="p_last" className="clinic-input" value={form.last_name} onChange={set('last_name')} required />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_birth">Naissance</label>
                <input id="p_birth" className="clinic-input" type="date" value={form.birth_date} onChange={set('birth_date')} />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_sex">Sexe</label>
                <select id="p_sex" className="clinic-input" value={form.sex} onChange={set('sex')}>
                  <option value="">—</option><option value="F">F</option><option value="M">M</option><option value="other">Autre</option>
                </select>
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_phone">Téléphone</label>
                <input id="p_phone" className="clinic-input" value={form.phone} onChange={set('phone')} />
              </div>
              <div className="clinic-field clinic-col-6">
                <label htmlFor="p_email">E-mail</label>
                <input id="p_email" className="clinic-input" type="email" value={form.email} onChange={set('email')} />
              </div>
              <div className="clinic-col-12">
                <button className="clinic-btn clinic-btn-primary" disabled={busy}>{busy ? 'Ajout…' : 'Enregistrer'}</button>
              </div>
            </form>
          </div>
        )}
      </section>

      <section className="clinic-card">
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Liste <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>({shown.length})</span></h2>
          <input className="clinic-input" style={{ maxWidth: 260 }} placeholder="Rechercher…" value={q}
            onChange={(e) => { setQ(e.target.value); pager.setPage(0) }} aria-label="Rechercher un patient" />
        </div>
        {loading ? (
          <div className="clinic-loading">Chargement…</div>
        ) : shown.length === 0 ? (
          <div className="clinic-empty">Aucun patient.</div>
        ) : (
          <>
            <table className="clinic-table">
              <thead><tr><th>Nom</th><th>Naissance</th><th>Téléphone</th><th>E-mail</th></tr></thead>
              <tbody>
                {pager.slice.map((p) => (
                  <tr key={p.id}>
                    <td className="clinic-patient-name">{p.last_name} {p.first_name}</td>
                    <td>{p.birth_date ? fmtDate(p.birth_date) : '—'}</td>
                    <td>{p.phone || '—'}</td>
                    <td>{p.email || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pager pager={pager} />
          </>
        )}
      </section>
    </>
  )
}
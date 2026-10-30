import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import '../../styles/clinic.css'
import { Link } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'


const emptyForm = { first_name: '', last_name: '', birth_date: '', sex: '' }

export default function Patients() {
  const { user, profile, signOut } = useAuth()
  const [patients, setPatients] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [isPatientFormOpen, setIsPatientFormOpen] = useState(false)

  async function load() {
    const { data, error } = await supabase
      .from('patients')
      .select('id, first_name, last_name, birth_date, sex, created_at')
      .order('last_name')
    if (error) setError(error.message)
    else setPatients(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  async function addPatient(e) {
    e.preventDefault()
    setError('')
    const { error } = await supabase.from('patients').insert({
      doctor_id: user.id,
      first_name: form.first_name,
      last_name: form.last_name,
      birth_date: form.birth_date || null,
      sex: form.sex || null,
    })
    if (error) return setError(error.message)
    setForm(emptyForm)
    load()
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const initials = (profile?.full_name || user?.email || '?')
    .split(/\s|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join('')

  return (
    <div className="clinic-app">
     

      <main className="clinic-main">
        <h1 className="clinic-page-title">Patients</h1>
        <p className="clinic-page-sub">Gérez le dossier de vos patients synthétiques.</p>

        <div className="clinic-notice">
          <strong>Données synthétiques uniquement.</strong>
          <span>Ne saisissez jamais de données patients réelles.</span>
        </div>

        <section className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-header">
            <h2 className="clinic-card-title clinic-card-title--collapsible">
              <button
                type="button"
                className="clinic-collapse-trigger"
                aria-expanded={isPatientFormOpen}
                aria-controls="new-patient-form-panel"
                onClick={() => setIsPatientFormOpen((isOpen) => !isOpen)}
              >
                Nouveau patient
                <ChevronDown className="clinic-collapse-icon" size={20} aria-hidden="true" />
              </button>
            </h2>
          </div>
          <div id="new-patient-form-panel" className="clinic-card-body" hidden={!isPatientFormOpen}>
            <form onSubmit={addPatient} className="clinic-form-grid clinic-form-grid--spacious">
              <div className="clinic-field clinic-col-3">
                <label htmlFor="first_name">Prénom</label>
                <input
                  id="first_name"
                  className="clinic-input"
                  placeholder="Camille"
                  value={form.first_name}
                  onChange={set('first_name')}
                  required
                />
              </div>

              <div className="clinic-field clinic-col-3">
                <label htmlFor="last_name">Nom</label>
                <input
                  id="last_name"
                  className="clinic-input"
                  placeholder="Durand"
                  value={form.last_name}
                  onChange={set('last_name')}
                  required
                />
              </div>

              <div className="clinic-field clinic-col-2">
                <label htmlFor="birth_date">Naissance</label>
                <input
                  id="birth_date"
                  className="clinic-input"
                  type="date"
                  value={form.birth_date}
                  onChange={set('birth_date')}
                />
              </div>

              <div className="clinic-field clinic-col-2">
                <label htmlFor="sex">Sexe</label>
                <select
                  id="sex"
                  className="clinic-input"
                  value={form.sex}
                  onChange={set('sex')}
                >
                  <option value="">—</option>
                  <option value="F">F</option>
                  <option value="M">M</option>
                  <option value="other">Autre</option>
                </select>
              </div>

              <div className="clinic-col-2 clinic-form-submit">
                <button type="submit" className="clinic-btn clinic-btn-primary clinic-btn-block">
                  Ajouter
                </button>
              </div>
            </form>

            {error && <p className="clinic-error">{error}</p>}
          </div>
        </section>

        <section className="clinic-card">
          <div className="clinic-card-header">
            <h2 className="clinic-card-title">
              Liste des patients
              {!loading && patients.length > 0 && (
                <span style={{ color: 'var(--clinic-muted)', fontWeight: 400, marginLeft: 8 }}>
                  ({patients.length})
                </span>
              )}
            </h2>
          </div>

          {loading ? (
            <div className="clinic-loading">Chargement…</div>
          ) : patients.length === 0 ? (
            <div className="clinic-empty">
              Aucun patient pour le moment. Ajoutez le premier ci-dessus.
            </div>
          ) : (
            <table className="clinic-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Naissance</th>
                  <th>Sexe</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((p) => (
                  <tr key={p.id}>
                   <td className="clinic-patient-name">
  <Link to={`/patients/${p.id}`} className="clinic-link-name">
    {p.last_name} <span style={{ color: 'var(--clinic-muted)', fontWeight: 400 }}>{p.first_name}</span>
  </Link>
</td>
                    <td>{p.birth_date ?? '—'}</td>
                    <td>{p.sex ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </div>
  )
}
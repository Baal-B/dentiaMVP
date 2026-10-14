import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import '../../styles/clinic.css'

export default function Login() {
  const { session, signIn } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to="/" replace />

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const { error } = await signIn(email, password)
    setBusy(false)
    if (error) setError(error.message)
    else navigate('/')
  }

  return (
    <div className="clinic-auth-shell">
      <form onSubmit={handleSubmit} className="clinic-auth-card">
        <div className="clinic-brand">
          <div className="clinic-brand-mark">D</div>
          <div>
            <div className="clinic-brand-name">DentIA</div>
          </div>
        </div>

        <h1>Connexion</h1>
        <p className="clinic-subtitle">Accédez à votre espace praticien.</p>

        <div className="clinic-field">
          <label htmlFor="email">Adresse e-mail</label>
          <input
            id="email"
            className="clinic-input"
            type="email"
            autoComplete="email"
            placeholder="vous@cabinet.fr"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="clinic-field">
          <label htmlFor="password">Mot de passe</label>
          <input
            id="password"
            className="clinic-input"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button
          type="submit"
          className="clinic-btn clinic-btn-primary clinic-btn-block"
          disabled={busy}
          style={{ marginTop: 8 }}
        >
          {busy ? 'Connexion…' : 'Se connecter'}
        </button>

        {error && <p className="clinic-error">{error}</p>}
      </form>
    </div>
  )
}
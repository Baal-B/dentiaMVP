import { useEffect, useState } from 'react'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../auth/AuthProvider'
import { TOPICS } from '../../lib/topics'

const EMPTY = {
  full_name: '', name_ar: '',
  title_fr: 'Médecin dentiste', title_ar: 'طبيب أسنان',
  extra_fr: '', extra_ar: '',
  practice_address: '', practice_address_ar: '',
  practice_name: '', license_number: '', practice_phone: '', practice_email: '',
}
const KEYS = Object.keys(EMPTY)

// defined outside Settings so the inputs keep focus while typing
function Pair({ k, ka, labelFr, labelAr, pro, set, multiline, phFr, phAr }) {
  const Tag = multiline ? 'textarea' : 'input'
  return (
    <>
      <div className="clinic-field clinic-col-6">
        <label htmlFor={k}>{labelFr}</label>
        <Tag id={k} className="clinic-input" value={pro[k]} placeholder={phFr}
          onChange={(e) => set(k, e.target.value)} />
      </div>
      <div className="clinic-field clinic-col-6">
        <label htmlFor={ka} dir="rtl" lang="ar" style={{ display: 'block', textAlign: 'right' }}>{labelAr}</label>
        <Tag id={ka} className="clinic-input" dir="rtl" lang="ar" value={pro[ka]} placeholder={phAr}
          onChange={(e) => set(ka, e.target.value)} />
      </div>
    </>
  )
}

export default function Settings() {
  const { user } = useAuth()
  const [pro, setPro] = useState(EMPTY)
  const [interests, setInterests] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    supabase.from('profiles')
      .select(`interests, ${KEYS.join(', ')}`)
      .eq('id', user.id).single()
      .then(({ data, error }) => {
        if (error) setError(error.message)
        else {
          setInterests(data.interests ?? [])
          setPro(Object.fromEntries(KEYS.map((k) => [k, data[k] ?? EMPTY[k]])))
        }
        setLoading(false)
      })
  }, [user.id])

  const set = (k, v) => { setSaved(false); setPro((p) => ({ ...p, [k]: v })) }

  const toggle = (key) => {
    setSaved(false)
    setInterests((list) => (list.includes(key) ? list.filter((k) => k !== key) : [...list, key]))
  }

  async function save(e) {
    e.preventDefault()
    setSaving(true); setError(''); setSaved(false)
    const { error } = await supabase
      .from('profiles').update({ ...pro, full_name: pro.full_name.trim(), interests }).eq('id', user.id)
    setSaving(false)
    if (error) return setError(error.message)
    setSaved(true)
  }

  if (loading) return <div className="clinic-loading">Chargement…</div>

  return (
    <>
      <h1 className="clinic-page-title">Paramètres</h1>
      <p className="clinic-page-sub">Votre profil, l'en-tête de vos ordonnances et vos alertes de veille scientifique.</p>

      <form onSubmit={save}>
        <section className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Profil et en-tête des ordonnances</h2></div>
          <div className="clinic-card-body">
            <p style={{ marginTop: 0, color: 'var(--clinic-muted)' }}>
              Le français s'affiche à gauche de l'ordonnance, l'arabe à droite. Les champs vides ne sont pas imprimés.
            </p>
            <div className="clinic-form-grid">
              <Pair pro={pro} set={set} k="full_name" ka="name_ar"
                labelFr="Nom affiché et nom sur l'ordonnance (français)" labelAr="الاسم"
                phFr="Dr Prénom Nom" phAr="الدكتور …" />
              <Pair pro={pro} set={set} k="title_fr" ka="title_ar"
                labelFr="Titre (français)" labelAr="اللقب" />
              <Pair pro={pro} set={set} k="extra_fr" ka="extra_ar"
                labelFr="Ligne complémentaire (diplôme, spécialités…)" labelAr="سطر إضافي (شهادة، اختصاصات…)"
                phFr="Diplômé de la Faculté de Médecine Dentaire de Monastir"
                phAr="متخرج من كلية طب الأسنان بالمنستير" multiline />
              <Pair pro={pro} set={set} k="practice_address" ka="practice_address_ar"
                labelFr="Adresse du cabinet (français)" labelAr="عنوان العيادة" multiline />

              {[
                ['license_number', "Numéro d'ordre / identifiant professionnel"],
                ['practice_name', 'Nom du cabinet (facultatif)'],
                ['practice_phone', 'Téléphone du cabinet'],
                ['practice_email', 'E-mail du cabinet (facultatif)'],
              ].map(([k, label]) => (
                <div className="clinic-field clinic-col-6" key={k}>
                  <label htmlFor={k}>{label}</label>
                  <input id={k} className="clinic-input" value={pro[k]} onChange={(e) => set(k, e.target.value)} />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="clinic-card" style={{ marginBottom: 24 }}>
          <div className="clinic-card-header"><h2 className="clinic-card-title">Centres d'intérêt</h2></div>
          <div className="clinic-card-body">
            <p style={{ marginTop: 0, color: 'var(--clinic-muted)' }}>
              Vous serez notifié des nouveaux articles sur ces sujets.
            </p>
            <div className="clinic-topic-grid">
              {TOPICS.map((t) => (
                <label key={t.key} className={'clinic-topic' + (interests.includes(t.key) ? ' on' : '')}>
                  <input type="checkbox" checked={interests.includes(t.key)} onChange={() => toggle(t.key)} />
                  {t.label}
                </label>
              ))}
            </div>
          </div>
        </section>

        <button className="clinic-btn clinic-btn-primary" disabled={saving}>
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </button>
        {saved && <span className="clinic-success" style={{ marginLeft: 12, display: 'inline-block' }}>Enregistré.</span>}
        {error && <p className="clinic-error">{error}</p>}
      </form>
    </>
  )
}
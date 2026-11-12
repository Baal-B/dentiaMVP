export default function TopKSelect({ value, onChange }) {
  return (
    <div className="clinic-field" style={{ maxWidth: 340, marginBottom: 0 }}>
      <label htmlFor="topk">Nombre de sources à consulter</label>
      <select id="topk" className="clinic-input" value={value} onChange={(e) => onChange(Number(e.target.value))}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
          <option key={n} value={n}>{n}{n === 3 ? ' (par défaut)' : ''}</option>
        ))}
      </select>
      <small style={{ color: 'var(--clinic-muted)' }}>
        Plus de sources donne plus de contexte, mais un petit modèle local peut s'y perdre.
      </small>
    </div>
  )
}
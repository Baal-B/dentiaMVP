export const fmtDateTime = (iso) =>
  new Date(iso).toLocaleString('fr-FR', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit',
  })

export const fmtDate = (iso) =>
  new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })

export const fullName = (p) => (p ? `${p.last_name} ${p.first_name}` : '—')
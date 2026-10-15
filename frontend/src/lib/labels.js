export const KINDS = {
  panoramic: 'Panoramique',
  periapical: 'Rétro-alvéolaire',
  bitewing: 'Bite-wing',
}

export function statusLabel(a) {
  if (!a) return { text: 'Pas encore analysée', cls: '' }
  if (a.status === 'pending') return { text: 'Analyse en cours', cls: '' }
  if (a.status === 'failed') return { text: 'Échec', cls: 'danger' }
  if (a.validation_status === 'validated') return { text: 'Validée', cls: 'ok' }
  if (a.validation_status === 'rejected') return { text: 'Rejetée', cls: 'danger' }
  return { text: 'À valider', cls: 'info' }
}

export const APPT_STATUS = {
  scheduled: { text: 'Prévu', cls: 'info' },
  completed: { text: 'Terminé', cls: 'ok' },
  cancelled: { text: 'Annulé', cls: '' },
  no_show: { text: 'Absent', cls: 'danger' },
}

export const REPORT_STATUS = {
  draft: { text: 'Brouillon', cls: 'info' },
  signed: { text: 'Signé', cls: 'ok' },
}
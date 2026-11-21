// a scheduled appointment whose end time has passed is shown as "À clôturer"
export const isPast = (a) => new Date(a.ends_at) < new Date()

export function displayStatus(a, table) {
  if (a.status === 'scheduled' && isPast(a)) return { text: 'À clôturer', cls: '' }
  return table[a.status]
}
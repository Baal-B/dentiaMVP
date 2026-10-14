const LABELS_FR = {
  Caries: 'Carie',
  'Deep Caries': 'Carie profonde',
  Impacted: 'Dent incluse',
  'Periapical Lesion': 'Lésion péri-apicale',
}

export const labelFr = (l) => LABELS_FR[l] ?? l
export const pct = (c) => `${Math.round(c * 100)} %`
export const REPORT_DISCLAIMER =
  "Document d'aide à la décision établi sous la responsabilité du praticien. " +
  "Les résultats de l'IA sont des suggestions qui doivent être confirmées par un chirurgien-dentiste."

const key = (c) => c.doi || c.url || c.title

// Builds the draft from persisted data (the validated copy), never from UI state.
export function buildReport({ radiograph, analysis, queries }) {
  const validated = analysis.validated_findings ?? []
  const accepted = validated
    .filter((f) => f.decision === 'accepted')
    .map(({ id, label, confidence, depth, tooth_fdi }) => ({ id, label, confidence, depth, tooth_fdi }))

  // one copy of each source, renumbered 1..n (the report must not depend on the RAG index)
  const seen = new Set()
  const citations = []
  for (const q of queries) {
    for (const c of q.citations ?? []) {
      if (seen.has(key(c))) continue
      seen.add(key(c))
      citations.push({ ...c, n: citations.length + 1 })
    }
  }

  return {
    content: {
      meta: {
        generated_at: new Date().toISOString(),
        mock_vision: !!analysis.model_info?.mock,
        mock_sources: citations.some((c) => c.title?.startsWith('[MOCK]')),
        vision_model: analysis.model_info?.vision ?? null,
      },
      motif: radiograph.symptoms ?? '',
      radiograph: { id: radiograph.id, kind: radiograph.kind, taken_at: radiograph.taken_at },
      findings: accepted,
      rejected_count: validated.length - accepted.length,
      observations: '',
      differential: '',
      plan: '',
    },
    citations,
  }
}
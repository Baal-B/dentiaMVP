export default function AssistantPanel({ queries }) {
  if (!queries?.length) return null

  return queries.map((q) => {
    const citations = q.citations ?? []
    const isMock = citations.some((c) => c.title?.startsWith('[MOCK]'))
    return (
      <section className="clinic-card" key={q.id} style={{ marginTop: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Sources de la littérature</h2>
        </div>
        <div className="clinic-card-body">
          <p style={{ marginTop: 0 }}>
            <strong>Recherche :</strong> <span style={{ color: 'var(--clinic-muted)' }}>{q.question}</span>
          </p>

          {isMock && (
            <div className="clinic-notice">
              <strong>Données fictives.</strong>
              <span>La base de connaissances est un simulateur : ces extraits ne sont pas de vraies publications.</span>
            </div>
          )}

          {q.insufficient_evidence || citations.length === 0 ? (
            <p style={{ marginBottom: 0 }}>
              Pas assez de preuves dans la base de connaissances pour répondre à cette question.
            </p>
          ) : (
            <ol className="clinic-sources">
              {citations.map((c) => (
                <li key={c.n}>
                  <div>
                    <strong>[{c.n}]</strong> {c.title}
                    <span style={{ color: 'var(--clinic-muted)' }}> — {c.journal}, {c.year}</span>
                    {c.url && (
                      <>
                        {' '}
                        <a href={c.url} target="_blank" rel="noopener noreferrer">lien</a>
                      </>
                    )}
                  </div>
                  <blockquote>{c.passage}</blockquote>
                </li>
              ))}
            </ol>
          )}
          <p style={{ color: 'var(--clinic-muted)', fontSize: 14, marginBottom: 0 }}>
            Extraits bruts des sources. Aucune réponse n'est générée : c'est au praticien de conclure.
          </p>
        </div>
      </section>
    )
  })
}
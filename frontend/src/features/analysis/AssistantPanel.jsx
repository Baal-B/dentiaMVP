export default function AssistantPanel({ queries }) {
  if (!queries?.length) return null

  return queries.map((q) => {
    const citations = q.citations ?? []
    const isMock = citations.some((c) => c.title?.startsWith('[MOCK]'))
    const generated = !!q.llm_model && !!q.answer
    const none = q.insufficient_evidence || citations.length === 0

    return (
      <section className="clinic-card" key={q.id} style={{ marginTop: 24 }}>
        <div className="clinic-card-header">
          <h2 className="clinic-card-title">Assistant : sources de la littérature</h2>
        </div>
        <div className="clinic-card-body">
          <p style={{ marginTop: 0 }}>
            <strong>Question :</strong> <span style={{ color: 'var(--clinic-muted)' }}>{q.question}</span>
          </p>

          {isMock && (
            <div className="clinic-notice">
              <strong>Données fictives.</strong>
              <span>La base de connaissances est un simulateur : ces extraits ne sont pas de vraies publications.</span>
            </div>
          )}

          {none ? (
            <p style={{ marginBottom: 0 }}>
              Pas assez de preuves dans la base de connaissances pour répondre à cette question.
            </p>
          ) : (
            <>
              {generated && (
                <div className="clinic-ai-answer">
                  <span className="clinic-pill info">Généré par IA</span>
                  <p className="report-text">{q.answer}</p>
                  <small style={{ color: 'var(--clinic-muted)' }}>
                    Résumé automatique des sources ci-dessous ({q.llm_model}). Il peut contenir des erreurs :
                    vérifiez chaque affirmation dans la source.
                  </small>
                </div>
              )}

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

              <p style={{ color: 'var(--clinic-muted)', fontSize: 14, marginBottom: 0 }}>
                {generated
                  ? "Extraits en anglais, langue des publications. L'aide à la décision ne remplace pas le jugement du praticien."
                  : "Extraits bruts des sources (en anglais, langue des publications). Aucune réponse n'a été générée."}
              </p>
            </>
          )}
        </div>
      </section>
    )
  })
}
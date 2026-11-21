-- DentIA : schéma de base pour le workflow n8n "Rappels de rendez-vous"
-- Ce script s'exécute automatiquement au tout premier démarrage du conteneur PostgreSQL.

CREATE TABLE IF NOT EXISTS patients (
    id          SERIAL PRIMARY KEY,
    prenom      VARCHAR(100) NOT NULL,
    nom         VARCHAR(100) NOT NULL,
    email       VARCHAR(150),
    telephone   VARCHAR(20),          -- format international, ex : +21612345678
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rendez_vous (
    id                          SERIAL PRIMARY KEY,
    patient_id                  INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    date_rdv                    TIMESTAMP NOT NULL,
    statut                      VARCHAR(20) NOT NULL DEFAULT 'confirme'
                                CHECK (statut IN ('confirme', 'annule', 'termine')),
    rappel_email_envoye_at      TIMESTAMP,   -- NULL = rappel pas encore envoyé
    rappel_whatsapp_envoye_at   TIMESTAMP,   -- NULL = rappel pas encore envoyé
    created_at                  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rdv_date_statut ON rendez_vous (date_rdv, statut);

-- Données de test (dates relatives à aujourd'hui, donc toujours utilisables)
-- Pense à remplacer le numéro +21600000000 par le tien pour tester WhatsApp.
INSERT INTO patients (prenom, nom, email, telephone) VALUES
    ('Mariem',  'Test',   'mariemtoumi44@gmail.com', '+21600000000'),
    ('Patient', 'Deux',   'mariemtoumi44@gmail.com', '+21600000000'),
    ('Patient', 'Annule', 'mariemtoumi44@gmail.com', '+21600000000'),
    ('Patient', 'Plus',   'mariemtoumi44@gmail.com', '+21600000000');

INSERT INTO rendez_vous (patient_id, date_rdv, statut) VALUES
    (1, CURRENT_DATE + INTERVAL '1 day 10 hours', 'confirme'),  -- demain : doit recevoir un rappel
    (2, CURRENT_DATE + INTERVAL '1 day 15 hours', 'confirme'),  -- demain : doit recevoir un rappel
    (3, CURRENT_DATE + INTERVAL '1 day 11 hours', 'annule'),    -- demain mais annulé : à ignorer
    (4, CURRENT_DATE + INTERVAL '3 days 9 hours', 'confirme');  -- dans 3 jours : à ignorer
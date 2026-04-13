CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    published_at TEXT,
    ingested_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    actor TEXT,
    target TEXT,
    predicate TEXT NOT NULL,
    polarity TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    claim_date TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS statements (
    statement_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    speaker TEXT,
    audience TEXT,
    tone REAL NOT NULL,
    text TEXT NOT NULL,
    statement_date TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    actor_a TEXT,
    actor_b TEXT,
    event_type TEXT NOT NULL,
    event_date TEXT,
    intensity REAL NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id)
);

CREATE TABLE IF NOT EXISTS legal_signals (
    signal_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    provision_id TEXT NOT NULL,
    modality TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    actor TEXT,
    strength REAL NOT NULL,
    condition_json TEXT NOT NULL,
    override_json TEXT NOT NULL,
    source_text TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type ON documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_claims_document ON claims(document_id);
CREATE INDEX IF NOT EXISTS idx_claims_actor_target ON claims(actor, target);
CREATE INDEX IF NOT EXISTS idx_events_actor_pair ON events(actor_a, actor_b);
CREATE INDEX IF NOT EXISTS idx_legal_signals_document ON legal_signals(document_id);


CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS event_index (
 event_id text PRIMARY KEY,
 descriptor jsonb NOT NULL,
 searchable text NOT NULL,
 indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS event_index_search ON event_index USING gin (to_tsvector('simple', searchable));
CREATE TABLE IF NOT EXISTS operation_journal (
 operation_id uuid PRIMARY KEY,
 user_id text NOT NULL,
 signer text NOT NULL,
 contract text NOT NULL,
 method text NOT NULL,
 args jsonb NOT NULL,
 payload_digest text NOT NULL,
 nonce bigint NOT NULL,
 transaction_hash text UNIQUE,
 status text NOT NULL DEFAULT 'pending',
 acknowledged boolean NOT NULL DEFAULT false,
 attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
 error text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS operation_journal_user ON operation_journal(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS operation_journal_recovery ON operation_journal(status, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS operation_journal_nonce ON operation_journal(signer, nonce);
CREATE TABLE IF NOT EXISTS challenge_journal (
 challenge_id uuid PRIMARY KEY,
 user_id text NOT NULL,
 relation_id text NOT NULL,
 successor_id text NOT NULL,
 reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS index_cursor (
 name text PRIMARY KEY,
 offset_value integer NOT NULL DEFAULT 0,
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO schema_migrations(version) VALUES (1) ON CONFLICT DO NOTHING;

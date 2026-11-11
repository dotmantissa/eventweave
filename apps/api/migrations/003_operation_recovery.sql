DROP INDEX IF EXISTS operation_journal_nonce;
ALTER TABLE operation_journal ADD COLUMN IF NOT EXISTS last_reconciled_at timestamptz;
ALTER TABLE operation_journal ADD COLUMN IF NOT EXISTS next_reconcile_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE operation_journal ADD COLUMN IF NOT EXISTS reconcile_attempts integer NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS operation_journal_fair_recovery ON operation_journal(next_reconcile_at,last_reconciled_at) WHERE acknowledged=false;
INSERT INTO schema_migrations(version) VALUES (3) ON CONFLICT DO NOTHING;

ALTER TABLE operation_journal ADD COLUMN IF NOT EXISTS contract_address text NOT NULL DEFAULT '';
ALTER TABLE operation_journal ADD COLUMN IF NOT EXISTS directory_address text NOT NULL DEFAULT '';
INSERT INTO schema_migrations(version) VALUES (2) ON CONFLICT DO NOTHING;

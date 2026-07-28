CREATE TABLE IF NOT EXISTS cfe_requests (
 id SERIAL PRIMARY KEY, request_key VARCHAR(150) UNIQUE NOT NULL,
 service_number VARCHAR(40) NOT NULL, requester_wa_id VARCHAR(100) NOT NULL,
 requester_name VARCHAR(160), client_group_jid VARCHAR(160) NOT NULL,
 client_instance VARCHAR(100) NOT NULL, client_message_id VARCHAR(180) UNIQUE NOT NULL,
 provider_group_jid VARCHAR(160) NOT NULL, provider_instance VARCHAR(100) NOT NULL,
 provider_message_id VARCHAR(180), provider_response_message_id VARCHAR(180) UNIQUE,
 provider_pdf_filename VARCHAR(255), status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
 error_message TEXT, delivery_claimed BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_cfe_service_number ON cfe_requests(service_number);
CREATE INDEX IF NOT EXISTS ix_cfe_provider_message_id ON cfe_requests(provider_message_id);
CREATE INDEX IF NOT EXISTS ix_cfe_status ON cfe_requests(status);

CREATE TABLE IF NOT EXISTS renapo_requests (
 id SERIAL PRIMARY KEY, request_key VARCHAR(150) UNIQUE NOT NULL,
 curp VARCHAR(18) NOT NULL, requester_wa_id VARCHAR(100) NOT NULL,
 client_group_jid VARCHAR(160) NOT NULL, client_instance VARCHAR(100) NOT NULL,
 client_message_id VARCHAR(180) UNIQUE NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'DISABLED',
 error_message TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_renapo_curp ON renapo_requests(curp);

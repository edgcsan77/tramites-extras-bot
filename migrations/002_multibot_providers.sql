BEGIN;

CREATE TABLE IF NOT EXISTS bot_controls (
 id SERIAL PRIMARY KEY,
 instance_name VARCHAR(120) UNIQUE NOT NULL,
 display_name VARCHAR(180) NOT NULL,
 panel_token VARCHAR(100) UNIQUE NOT NULL,
 limit_total INTEGER NOT NULL DEFAULT 0 CHECK (limit_total >= 0),
 used_total INTEGER NOT NULL DEFAULT 0 CHECK (used_total >= 0),
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
 is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_bot_controls_instance_name ON bot_controls(instance_name);
CREATE INDEX IF NOT EXISTS ix_bot_controls_panel_token ON bot_controls(panel_token);

CREATE TABLE IF NOT EXISTS authorized_groups (
 id SERIAL PRIMARY KEY,
 group_jid VARCHAR(160) UNIQUE NOT NULL,
 owner_instance VARCHAR(120) NOT NULL,
 custom_name VARCHAR(200),
 is_blocked BOOLEAN NOT NULL DEFAULT FALSE,
 is_hidden BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_authorized_groups_owner ON authorized_groups(owner_instance);

CREATE TABLE IF NOT EXISTS provider_settings (
 id SERIAL PRIMARY KEY,
 provider_name VARCHAR(120) UNIQUE NOT NULL,
 display_name VARCHAR(180) NOT NULL,
 module VARCHAR(30) NOT NULL DEFAULT 'CFE',
 provider_type VARCHAR(40) NOT NULL DEFAULT 'WHATSAPP_GROUP',
 group_jid VARCHAR(160) UNIQUE,
 priority INTEGER NOT NULL DEFAULT 100,
 is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
 no_record_phrases TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_provider_settings_module_enabled ON provider_settings(module,is_enabled,priority);

CREATE TABLE IF NOT EXISTS bot_recharge_logs (
 id SERIAL PRIMARY KEY,
 instance_name VARCHAR(120) NOT NULL,
 amount INTEGER NOT NULL,
 previous_limit INTEGER NOT NULL,
 new_limit INTEGER NOT NULL,
 used_at_recharge INTEGER NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_bot_recharge_logs_instance ON bot_recharge_logs(instance_name);

ALTER TABLE cfe_requests ADD COLUMN IF NOT EXISTS provider_name VARCHAR(120);
ALTER TABLE cfe_requests ADD COLUMN IF NOT EXISTS usage_counted BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_cfe_provider_name ON cfe_requests(provider_name);

COMMIT;

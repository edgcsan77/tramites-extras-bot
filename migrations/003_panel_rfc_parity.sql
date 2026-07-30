BEGIN;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS cfe_limit
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS cfe_used
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS renapo_limit
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS renapo_used
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS sale_price_cfe
VARCHAR(30);

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS sale_price_renapo
VARCHAR(30);

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS private_notify_jid
VARCHAR(160);

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS is_hidden
BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE bot_controls
ADD COLUMN IF NOT EXISTS updated_at
TIMESTAMPTZ NOT NULL DEFAULT NOW();


ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS category
VARCHAR(80);

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS price_cfe
VARCHAR(30);

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS price_renapo
VARCHAR(30);

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS cfe_limit
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS cfe_used
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS renapo_limit
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS renapo_used
INTEGER NOT NULL DEFAULT 0;

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS hidden_in_main
BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE authorized_groups
ADD COLUMN IF NOT EXISTS updated_at
TIMESTAMPTZ NOT NULL DEFAULT NOW();


CREATE TABLE IF NOT EXISTS product_recharge_logs (
    id SERIAL PRIMARY KEY,
    owner_type VARCHAR(20) NOT NULL,
    owner_key VARCHAR(160) NOT NULL,
    product VARCHAR(30) NOT NULL,
    amount INTEGER NOT NULL,
    previous_limit INTEGER NOT NULL,
    new_limit INTEGER NOT NULL,
    used_at_recharge INTEGER NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS
ix_product_recharge_logs_owner_key
ON product_recharge_logs(owner_key);

CREATE INDEX IF NOT EXISTS
ix_product_recharge_logs_product
ON product_recharge_logs(product);

CREATE INDEX IF NOT EXISTS
ix_product_recharge_logs_created_at
ON product_recharge_logs(created_at);

COMMIT;

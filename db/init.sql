-- Enable pgcrypto for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) UNIQUE NOT NULL,
    username            VARCHAR(100) UNIQUE NOT NULL,
    hashed_password     VARCHAR(255) NOT NULL,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    is_admin            BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

-- Labs table
CREATE TABLE IF NOT EXISTS labs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                VARCHAR(100) UNIQUE NOT NULL,
    title               VARCHAR(255) NOT NULL,
    description         TEXT        NOT NULL,
    category            VARCHAR(50) NOT NULL,
    difficulty          VARCHAR(20) NOT NULL,
    estimated_minutes   INT         NOT NULL DEFAULT 30,
    objectives          JSONB,
    theory_content      TEXT,
    instructions        JSONB,
    initial_topology    JSONB,
    verification_rules  JSONB,
    prerequisites       JSONB,
    sort_order          INT         NOT NULL DEFAULT 0,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ
);

-- Topologies table
CREATE TABLE IF NOT EXISTS topologies (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    lab_id          UUID        NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    is_template     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    topology_id     UUID        NOT NULL REFERENCES topologies(id) ON DELETE CASCADE,
    device_type     VARCHAR(50) NOT NULL,
    label           VARCHAR(100) NOT NULL,
    x               FLOAT       NOT NULL DEFAULT 0,
    y               FLOAT       NOT NULL DEFAULT 0,
    configuration   JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ
);

-- Connections table
CREATE TABLE IF NOT EXISTS connections (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    topology_id         UUID        NOT NULL REFERENCES topologies(id) ON DELETE CASCADE,
    source_device_id    UUID        NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    target_device_id    UUID        NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    source_interface    VARCHAR(50) NOT NULL DEFAULT 'eth0',
    target_interface    VARCHAR(50) NOT NULL DEFAULT 'eth0',
    link_type           VARCHAR(20) NOT NULL DEFAULT 'ethernet',
    bandwidth_mbps      INT         DEFAULT 1000,
    configuration       JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Simulations table
CREATE TABLE IF NOT EXISTS simulations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    topology_id     UUID        NOT NULL REFERENCES topologies(id) ON DELETE CASCADE,
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    lab_id          UUID        NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    configuration   JSONB,
    results         JSONB,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Progress table
CREATE TABLE IF NOT EXISTS progress (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lab_id              UUID        NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    status              VARCHAR(20) NOT NULL DEFAULT 'not_started',
    score               INT,
    attempts            INT         NOT NULL DEFAULT 0,
    last_simulation_id  UUID        REFERENCES simulations(id),
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ,
    CONSTRAINT uq_progress_user_lab UNIQUE (user_id, lab_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_topologies_user_lab   ON topologies (user_id, lab_id);
CREATE INDEX IF NOT EXISTS idx_devices_topology      ON devices     (topology_id);
CREATE INDEX IF NOT EXISTS idx_connections_topology  ON connections (topology_id);
CREATE INDEX IF NOT EXISTS idx_simulations_user      ON simulations (user_id);
CREATE INDEX IF NOT EXISTS idx_simulations_lab       ON simulations (lab_id);
CREATE INDEX IF NOT EXISTS idx_progress_user         ON progress    (user_id);
CREATE INDEX IF NOT EXISTS idx_progress_lab          ON progress    (lab_id);

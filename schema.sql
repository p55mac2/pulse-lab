-- Pulse Check schema. Applied automatically at app startup (idempotent).

CREATE TABLE IF NOT EXISTS players (
    id          SERIAL PRIMARY KEY,
    handle      TEXT NOT NULL UNIQUE,
    team        TEXT,
    region      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attempts (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    target_seconds  NUMERIC(4, 2) NOT NULL,
    delta_seconds   NUMERIC(6, 3) NOT NULL,
    score           INTEGER NOT NULL,
    played_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

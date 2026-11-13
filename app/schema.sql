PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name        TEXT NOT NULL,
    email            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash    TEXT NOT NULL,
    role             TEXT NOT NULL CHECK (role IN ('student', 'admin')),
    current_standard INTEGER CHECK (current_standard IS NULL OR current_standard BETWEEN 1 AND 10),
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS examinations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL,
    conducting_body    TEXT,
    description        TEXT,
    category           TEXT NOT NULL DEFAULT 'Other'
        CHECK (category IN ('Olympiad', 'Scholarship', 'Talent Search', 'Aptitude', 'Other')),
    board              TEXT NOT NULL DEFAULT 'All'
        CHECK (board IN ('All', 'CBSE', 'ICSE', 'State Board')),
    medium             TEXT NOT NULL DEFAULT 'All'
        CHECK (medium IN ('All', 'English', 'Marathi', 'Hindi', 'Other')),
    exam_date          TEXT,
    registration_start TEXT,
    registration_end   TEXT,
    fee_info           TEXT,
    official_url       TEXT,
    link_last_checked  TEXT,
    is_sample          INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0, 1)),
    is_published       INTEGER NOT NULL DEFAULT 1 CHECK (is_published IN (0, 1)),
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS eligibility_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id      INTEGER NOT NULL REFERENCES examinations(id) ON DELETE CASCADE,
    min_standard INTEGER CHECK (min_standard IS NULL OR min_standard BETWEEN 1 AND 10),
    max_standard INTEGER CHECK (max_standard IS NULL OR max_standard BETWEEN 1 AND 10),
    criteria_text TEXT,
    source_note  TEXT,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (min_standard IS NULL OR max_standard IS NULL OR min_standard <= max_standard)
);

CREATE TABLE IF NOT EXISTS notes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id           INTEGER REFERENCES examinations(id) ON DELETE SET NULL,
    subject           TEXT NOT NULL,
    topic             TEXT,
    title             TEXT NOT NULL,
    description       TEXT,
    is_free           INTEGER NOT NULL CHECK (is_free IN (0, 1)),
    price_paise       INTEGER NOT NULL DEFAULT 0,
    file_path         TEXT,
    original_filename TEXT,
    is_sample         INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0, 1)),
    is_published      INTEGER NOT NULL DEFAULT 1 CHECK (is_published IN (0, 1)),
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((is_free = 1 AND price_paise = 0) OR (is_free = 0 AND price_paise > 0))
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    note_id           INTEGER NOT NULL REFERENCES notes(id) ON DELETE RESTRICT,
    amount_paise      INTEGER NOT NULL CHECK (amount_paise > 0),
    currency          TEXT NOT NULL DEFAULT 'INR',
    status            TEXT NOT NULL DEFAULT 'created'
        CHECK (status IN ('created', 'pending', 'paid', 'failed', 'cancelled')),
    provider          TEXT NOT NULL,
    provider_order_id TEXT UNIQUE,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    paid_at           TEXT
);

-- A student can hold at most one *paid* order per note.
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_one_paid
    ON orders(user_id, note_id) WHERE status = 'paid';

CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    provider_payment_id TEXT UNIQUE,      -- set only when the provider data was authentic
    signature_verified  INTEGER NOT NULL DEFAULT 0 CHECK (signature_verified IN (0, 1)),
    provider_status     TEXT,
    amount_paise        INTEGER,
    raw_payload         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookmarks (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_id    INTEGER NOT NULL REFERENCES examinations(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, exam_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    entity     TEXT NOT NULL,
    entity_id  INTEGER,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_rules_exam    ON eligibility_rules(exam_id);
CREATE INDEX IF NOT EXISTS ix_notes_exam    ON notes(exam_id);
CREATE INDEX IF NOT EXISTS ix_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS ix_orders_note   ON orders(note_id);
CREATE INDEX IF NOT EXISTS ix_payments_order ON payments(order_id);

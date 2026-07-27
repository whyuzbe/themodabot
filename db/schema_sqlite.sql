-- ════════════════════════════════════════════════════════════════
--  Schema: TheModa shop bot (SQLite version)
--  Идентична по структуре schema_postgres.sql, но с SQLite-типами.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id           INTEGER UNIQUE NOT NULL,
    username        TEXT,
    phone           TEXT,
    gender          TEXT,
    language        TEXT DEFAULT 'ru',
    is_blocked      INTEGER DEFAULT 0,
    last_address    TEXT,
    language_auto   INTEGER DEFAULT 0,
    registered_at   TEXT DEFAULT (datetime('now'))
);

-- Сохранённые размеры клиента, отдельно по категории (обувь/одежда/...)
CREATE TABLE IF NOT EXISTS user_sizes (
    user_tg_id      INTEGER NOT NULL,
    category        TEXT NOT NULL,
    size            TEXT NOT NULL,
    updated_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_tg_id, category)
);

CREATE TABLE IF NOT EXISTS staff_accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    role            TEXT NOT NULL,
    login           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    tg_id           INTEGER,
    is_online       INTEGER DEFAULT 0,
    ref_code        TEXT UNIQUE,
    commission_pct  REAL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (role, login)
);

-- Учёт клиентов, пришедших по реф-ссылке партнёра (первый переход — навсегда привязан)
CREATE TABLE IF NOT EXISTS partner_referrals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_login   TEXT NOT NULL,
    user_tg_id      INTEGER UNIQUE NOT NULL,
    joined_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_sessions (
    tg_id           INTEGER PRIMARY KEY,
    role            TEXT NOT NULL,
    login           TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gender_channels (
    gender          TEXT NOT NULL,
    category        TEXT NOT NULL,
    chat_id         TEXT NOT NULL,
    invite_url      TEXT NOT NULL,
    PRIMARY KEY (gender, category)
);

CREATE TABLE IF NOT EXISTS brands (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    emoji           TEXT DEFAULT '🏷',
    gender          TEXT NOT NULL,
    category        TEXT NOT NULL,
    topic_id        INTEGER NOT NULL,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id        INTEGER REFERENCES brands(id),
    gender          TEXT NOT NULL,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    price           TEXT NOT NULL,
    size            TEXT,
    description     TEXT,
    photo_file_id   TEXT NOT NULL,
    tg_message_id   INTEGER,
    admin_login     TEXT,
    in_stock        INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Лист ожидания: кто кликнул "уведомить когда появится" по закончившемуся товару
CREATE TABLE IF NOT EXISTS stock_interest (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         INTEGER NOT NULL,
    user_tg_id      INTEGER NOT NULL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cart (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id      INTEGER NOT NULL,
    post_id         INTEGER REFERENCES channel_posts(id),
    added_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (user_tg_id, post_id)
);

CREATE TABLE IF NOT EXISTS wishlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id      INTEGER NOT NULL,
    post_id         INTEGER REFERENCES channel_posts(id),
    added_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (user_tg_id, post_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id      INTEGER NOT NULL,
    status          TEXT DEFAULT 'pending',
    size            TEXT,
    comment         TEXT,
    total_price     REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    confirmed_at    TEXT,
    completed_at    TEXT,
    client_verified INTEGER DEFAULT 0,
    client_confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    post_id         INTEGER REFERENCES channel_posts(id),
    title           TEXT,
    price           TEXT,
    size            TEXT,
    photo_file_id   TEXT,
    brand_id        INTEGER REFERENCES brands(id)
);

CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id      INTEGER NOT NULL,
    username        TEXT,
    status          TEXT DEFAULT 'new',
    admin_login     TEXT,
    admin_tg_id     INTEGER,
    last_message    TEXT,
    rating          INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    taken_at        TEXT,
    closed_at       TEXT
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id       INTEGER REFERENCES tickets(id) ON DELETE CASCADE,
    sender          TEXT NOT NULL,
    text            TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS finance_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id        INTEGER REFERENCES orders(id),
    revenue         REAL DEFAULT 0,
    cost            REAL DEFAULT 0,
    profit          REAL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS warehouse_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    warehouse_tg_id INTEGER NOT NULL,
    order_id        INTEGER REFERENCES orders(id),
    title           TEXT,
    price           TEXT,
    photo_file_id   TEXT,
    report_channel_msg_id INTEGER,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bot_texts (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT
);

-- Кэш динамических переводов (чтобы не дёргать внешний сервис повторно на одну фразу)
CREATE TABLE IF NOT EXISTS translation_cache (
    source_text     TEXT NOT NULL,
    lang            TEXT NOT NULL,
    translated      TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (source_text, lang)
);

CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_wish_user ON wishlist(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_brands_gender_cat ON brands(gender, category);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
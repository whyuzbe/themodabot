-- ════════════════════════════════════════════════════════════════
--  Schema: TheModa shop bot (Postgres)
-- ════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    tg_id           BIGINT UNIQUE NOT NULL,
    username        TEXT,
    phone           TEXT,
    gender          TEXT,                  -- male / female
    language        TEXT DEFAULT 'ru',
    is_blocked      BOOLEAN DEFAULT FALSE,
    last_address    TEXT,
    language_auto   BOOLEAN DEFAULT FALSE,
    registered_at   TIMESTAMPTZ DEFAULT now()
);

-- Сохранённые размеры клиента, отдельно по категории (обувь/одежда/...)
CREATE TABLE IF NOT EXISTS user_sizes (
    user_tg_id      BIGINT NOT NULL,
    category        TEXT NOT NULL,
    size            TEXT NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_tg_id, category)
);

-- Стафф-аккаунты (admin / manager / warehouse) — единая таблица с ролью
CREATE TABLE IF NOT EXISTS staff_accounts (
    id              SERIAL PRIMARY KEY,
    role            TEXT NOT NULL,         -- admin / manager / warehouse / partner
    login           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    tg_id           BIGINT,
    is_online       BOOLEAN DEFAULT FALSE,
    ref_code        TEXT UNIQUE,
    commission_pct  NUMERIC(5,2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (role, login)
);

-- Учёт клиентов, пришедших по реф-ссылке партнёра (первый переход — навсегда привязан)
CREATE TABLE IF NOT EXISTS partner_referrals (
    id              SERIAL PRIMARY KEY,
    partner_login   TEXT NOT NULL,
    user_tg_id      BIGINT UNIQUE NOT NULL,
    joined_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staff_sessions (
    tg_id           BIGINT PRIMARY KEY,
    role            TEXT NOT NULL,
    login           TEXT NOT NULL,
    expires_at      TEXT NOT NULL
);

-- Каналы: 7 шт — по одному на каждую пару (пол, категория)
CREATE TABLE IF NOT EXISTS gender_channels (
    gender          TEXT NOT NULL,
    category        TEXT NOT NULL,
    chat_id         TEXT NOT NULL,
    invite_url      TEXT NOT NULL,
    PRIMARY KEY (gender, category)
);

-- Бренды = топики внутри одного из 2 каналов
CREATE TABLE IF NOT EXISTS brands (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    emoji           TEXT DEFAULT '🏷',
    gender          TEXT NOT NULL,         -- male / female
    category        TEXT NOT NULL,         -- clothes / shoes / accessories / bags
    topic_id         INTEGER NOT NULL,      -- message_thread_id топика бренда
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Посты, опубликованные админом в топик бренда (источник для корзины/wishlist)
CREATE TABLE IF NOT EXISTS channel_posts (
    id              SERIAL PRIMARY KEY,
    brand_id        INTEGER REFERENCES brands(id),
    gender          TEXT NOT NULL,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    price           TEXT NOT NULL,
    size            TEXT,
    description     TEXT,
    photo_file_id   TEXT NOT NULL,
    tg_message_id   BIGINT,
    admin_login     TEXT,
    in_stock        BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Лист ожидания: кто кликнул "уведомить когда появится" по закончившемуся товару
CREATE TABLE IF NOT EXISTS stock_interest (
    id              SERIAL PRIMARY KEY,
    post_id         INTEGER NOT NULL,
    user_tg_id      BIGINT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Корзина
CREATE TABLE IF NOT EXISTS cart (
    id              SERIAL PRIMARY KEY,
    user_tg_id      BIGINT NOT NULL,
    post_id         INTEGER REFERENCES channel_posts(id),
    added_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_tg_id, post_id)
);

-- Wishlist (сохранённые)
CREATE TABLE IF NOT EXISTS wishlist (
    id              SERIAL PRIMARY KEY,
    user_tg_id      BIGINT NOT NULL,
    post_id         INTEGER REFERENCES channel_posts(id),
    added_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_tg_id, post_id)
);

-- Заказы
CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    user_tg_id      BIGINT NOT NULL,
    status          TEXT DEFAULT 'pending', -- pending/confirmed/warehouse_received/completed/cancelled
    size            TEXT,
    comment         TEXT,
    total_price     NUMERIC(12,2),
    created_at      TIMESTAMPTZ DEFAULT now(),
    confirmed_at    TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    client_verified BOOLEAN DEFAULT FALSE,
    client_confirmed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    post_id         INTEGER REFERENCES channel_posts(id),
    title           TEXT,
    price           TEXT,
    size            TEXT,
    photo_file_id   TEXT,
    brand_id        INTEGER REFERENCES brands(id)
);

-- Тикеты поддержки
CREATE TABLE IF NOT EXISTS tickets (
    id              SERIAL PRIMARY KEY,
    user_tg_id      BIGINT NOT NULL,
    username        TEXT,
    status          TEXT DEFAULT 'new',   -- new/waiting/in_progress/closed
    admin_login     TEXT,
    admin_tg_id     BIGINT,
    last_message    TEXT,
    rating          SMALLINT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    taken_at        TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id              SERIAL PRIMARY KEY,
    ticket_id       INTEGER REFERENCES tickets(id) ON DELETE CASCADE,
    sender          TEXT NOT NULL,         -- user / admin
    text            TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Финансовые записи (для аналитики менеджера)
CREATE TABLE IF NOT EXISTS finance_entries (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER REFERENCES orders(id),
    revenue         NUMERIC(12,2) DEFAULT 0,
    cost            NUMERIC(12,2) DEFAULT 0,
    profit          NUMERIC(12,2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Фотоотчёты склада
CREATE TABLE IF NOT EXISTS warehouse_reports (
    id              SERIAL PRIMARY KEY,
    warehouse_tg_id BIGINT NOT NULL,
    order_id        INTEGER REFERENCES orders(id),
    title           TEXT,
    price           TEXT,
    photo_file_id   TEXT,
    report_channel_msg_id BIGINT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Редактируемые тексты/баннеры
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
    created_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (source_text, lang)
);

CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_wish_user ON wishlist(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_tg_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_brands_gender_cat ON brands(gender, category);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
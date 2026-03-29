-- =============================================================================
-- init_db.sql — Инициализация базы данных МедПлатформа
-- Автор: Аль-Раве Мустафа Исам Табит · РГСУ · спец. 2.3.5
-- Запустить: psql "postgresql://gen_user:ПАРОЛЬ@2becf44e38c66a65b2f1dfc5.twc1.net:5432/default_db?sslmode=require" -f init_db.sql
-- =============================================================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- для поиска по тексту

-- =============================================================================
-- Таблица пользователей
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id            VARCHAR(50)  PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('doctor','patient','admin')),
    password_hash VARCHAR(64)  NOT NULL,
    posts_count   INTEGER      DEFAULT 0,
    likes_count   INTEGER      DEFAULT 0,
    is_anomalous  BOOLEAN      DEFAULT FALSE,
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- Таблица публикаций
-- =============================================================================
CREATE TABLE IF NOT EXISTS posts (
    id          VARCHAR(50)   PRIMARY KEY DEFAULT 'p' || extract(epoch from now())::bigint,
    author_id   VARCHAR(50)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(500)  NOT NULL,
    body        TEXT          NOT NULL,
    status      VARCHAR(30)   NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('approved','pending','blocked','suspicious')),
    mod_level   SMALLINT      DEFAULT 1,
    mod_conf    NUMERIC(4,3)  DEFAULT 0,
    likes_count INTEGER       DEFAULT 0,
    created_at  TIMESTAMPTZ   DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- =============================================================================
-- Таблица тегов
-- =============================================================================
CREATE TABLE IF NOT EXISTS tags (
    id      SERIAL      PRIMARY KEY,
    name    VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS post_tags (
    post_id VARCHAR(50) REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  INTEGER     REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

-- =============================================================================
-- Таблица лайков
-- =============================================================================
CREATE TABLE IF NOT EXISTS likes (
    user_id VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    post_id VARCHAR(50) REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- =============================================================================
-- Таблица рекомендаций (кеш)
-- =============================================================================
CREATE TABLE IF NOT EXISTS recommendations (
    user_id    VARCHAR(50)  REFERENCES users(id) ON DELETE CASCADE,
    post_id    VARCHAR(50)  REFERENCES posts(id) ON DELETE CASCADE,
    score      NUMERIC(6,4) NOT NULL,
    cbf_score  NUMERIC(6,4) DEFAULT 0,
    svd_score  NUMERIC(6,4) DEFAULT 0,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- =============================================================================
-- Таблица JWT-сессий (токены)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    token      VARCHAR(100) PRIMARY KEY,
    user_id    VARCHAR(50)  REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ  NOT NULL,
    created_at TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- Таблица результатов модерации (лог)
-- =============================================================================
CREATE TABLE IF NOT EXISTS moderation_log (
    id          SERIAL       PRIMARY KEY,
    post_id     VARCHAR(50)  REFERENCES posts(id) ON DELETE SET NULL,
    input_text  TEXT         NOT NULL,
    label       VARCHAR(20)  NOT NULL,
    confidence  NUMERIC(4,3) NOT NULL,
    level       SMALLINT     NOT NULL,
    reasons     TEXT[],
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- Индексы для производительности
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_posts_author   ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_status   ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_created  ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recs_user      ON recommendations(user_id, score DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_exp   ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_posts_trgm     ON posts USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_posts_body_trgm ON posts USING GIN (body gin_trgm_ops);

-- =============================================================================
-- Начальные данные
-- =============================================================================
INSERT INTO users (id, name, role, password_hash, posts_count, likes_count) VALUES
    ('user1', 'Д-р Петров А.С.',  'doctor',  encode(sha256('doctor123'),  'hex'), 42, 287),
    ('user2', 'Мария Иванова',    'patient', encode(sha256('patient123'), 'hex'),  8,  34),
    ('admin', 'Администратор',    'admin',   encode(sha256('admin123'),   'hex'),  0,   0)
ON CONFLICT (id) DO NOTHING;

INSERT INTO tags (name) VALUES
    ('кардиология'), ('диабет'), ('неврология'),
    ('педиатрия'), ('реабилитация'), ('антибиотики'),
    ('онкология'), ('терапия'), ('диагностика'), ('хирургия')
ON CONFLICT (name) DO NOTHING;

INSERT INTO posts (id, author_id, title, body, status, likes_count) VALUES
(
    'p1', 'user1',
    'Реабилитация после инфаркта миокарда',
    'После перенесённого инфаркта миокарда крайне важно соблюдать программу кардиореабилитации. Первые 6 недель — ограниченная физическая активность, диета с ограничением соли и жиров.',
    'approved', 34
),
(
    'p2', 'user2',
    'Как принимать метформин при диабете 2 типа?',
    'Врач назначил метформин 500мг. Когда лучше принимать — до или после еды? Есть ли побочные эффекты при длительном приёме?',
    'approved', 12
),
(
    'p3', 'user1',
    'Профилактика ОРВИ у детей дошкольного возраста',
    'Закаливание, регулярное проветривание, промывание носа физраствором и вакцинация от гриппа значительно снижают частоту заболеваний.',
    'approved', 56
)
ON CONFLICT (id) DO NOTHING;

-- Связь постов с тегами
INSERT INTO post_tags (post_id, tag_id)
SELECT 'p1', id FROM tags WHERE name IN ('кардиология','реабилитация')
ON CONFLICT DO NOTHING;

INSERT INTO post_tags (post_id, tag_id)
SELECT 'p2', id FROM tags WHERE name IN ('диабет','терапия')
ON CONFLICT DO NOTHING;

INSERT INTO post_tags (post_id, tag_id)
SELECT 'p3', id FROM tags WHERE name IN ('педиатрия','диагностика')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Проверка
-- =============================================================================
SELECT 'users'     AS table_name, COUNT(*) AS rows FROM users    UNION ALL
SELECT 'posts',    COUNT(*) FROM posts     UNION ALL
SELECT 'tags',     COUNT(*) FROM tags      UNION ALL
SELECT 'post_tags',COUNT(*) FROM post_tags;

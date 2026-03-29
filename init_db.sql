-- ============================================================
-- МедПлатформа — Инициализация PostgreSQL
-- Запустить один раз через Веб-интерфейс БД (Adminer)
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Пользователи
CREATE TABLE IF NOT EXISTS users (
    id            VARCHAR(50)  PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('doctor','patient','admin')),
    password_hash VARCHAR(64)  NOT NULL,
    posts_count   INTEGER      DEFAULT 0,
    likes_count   INTEGER      DEFAULT 0,
    is_anomalous  BOOLEAN      DEFAULT FALSE,
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);

-- Публикации
CREATE TABLE IF NOT EXISTS posts (
    id          VARCHAR(50)   PRIMARY KEY,
    author_id   VARCHAR(50)   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(500)  NOT NULL,
    body        TEXT          NOT NULL,
    status      VARCHAR(20)   NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('approved','pending','blocked','suspicious')),
    mod_level   SMALLINT      DEFAULT 1,
    mod_conf    NUMERIC(5,3)  DEFAULT 0,
    likes_count INTEGER       DEFAULT 0,
    created_at  TIMESTAMPTZ   DEFAULT NOW()
);

-- Теги
CREATE TABLE IF NOT EXISTS tags (
    id   SERIAL       PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS post_tags (
    post_id VARCHAR(50) REFERENCES posts(id) ON DELETE CASCADE,
    tag_id  INTEGER     REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
);

-- Лайки
CREATE TABLE IF NOT EXISTS likes (
    user_id    VARCHAR(50) REFERENCES users(id) ON DELETE CASCADE,
    post_id    VARCHAR(50) REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_posts_status  ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_likes_user    ON likes(user_id);

-- ── Начальные данные ──────────────────────────────────────
INSERT INTO users (id, name, role, password_hash, posts_count, likes_count)
VALUES
    ('user1','Д-р Петров А.С.', 'doctor',  encode(sha256('doctor123' ::bytea),'hex'), 42, 287),
    ('user2','Мария Иванова',   'patient', encode(sha256('patient123'::bytea),'hex'),  8,  34),
    ('admin','Администратор',   'admin',   encode(sha256('admin123'  ::bytea),'hex'),  0,   0)
ON CONFLICT (id) DO NOTHING;

INSERT INTO tags (name) VALUES
    ('кардиология'),('диабет'),('неврология'),
    ('педиатрия'),('реабилитация'),('антибиотики'),
    ('онкология'),('терапия'),('диагностика'),('хирургия')
ON CONFLICT (name) DO NOTHING;

INSERT INTO posts (id, author_id, title, body, status, likes_count)
VALUES
    ('p1','user1',
     'Реабилитация после инфаркта миокарда',
     'После инфаркта важна кардиореабилитация. Первые 6 недель — ограниченная активность, диета.',
     'approved', 34),
    ('p2','user2',
     'Как принимать метформин при диабете 2 типа?',
     'Врач назначил метформин 500мг. Когда лучше принимать — до или после еды?',
     'approved', 12),
    ('p3','user1',
     'Профилактика ОРВИ у детей',
     'Закаливание, проветривание, промывание носа физраствором и вакцинация от гриппа.',
     'approved', 56)
ON CONFLICT (id) DO NOTHING;

INSERT INTO post_tags (post_id, tag_id)
SELECT 'p1', id FROM tags WHERE name IN ('кардиология','реабилитация') ON CONFLICT DO NOTHING;
INSERT INTO post_tags (post_id, tag_id)
SELECT 'p2', id FROM tags WHERE name IN ('диабет','терапия')           ON CONFLICT DO NOTHING;
INSERT INTO post_tags (post_id, tag_id)
SELECT 'p3', id FROM tags WHERE name IN ('педиатрия','диагностика')    ON CONFLICT DO NOTHING;

-- Проверка
SELECT 'users'     AS tbl, COUNT(*) n FROM users     UNION ALL
SELECT 'posts',    COUNT(*) FROM posts      UNION ALL
SELECT 'tags',     COUNT(*) FROM tags       UNION ALL
SELECT 'post_tags',COUNT(*) FROM post_tags;

-- Tiny Second-hand Shopping Platform 스키마
-- 모든 쿼리는 애플리케이션 코드에서 파라미터 바인딩(?)으로만 실행한다.

PRAGMA foreign_keys = ON;

-- 사용자
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,              -- UUID
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,                 -- 평문 저장 금지, 해시만 저장
    bio           TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'user'   -- 'user' | 'admin'
                     CHECK (role IN ('user', 'admin')),
    status        TEXT NOT NULL DEFAULT 'active' -- 'active' | 'blocked'
                     CHECK (status IN ('active', 'blocked')),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 상품
CREATE TABLE IF NOT EXISTS products (
    id          TEXT PRIMARY KEY,                -- UUID
    seller_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    price       INTEGER NOT NULL CHECK (price >= 0),
    image_path  TEXT,                            -- static/uploads 하위 상대경로
    status      TEXT NOT NULL DEFAULT 'available'
                   CHECK (status IN ('available', 'sold', 'hidden')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (seller_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 1:1 채팅 메시지
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    sender_id   TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (sender_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 신고 (유저/상품 대상)
CREATE TABLE IF NOT EXISTS reports (
    id           TEXT PRIMARY KEY,
    reporter_id  TEXT NOT NULL,
    target_type  TEXT NOT NULL CHECK (target_type IN ('user', 'product')),
    target_id    TEXT NOT NULL,
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved')),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------------
-- 송금(직거래) 관련
--
-- 이 플랫폼은 사용자의 돈을 절대 보유·중개하지 않는다.
-- 구매자가 자신의 은행 앱으로 판매자에게 직접 이체하고,
-- 플랫폼은 '거래 상태'만 기록한다. (전자금융업 규제 대상 아님)
-- ---------------------------------------------------------------------------

-- 판매자 정산 계좌 (민감 개인정보 → 계좌번호는 AES-GCM 암호문으로만 저장)
CREATE TABLE IF NOT EXISTS payout_accounts (
    user_id       TEXT PRIMARY KEY,
    bank_name     TEXT NOT NULL,
    account_enc   TEXT NOT NULL,   -- 암호문(base64). 평문 저장 금지
    account_last4 TEXT NOT NULL,   -- 마스킹 표시용 뒤 4자리
    holder_name   TEXT NOT NULL,
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 거래: 구매요청 → 판매자수락 → 구매자송금 → 판매자입금확인
CREATE TABLE IF NOT EXISTS trades (
    id         TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    buyer_id   TEXT NOT NULL,
    seller_id  TEXT NOT NULL,
    amount     INTEGER NOT NULL CHECK (amount >= 0),
    status     TEXT NOT NULL DEFAULT 'requested'
                  CHECK (status IN ('requested', 'accepted', 'sent', 'confirmed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id)   REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (seller_id)  REFERENCES users(id)    ON DELETE CASCADE
);

-- 감사 로그: 계좌 열람 등 민감 행위 추적
CREATE TABLE IF NOT EXISTS audit_logs (
    id         TEXT PRIMARY KEY,
    actor_id   TEXT,
    action     TEXT NOT NULL,
    target     TEXT,
    ip         TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_seller ON products(seller_id);
CREATE INDEX IF NOT EXISTS idx_messages_pair   ON messages(sender_id, receiver_id);
CREATE INDEX IF NOT EXISTS idx_reports_target  ON reports(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_trades_buyer    ON trades(buyer_id);
CREATE INDEX IF NOT EXISTS idx_trades_seller   ON trades(seller_id);
-- 한 상품에 대해 진행 중인 거래는 구매자당 하나만 허용 (중복 요청 방지)
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_active
    ON trades(product_id, buyer_id)
    WHERE status IN ('requested', 'accepted', 'sent');

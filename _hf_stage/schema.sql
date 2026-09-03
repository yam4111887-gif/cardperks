-- =========================================================
-- 卡優惠 CardPerks — PostgreSQL Schema (14+)
-- 對應互動原型 index.html 的資料模型，並包含資料更新管線
-- （爬蟲 → LLM 解析 pending → 人工審核 approved）所需欄位。
-- =========================================================

CREATE TYPE offer_status  AS ENUM ('pending', 'approved', 'rejected', 'expired');
CREATE TYPE pay_channel   AS ENUM ('any', 'line_pay', 'pi_wallet', 'jkopay', 'full_pay', 'tap', 'other');
CREATE TYPE sub_plan      AS ENUM ('free', 'pro_monthly', 'pro_yearly');
CREATE TYPE store_src     AS ENUM ('appstore', 'googleplay', 'web');
CREATE TYPE reminder_type AS ENUM ('offer_expiry', 'quota_low', 'login_needed', 'new_offer');

-- ---------- 基礎資料：銀行 / 卡 ----------

CREATE TABLE banks (
  id            serial PRIMARY KEY,
  code          text UNIQUE NOT NULL,          -- 'taishin'
  name          text NOT NULL,                 -- '台新銀行'
  short_name    text NOT NULL,                 -- '台新'（原型卡片色塊用）
  brand_color   text,                          -- 品牌色（UI）
  official_site text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cards (
  id           serial PRIMARY KEY,
  bank_id      int NOT NULL REFERENCES banks(id),
  slug         text UNIQUE NOT NULL,           -- 'gogo'（對應原型 CARDS[].id）
  name         text NOT NULL,                  -- '@GoGo icash 聯名卡'
  network      text,                           -- Visa / Mastercard / JCB
  annual_fee   text,                           -- 年費與減免條件（描述）
  base_reward  numeric(4,2),                   -- 一般消費回饋率（%）
  base_note    text,                           -- '一般 1%．數位帳戶加碼'
  is_active    bool NOT NULL DEFAULT true,
  source_url   text,                           -- 官方權益頁（追溯用）
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_cards_bank ON cards(bank_id) WHERE is_active;

-- ---------- 商家 / 據點 ----------

CREATE TABLE merchants (
  id         serial PRIMARY KEY,
  slug       text UNIQUE NOT NULL,             -- 'pxmart'
  name       text NOT NULL,                    -- '全聯福利中心'
  category   text NOT NULL,                    -- 超市/超商/量販/網購/外送/加油/餐廳/娛樂
  is_online  bool NOT NULL DEFAULT false,      -- 網購/外送不進地圖
  aliases    text[] NOT NULL DEFAULT '{}',     -- 搜尋別名：{'全聯','pxmart'}
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_merchants_cat ON merchants(category);

-- 地圖據點；量大後可升級 PostGIS geography 欄位與 GiST 索引做「附近商家」查詢
CREATE TABLE merchant_locations (
  id          serial PRIMARY KEY,
  merchant_id int NOT NULL REFERENCES merchants(id),
  name        text,                            -- 分店名：'南京建國店'
  lat         numeric(10,7) NOT NULL,
  lng         numeric(10,7) NOT NULL,
  address     text,
  is_active   bool NOT NULL DEFAULT true
);
CREATE INDEX idx_loc_merchant ON merchant_locations(merchant_id);

-- ---------- 優惠（核心資料表） ----------

CREATE TABLE offers (
  id             bigserial PRIMARY KEY,
  card_id        int NOT NULL REFERENCES cards(id),
  merchant_id    int REFERENCES merchants(id), -- NULL = 類別型優惠（如「網購全面 3.8%」）
  channel        text,                         -- 類別型優惠的通路：'網購'/'行動支付'
  reward_rate    numeric(5,2) NOT NULL,        -- 回饋率（%）；與 reward_fixed 二擇一
  reward_fixed   numeric(10,2),                -- 固定金額回饋（少數活動）
  monthly_cap    numeric(10,2) NOT NULL DEFAULT 0,  -- 0 = 無上限
  requires_login bool NOT NULL DEFAULT false,  -- 需登錄
  pay_channel    pay_channel NOT NULL DEFAULT 'any',
  terms          text,                         -- 排富、限新戶、限指定門市等條款全文
  starts_on      date,
  ends_on        date NOT NULL,
  source_url     text NOT NULL,                -- 優惠出處（銀行公告頁）
  status         offer_status NOT NULL DEFAULT 'pending',  -- LLM 解析入庫後待人工審核
  verified_at    timestamptz,                  -- 審核通過時間
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (merchant_id IS NOT NULL OR channel IS NOT NULL),
  CHECK (reward_rate > 0 OR reward_fixed > 0)
);
CREATE INDEX idx_offers_card_end ON offers(card_id, ends_on) WHERE status = 'approved';
CREATE INDEX idx_offers_merchant_end ON offers(merchant_id, ends_on) WHERE status = 'approved';
CREATE INDEX idx_offers_pending ON offers(created_at) WHERE status = 'pending';  -- 審核佇列

-- 審計：每次爬蟲/LLM/人工改動留痕，資料錯誤可回溯
CREATE TABLE offer_revisions (
  id         bigserial PRIMARY KEY,
  offer_id   bigint NOT NULL REFERENCES offers(id),
  changed_by text NOT NULL,                    -- 'crawler' | 'llm' | 'editor'
  diff       jsonb NOT NULL,                   -- { "reward_rate": {"old": 3.0, "new": 3.8} }
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- 使用者 / 卡簿 ----------

CREATE TABLE users (
  id           bigserial PRIMARY KEY,
  email        text UNIQUE,
  line_user_id text UNIQUE,                    -- 台灣市場建議 LINE Login
  display_name text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_cards (
  user_id   bigint NOT NULL REFERENCES users(id),
  card_id   int NOT NULL REFERENCES cards(id),
  nickname  text,                              -- '皮夾左邊那張'
  added_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, card_id)
);

-- 回饋額度計數器：額度用罄推播的資料來源
CREATE TABLE usage_quotas (
  id          bigserial PRIMARY KEY,
  user_id     bigint NOT NULL REFERENCES users(id),
  card_id     int NOT NULL REFERENCES cards(id),
  period      date NOT NULL,                   -- 月份第一天：2026-08-01
  cap_amount  numeric(10,2) NOT NULL,          -- 該期上限（自 offers 快照）
  used_amount numeric(10,2) NOT NULL DEFAULT 0,-- 使用者手動輸入或帳單解析累計
  UNIQUE (user_id, card_id, period)
);

-- ---------- 提醒 ----------

CREATE TABLE reminders (
  id         bigserial PRIMARY KEY,
  user_id    bigint NOT NULL REFERENCES users(id),
  offer_id   bigint REFERENCES offers(id),
  type       reminder_type NOT NULL,
  title      text NOT NULL,
  body       text,
  fire_at    timestamptz NOT NULL,             -- 預定推播時間
  is_read    bool NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_reminders_user_fire ON reminders(user_id, fire_at) WHERE is_read = false;

-- ---------- 訂閱 ----------

CREATE TABLE subscriptions (
  id           bigserial PRIMARY KEY,
  user_id      bigint NOT NULL REFERENCES users(id),
  plan         sub_plan NOT NULL DEFAULT 'free',
  store        store_src NOT NULL,             -- App Store / Google Play / 官網
  store_txn_id text,                           -- 商店訂閱憑證（伺服器驗證用）
  starts_at    timestamptz,
  ends_at      timestamptz,
  auto_renew   bool NOT NULL DEFAULT true,
  is_active    bool NOT NULL DEFAULT true
);
CREATE INDEX idx_subs_user ON subscriptions(user_id) WHERE is_active;

-- 免費版卡簿上限（對應原型 FREE_LIMIT = 5）；其他功能開關也可放這裡
CREATE TABLE feature_flags (
  key    text PRIMARY KEY,
  value  jsonb NOT NULL,
  note   text
);
INSERT INTO feature_flags (key, value, note) VALUES
  ('free_card_limit', '5', '免費版卡簿張數上限'),
  ('pro_price_monthly_twd', '79', 'Pro 月訂價（原型示範）');

-- ---------- 帳單健檢（Pro 功能） ----------

CREATE TABLE bills (
  id             bigserial PRIMARY KEY,
  user_id        bigint NOT NULL REFERENCES users(id),
  period         date NOT NULL,                -- 帳單月份
  uploaded_at    timestamptz NOT NULL DEFAULT now(),
  file_url       text,                         -- OCR 用暫存；分析後可刪除原始檔
  total_spend    numeric(12,2),
  actual_reward  numeric(10,2),                -- 實際拿到的回饋
  optimal_reward numeric(10,2),                -- 全部刷對卡的可得回饋
  missed_reward  numeric(10,2)                 -- 少賺（= optimal - actual，付費說服點）
);

CREATE TABLE bill_items (
  id                bigserial PRIMARY KEY,
  bill_id           bigint NOT NULL REFERENCES bills(id),
  merchant_id       int REFERENCES merchants(id),
  merchant_raw      text,                      -- 帳單上的原始商家字串（OCR）
  spend_date        date,
  amount            numeric(10,2) NOT NULL,
  used_card_id      int REFERENCES cards(id),
  suggested_card_id int REFERENCES cards(id),  -- AI 建議改刷的卡
  delta_reward      numeric(10,2)              -- 改刷可多拿的回饋
);
CREATE INDEX idx_bill_items_bill ON bill_items(bill_id);

-- ---------- 變現：辦卡分潤 ----------

CREATE TABLE affiliate_clicks (
  id           bigserial PRIMARY KEY,
  user_id      bigint REFERENCES users(id),    -- 可為匿名
  card_id      int NOT NULL REFERENCES cards(id),
  partner      text NOT NULL,                  -- 'money101' | 'bank_direct' | ...
  clicked_at   timestamptz NOT NULL DEFAULT now(),
  converted_at timestamptz,
  commission    numeric(10,2)                  -- 確認轉換後回填
);
CREATE INDEX idx_aff_card ON affiliate_clicks(card_id, clicked_at);

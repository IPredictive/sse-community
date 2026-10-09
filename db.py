import os
import pymysql
import pandas as pd
from contextlib import contextmanager

def get_conn():
    required = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing database environment variables: " + ", ".join(missing))
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

@contextmanager
def connection():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    statements = [
        """CREATE TABLE IF NOT EXISTS daily_index (
            date DATE PRIMARY KEY, open DOUBLE, high DOUBLE, low DOUBLE,
            close DOUBLE, volume DOUBLE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS predictions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            base_date DATE NOT NULL, agent VARCHAR(40) NOT NULL,
            prob_up DOUBLE NOT NULL, reason TEXT,
            confidence DOUBLE DEFAULT 0.5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_prediction_date_agent (base_date, agent),
            KEY idx_predictions_date (base_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS users (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(40) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            points INT NOT NULL DEFAULT 3000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            KEY idx_users_points (points)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS votes (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            target_date DATE NOT NULL,
            direction ENUM('bull','bear') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_target (user_id, target_date),
            KEY idx_votes_target (target_date),
            CONSTRAINT fk_votes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS point_ledger (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            change_amount INT NOT NULL,
            reason VARCHAR(200) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            KEY idx_ledger_user (user_id),
            CONSTRAINT fk_ledger_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    ]
    with connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)

def load_daily():
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT date, open, high, low, close, volume FROM daily_index ORDER BY date")
            rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df

def upsert_daily(df):
    if df is None or df.empty:
        return
    sql = """INSERT INTO daily_index (date,open,high,low,close,volume)
             VALUES (%s,%s,%s,%s,%s,%s)
             ON DUPLICATE KEY UPDATE open=VALUES(open), high=VALUES(high),
             low=VALUES(low), close=VALUES(close), volume=VALUES(volume)"""
    rows = []
    for _, r in df.iterrows():
        rows.append((str(r["date"])[:10], float(r["open"]), float(r["high"]),
                     float(r["low"]), float(r["close"]), float(r["volume"])))
    with connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)

def save_prediction(base_date, agent, prob_up, reason, confidence=0.5):
    sql = """INSERT INTO predictions (base_date,agent,prob_up,reason,confidence)
             VALUES (%s,%s,%s,%s,%s)
             ON DUPLICATE KEY UPDATE prob_up=VALUES(prob_up), reason=VALUES(reason),
             confidence=VALUES(confidence), created_at=CURRENT_TIMESTAMP"""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (str(base_date)[:10], agent, float(prob_up), str(reason or ""), float(confidence)))

def refresh_predictions_for_date(base_date):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM predictions WHERE base_date=%s", (str(base_date)[:10],))

def load_predictions():
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT base_date,agent,prob_up,reason,confidence,created_at FROM predictions ORDER BY base_date,agent")
            rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if not df.empty:
        df["base_date"] = pd.to_datetime(df["base_date"]).dt.strftime("%Y-%m-%d")
    return df

def load_scored():
    q = """SELECT p.base_date,p.agent,p.prob_up,
                  d1.close AS base_close,d2.close AS result_close
           FROM predictions p
           JOIN daily_index d1 ON d1.date=p.base_date
           JOIN daily_index d2 ON d2.date=(SELECT MIN(d3.date) FROM daily_index d3 WHERE d3.date>p.base_date)"""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(q)
            rows = cur.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["went_up"] = (df["result_close"] > df["base_close"]).astype(int)
    df["correct"] = ((df["prob_up"] > .5).astype(int) == df["went_up"]).astype(int)
    df["brier"] = (df["prob_up"] - df["went_up"]) ** 2
    return df.sort_values("base_date")

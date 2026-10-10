import sqlite3
from pathlib import Path
import pandas as pd
DB_PATH=Path(__file__).parent/"data"/"sse.db"
SCHEMA="""CREATE TABLE IF NOT EXISTS daily_index(date TEXT PRIMARY KEY,open REAL,high REAL,low REAL,close REAL,volume REAL);CREATE TABLE IF NOT EXISTS predictions(id INTEGER PRIMARY KEY AUTOINCREMENT,base_date TEXT NOT NULL,agent TEXT NOT NULL,prob_up REAL NOT NULL,reason TEXT,confidence REAL DEFAULT .5,created_at TEXT NOT NULL DEFAULT(datetime('now')),UNIQUE(base_date,agent));CREATE TRIGGER IF NOT EXISTS predictions_no_update BEFORE UPDATE ON predictions BEGIN SELECT RAISE(ABORT,'predictions are immutable'); END;CREATE TRIGGER IF NOT EXISTS predictions_no_delete BEFORE DELETE ON predictions BEGIN SELECT RAISE(ABORT,'predictions are immutable'); END;"""
def get_conn():DB_PATH.parent.mkdir(exist_ok=True);return sqlite3.connect(DB_PATH)
def init_db():
    with get_conn() as c:c.executescript(SCHEMA)
def upsert_daily(df):
    with get_conn() as c:c.executemany("INSERT OR REPLACE INTO daily_index VALUES (?,?,?,?,?,?)",df[["date","open","high","low","close","volume"]].values.tolist())
def load_daily():
    with get_conn() as c:return pd.read_sql("SELECT * FROM daily_index ORDER BY date",c)
def save_prediction(base_date,agent,prob_up,reason,confidence=.5):
    with get_conn() as c:c.execute("INSERT OR IGNORE INTO predictions(base_date,agent,prob_up,reason,confidence) VALUES(?,?,?,?,?)",(base_date,agent,float(prob_up),reason,float(confidence)))
def refresh_predictions_for_date(base_date):
    """Replace only the current run's predictions; historical predictions remain immutable."""
    with get_conn() as c:
        c.execute("DROP TRIGGER IF EXISTS predictions_no_delete")
        c.execute("DELETE FROM predictions WHERE base_date=?",(str(base_date),))
        c.execute("""CREATE TRIGGER predictions_no_delete BEFORE DELETE ON predictions
                     BEGIN SELECT RAISE(ABORT,'predictions are immutable'); END;""")
def load_predictions():
    with get_conn() as c:return pd.read_sql("SELECT base_date,agent,prob_up,reason,confidence,created_at FROM predictions ORDER BY base_date,agent",c)
def load_scored():
    q="SELECT p.base_date,p.agent,p.prob_up,(SELECT close FROM daily_index WHERE date=p.base_date) base_close,(SELECT close FROM daily_index d WHERE d.date>p.base_date ORDER BY d.date LIMIT 1) result_close FROM predictions p"
    with get_conn() as c:df=pd.read_sql(q,c)
    df=df.dropna(subset=["base_close","result_close"]).copy();df["went_up"]=(df.result_close>df.base_close).astype(int);df["correct"]=((df.prob_up>.5).astype(int)==df.went_up).astype(int);df["brier"]=(df.prob_up-df.went_up)**2;return df.sort_values("base_date")

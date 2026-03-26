import sqlite3
from datetime import datetime, timedelta

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  lang TEXT,
                  daily_count INTEGER,
                  last_reset TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS generations
                 (generation_id TEXT PRIMARY KEY,
                  user_id INTEGER,
                  category TEXT,
                  topic TEXT,
                  prompt TEXT,
                  response TEXT,
                  tokens_used INTEGER,
                  timestamp TEXT,
                  feedback_rating INTEGER,
                  feedback_comment TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  event_type TEXT,
                  details TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT lang, daily_count, last_reset FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_lang(user_id, lang):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, lang, daily_count, last_reset) VALUES (?, ?, 0, ?)",
              (user_id, lang, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def increment_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET daily_count = daily_count + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def log_generation(generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO generations
                 (generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (generation_id, user_id, category, topic, prompt, response, tokens_used, timestamp))
    conn.commit()
    conn.close()

def log_event(user_id, event_type, details):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    c.execute('''INSERT INTO events (user_id, event_type, details, timestamp)
                 VALUES (?, ?, ?, ?)''', (user_id, event_type, details, timestamp))
    conn.commit()
    conn.close()

def update_feedback(generation_id, rating, comment):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE generations
                 SET feedback_rating = ?, feedback_comment = ?
                 WHERE generation_id = ?''', (rating, comment, generation_id))
    conn.commit()
    conn.close()

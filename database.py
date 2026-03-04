import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.getenv("DB_PATH", "data/habits.db")

def get_connection():
    # Ensure the directory exists
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # habits table: stores daily check-ins
    c.execute('''
        CREATE TABLE IF NOT EXISTS habits (
            date TEXT PRIMARY KEY,
            wake_time TEXT,
            bath_time TEXT,
            wake_failed_tweeted INTEGER DEFAULT 0,
            bath_failed_tweeted INTEGER DEFAULT 0
        )
    ''')
    
    # user_stats table: stores consecutive failures
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            wake_consecutive_failures INTEGER DEFAULT 0,
            bath_consecutive_failures INTEGER DEFAULT 0
        )
    ''')
    
    # Initialize stats if empty
    c.execute('INSERT OR IGNORE INTO user_stats (id) VALUES (1)')
    conn.commit()
    conn.close()

def get_today_record(today_str: str = None):
    if today_str is None:
        today_str = date.today().isoformat()
        
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM habits WHERE date = ?', (today_str,))
    row = c.fetchone()
    if not row:
        c.execute('INSERT INTO habits (date) VALUES (?)', (today_str,))
        conn.commit()
        c.execute('SELECT * FROM habits WHERE date = ?', (today_str,))
        row = c.fetchone()
    conn.close()
    return dict(row)

def record_action(action: str, timestamp: str, today_str: str = None):
    if today_str is None:
        today_str = date.today().isoformat()
    
    # Ensure record exists
    get_today_record(today_str)
    
    conn = get_connection()
    c = conn.cursor()
    
    if action == "wake":
        c.execute('UPDATE habits SET wake_time = ? WHERE date = ? AND wake_time IS NULL', (timestamp, today_str))
    elif action == "bath":
        c.execute('UPDATE habits SET bath_time = ? WHERE date = ? AND bath_time IS NULL', (timestamp, today_str))
        
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def mark_tweeted(action: str, today_str: str = None):
    if today_str is None:
        today_str = date.today().isoformat()
        
    conn = get_connection()
    c = conn.cursor()
    
    if action == "wake":
        c.execute('UPDATE habits SET wake_failed_tweeted = 1 WHERE date = ?', (today_str,))
    elif action == "bath":
        c.execute('UPDATE habits SET bath_failed_tweeted = 1 WHERE date = ?', (today_str,))
        
    conn.commit()
    conn.close()

def get_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM user_stats WHERE id = 1')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {"wake_consecutive_failures": 0, "bath_consecutive_failures": 0}

def update_consecutive_failures(action: str, failed: bool):
    conn = get_connection()
    c = conn.cursor()
    
    if action == "wake":
        if failed:
            c.execute('UPDATE user_stats SET wake_consecutive_failures = wake_consecutive_failures + 1 WHERE id = 1')
        else:
            c.execute('UPDATE user_stats SET wake_consecutive_failures = 0 WHERE id = 1')
    elif action == "bath":
        if failed:
            c.execute('UPDATE user_stats SET bath_consecutive_failures = bath_consecutive_failures + 1 WHERE id = 1')
        else:
            c.execute('UPDATE user_stats SET bath_consecutive_failures = 0 WHERE id = 1')
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")

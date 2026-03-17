import sqlite3
import os
from datetime import date, datetime
from contextlib import closing

# DBファイルのパス。環境変数 DB_PATH で上書き可能（Dockerでのボリュームマウント用）
DB_PATH = os.getenv("DB_PATH", "data/habits.db")

def get_connection():
    """DBへの接続を返す。接続前に保存先ディレクトリを自動作成する。"""
    # DBファイルの保存先ディレクトリがなければ作成する
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # 取得した行を辞書のようにキー名でアクセスできるようにする
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """DBテーブルを初期化する（マルチユーザー対応）。アプリ起動時に呼ばれる。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        
        # 1. usersテーブル: LINE IDと内部サーバーIDの紐づけ
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_user_id TEXT UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 2. habitsテーブル: ユーザーごとの毎日のチェックイン記録
        # (date, user_id) の複合主キー
        c.execute('''
            CREATE TABLE IF NOT EXISTS habits (
                date TEXT,
                user_id INTEGER,
                wake_time TEXT,
                bath_time TEXT,
                wake_failed_tweeted INTEGER DEFAULT 0,
                bath_failed_tweeted INTEGER DEFAULT 0,
                PRIMARY KEY (date, user_id)
            )
        ''')
    
        # 3. user_statsテーブル: ユーザーごとの連続失敗回数
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                wake_consecutive_failures INTEGER DEFAULT 0,
                bath_consecutive_failures INTEGER DEFAULT 0
            )
        ''')
        
        # マイグレーション: 旧テーブルからの移行などの複雑な処理は今回は省略し、
        # 常に user_id=1 をデフォルトユーザー（管理者/初期ユーザー）として用意する仕組み
        c.execute('INSERT OR IGNORE INTO users (id, line_user_id) VALUES (1, ?)', (os.getenv("LINE_USER_ID", "DEFAULT_ADMIN"),))
        c.execute('INSERT OR IGNORE INTO user_stats (user_id) VALUES (1)')
        
        conn.commit()

def get_or_create_user(line_user_id: str):
    """LINE ID からユーザーIDを取得する。存在しない場合は新規作成する。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE line_user_id = ?', (line_user_id,))
        row = c.fetchone()
        if row:
            return row['id']
        else:
            c.execute('INSERT INTO users (line_user_id) VALUES (?)', (line_user_id,))
            user_id = c.lastrowid
            # 統計レコードも作成
            c.execute('INSERT INTO user_stats (user_id) VALUES (?)', (user_id,))
            conn.commit()
            return user_id

def get_all_users():
    """全ユーザーのリストを返す。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users')
        return [dict(row) for row in c.fetchall()]

def get_today_record(user_id: int, today_str: str = None):
    """指定ユーザーの指定日（デフォルト: 今日）の習慣記録を取得する。"""
    if today_str is None:
        today_str = date.today().isoformat()
        
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM habits WHERE date = ? AND user_id = ?', (today_str, user_id))
        row = c.fetchone()
        if not row:
            # 今日のレコードがなければ空レコードを挿入して再取得する
            c.execute('INSERT OR IGNORE INTO habits (date, user_id) VALUES (?, ?)', (today_str, user_id))
            conn.commit()
            c.execute('SELECT * FROM habits WHERE date = ? AND user_id = ?', (today_str, user_id))
            row = c.fetchone()
        return dict(row)

def record_action(user_id: int, action: str, timestamp: str, today_str: str = None):
    """ユーザーの習慣達成時刻を記録する。"""
    if today_str is None:
        today_str = date.today().isoformat()
    
    # レコード存在保証
    get_today_record(user_id, today_str)
    
    with closing(get_connection()) as conn:
        c = conn.cursor()
        if action == "wake":
            c.execute('UPDATE habits SET wake_time = ? WHERE date = ? AND user_id = ? AND wake_time IS NULL', (timestamp, today_str, user_id))
        elif action == "bath":
            c.execute('UPDATE habits SET bath_time = ? WHERE date = ? AND user_id = ? AND bath_time IS NULL', (timestamp, today_str, user_id))
            
        updated = c.rowcount > 0
        conn.commit()
        return updated

def mark_tweeted(user_id: int, action: str, today_str: str = None):
    """ツイート/通知済みフラグを立てる。"""
    if today_str is None:
        today_str = date.today().isoformat()
        
    with closing(get_connection()) as conn:
        c = conn.cursor()
        if action == "wake":
            c.execute('UPDATE habits SET wake_failed_tweeted = 1 WHERE date = ? AND user_id = ?', (today_str, user_id))
        elif action == "bath":
            c.execute('UPDATE habits SET bath_failed_tweeted = 1 WHERE date = ? AND user_id = ?', (today_str, user_id))
        conn.commit()

def get_stats(user_id: int):
    """ユーザーごとの統計を取得する。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM user_stats WHERE user_id = ?', (user_id,))
        row = c.fetchone()
    return dict(row) if row else {"wake_consecutive_failures": 0, "bath_consecutive_failures": 0}

def update_consecutive_failures(user_id: int, action: str, failed: bool):
    """連続失敗回数を更新する。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        if action == "wake":
            if failed:
                c.execute('UPDATE user_stats SET wake_consecutive_failures = wake_consecutive_failures + 1 WHERE user_id = ?', (user_id,))
            else:
                c.execute('UPDATE user_stats SET wake_consecutive_failures = 0 WHERE user_id = ?', (user_id,))
        elif action == "bath":
            if failed:
                c.execute('UPDATE user_stats SET bath_consecutive_failures = bath_consecutive_failures + 1 WHERE user_id = ?', (user_id,))
            else:
                c.execute('UPDATE user_stats SET bath_consecutive_failures = 0 WHERE user_id = ?', (user_id,))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("データベースをマルチユーザー対応で初期化しました。")

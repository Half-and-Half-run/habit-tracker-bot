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
    """DBテーブルを初期化する（存在しない場合のみ作成する）。アプリ起動時に呼ばれる。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        # habitsテーブル: 毎日のチェックイン記録を保存する
        # date: 日付（主キー）、wake_time/bath_time: 達成時刻、*_failed_tweeted: ツイート済みフラグ
        c.execute('''
            CREATE TABLE IF NOT EXISTS habits (
                date TEXT PRIMARY KEY,
                wake_time TEXT,
                bath_time TEXT,
                wake_failed_tweeted INTEGER DEFAULT 0,
                bath_failed_tweeted INTEGER DEFAULT 0
            )
        ''')
    
        # user_statsテーブル: 習慣ごとの連続失敗回数を保存する（行は常に1行だけ）
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                wake_consecutive_failures INTEGER DEFAULT 0,
                bath_consecutive_failures INTEGER DEFAULT 0
            )
        ''')
        
        # 統計レコードがなければ初期値（0）で挿入する（既存の場合は無視）
        c.execute('INSERT OR IGNORE INTO user_stats (id) VALUES (1)')
        conn.commit()

def get_today_record(today_str: str = None):
    """指定日（デフォルト: 今日）の習慣記録を取得する。
    
    レコードが存在しない場合は空の行を自動で作成してから返す。
    """
    if today_str is None:
        today_str = date.today().isoformat()
        
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM habits WHERE date = ?', (today_str,))
        row = c.fetchone()
        if not row:
            # 今日のレコードがなければ空レコードを挿入して再取得する
            c.execute('INSERT INTO habits (date) VALUES (?)', (today_str,))
            conn.commit()
            c.execute('SELECT * FROM habits WHERE date = ?', (today_str,))
            row = c.fetchone()
        return dict(row)

def record_action(action: str, timestamp: str, today_str: str = None):
    """習慣の達成時刻を記録する。
    
    同じ日に同じアクションが既に記録されている場合は更新せず False を返す（冪等性）。
    正常に記録できた場合は True を返す。
    """
    if today_str is None:
        today_str = date.today().isoformat()
    
    # 今日のレコードが存在することを保証する
    get_today_record(today_str)
    
    with closing(get_connection()) as conn:
        c = conn.cursor()
        
        # wake_time/bath_time が NULL のときだけ更新する（二重記録防止）
        if action == "wake":
            c.execute('UPDATE habits SET wake_time = ? WHERE date = ? AND wake_time IS NULL', (timestamp, today_str))
        elif action == "bath":
            c.execute('UPDATE habits SET bath_time = ? WHERE date = ? AND bath_time IS NULL', (timestamp, today_str))
            
        # rowcount > 0 なら実際に更新された（＝初回記録）
        updated = c.rowcount > 0
        conn.commit()
        return updated

def mark_tweeted(action: str, today_str: str = None):
    """失敗ツイートを送信済みとしてフラグを立てる。
    
    これにより同じ日に同じ習慣の失敗ツイートが二重投稿されるのを防ぐ。
    """
    if today_str is None:
        today_str = date.today().isoformat()
        
    with closing(get_connection()) as conn:
        c = conn.cursor()
        
        if action == "wake":
            c.execute('UPDATE habits SET wake_failed_tweeted = 1 WHERE date = ?', (today_str,))
        elif action == "bath":
            c.execute('UPDATE habits SET bath_failed_tweeted = 1 WHERE date = ?', (today_str,))
            
        conn.commit()

def get_stats():
    """起床・入浴それぞれの連続失敗回数を取得して辞書で返す。"""
    with closing(get_connection()) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM user_stats WHERE id = 1')
        row = c.fetchone()
        
    # レコードがない場合（DBが壊れたなど）はデフォルト値を返す
    return dict(row) if row else {"wake_consecutive_failures": 0, "bath_consecutive_failures": 0}

def update_consecutive_failures(action: str, failed: bool):
    """連続失敗回数を更新する。
    
    failed=True  → 指定した習慣の連続失敗回数を +1 する
    failed=False → 指定した習慣の連続失敗回数を 0 にリセットする（チェックイン成功時）
    """
    with closing(get_connection()) as conn:
        c = conn.cursor()
        
        if action == "wake":
            if failed:
                # 起床の連続失敗回数を増やす
                c.execute('UPDATE user_stats SET wake_consecutive_failures = wake_consecutive_failures + 1 WHERE id = 1')
            else:
                # 起床に成功したのでカウントをリセット
                c.execute('UPDATE user_stats SET wake_consecutive_failures = 0 WHERE id = 1')
        elif action == "bath":
            if failed:
                # 入浴の連続失敗回数を増やす
                c.execute('UPDATE user_stats SET bath_consecutive_failures = bath_consecutive_failures + 1 WHERE id = 1')
            else:
                # 入浴に成功したのでカウントをリセット
                c.execute('UPDATE user_stats SET bath_consecutive_failures = 0 WHERE id = 1')
                
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("データベースを初期化しました。")

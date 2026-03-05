# コードレビュー報告書 / Code Review Report

**プロジェクト名 / Project:** Habit Tracker Webhook Bot  
**レビュー日 / Review Date:** 2026-03-05  
**レビュー対象ファイル / Files Reviewed:** `main.py`, `database.py`, `twitter.py`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `README.md`

---

## 1. プロジェクト概要 / Project Overview

このBotは**習慣化トラッキング**を目的としたWebhook対応のAPIサーバーです。  
This is a webhook-enabled API server designed for **habit tracking**.

### 主な機能 / Core Features

| 機能 | 概要 |
|------|------|
| チェックイン記録 | `POST /checkin` でアクション（起床・入浴）を記録する |
| 失敗自動ツイート | 締め切り時刻を過ぎても未記録なら自動的にTwitterへ失敗をツイートする |
| 連続失敗カウント | 連続して失敗した回数をDBで管理し、ツイートに反映する |
| 定期チェック | APSchedulerで1時間ごとに締め切り超過を確認する |
| ステータス確認 | `GET /status` で本日の記録と統計情報を返す |

### 技術スタック / Tech Stack

- **Webフレームワーク:** FastAPI + Uvicorn
- **データベース:** SQLite (`data/habits.db`)
- **外部API連携:** Twitter API v2 (Tweepy)
- **スケジューラ:** APScheduler
- **コンテナ:** Docker / Docker Compose
- **Python:** 3.11+

---

## 2. 要件定義と実装状況 / Requirements vs. Implementation

### 2.1 機能要件 / Functional Requirements

| # | 要件 | 実装状況 | 備考 |
|---|------|----------|------|
| F-1 | `POST /checkin` で `wake` / `bath` アクションを記録できる | ✅ 実装済み | `main.py:79-95` |
| F-2 | 同日に同じアクションを2回記録しても無視（冪等性） | ✅ 実装済み | `database.py:69-71` の `wake_time IS NULL` 条件 |
| F-3 | 締め切り時刻（起床=9:00、入浴=23:00）を過ぎたら失敗判定する | ✅ 実装済み | `main.py:35-52` |
| F-4 | 失敗時にTwitterへ自動ツイートする | ✅ 実装済み | `twitter.py:22-43` |
| F-5 | 失敗ツイートは1日1回だけ送信する（重複防止） | ✅ 実装済み | `wake_failed_tweeted` フラグ |
| F-6 | 連続失敗回数をカウントし、ツイートに含める | ✅ 実装済み | `database.py:101-117` |
| F-7 | チェックイン成功時に連続失敗カウントをリセットする | ✅ 実装済み | `main.py:91` |
| F-8 | `GET /status` で本日の記録と統計を取得できる | ✅ 実装済み | `main.py:97-107` |
| F-9 | Twitter認証情報が未設定の場合はドライラン（ツイートせずログだけ出す）で動作する | ❌ **バグあり** | 後述「バグ #1」参照 |
| F-10 | 1時間ごとに定期チェックを行う | ✅ 実装済み | `main.py:61` |
| F-11 | 起動直後に1回キャッチアップチェックを行う | ✅ 実装済み | `main.py:63-66` |

### 2.2 非機能要件 / Non-Functional Requirements

| # | 要件 | 実装状況 | 備考 |
|---|------|----------|------|
| NF-1 | Dockerで起動できる | ✅ 実装済み | `Dockerfile` / `docker-compose.yml` |
| NF-2 | データはホストの `./data` ディレクトリに永続化される | ✅ 実装済み | `docker-compose.yml:9-10` |
| NF-3 | APIキー等の機密情報は環境変数で管理する | ✅ 実装済み | `twitter.py:5-8`、`.env` 利用 |
| NF-4 | コンテナ停止時に自動再起動する | ✅ 実装済み | `docker-compose.yml` `restart: unless-stopped` |
| NF-5 | 依存ライブラリのバージョンが固定されている | ❌ **未実装** | `requirements.txt` にバージョン指定なし |
| NF-6 | 認証・アクセス制御が実装されている | ❌ **未実装** | `/checkin` エンドポイントは認証なし |
| NF-7 | 自動テスト（ユニットテスト）が存在する | ❌ **未実装** | テストファイルが一切ない |

---

## 3. 発見されたバグ / Bugs Found

### 🐛 バグ #1（重大）: twitter.py — ドライランコードが到達不能 (Dead Code)

**ファイル:** `twitter.py`  
**行数:** 39–43  
**深刻度:** 🔴 重大 (Critical)

**問題のコード:**

```python
def post_failure_tweet(habit_name: str, failures: int, timestamp: str):
    client = get_client()
    # ...メッセージ構築...

    if client:
        try:
            response = client.create_tweet(text=message)
            print(f"Tweet posted successfully: {response}")
            return True          # ← ここで関数が終了する
        except Exception as e:
            print(f"Error posting tweet: {e}")
            return False
        try:                     # ← ここは絶対に実行されない (Dead Code)
            print(f"[DRY RUN - No Twitter API Keys] Would tweet:\n{message}")
        except UnicodeEncodeError:
            ...
        return True              # ← これも到達不能
```

**影響:**  
Twitter認証情報が設定されていない場合（`client is None`）、関数はドライランのログを出力せず、`None` を返します。  
`None` は Python において `False` と等価なため、呼び出し元の `main.py:43-44` では**成功と判定されず**、`mark_tweeted()` が呼ばれません。  
その結果、スケジューラが次に実行されるたびに何度も `update_consecutive_failures` と `get_stats` が呼ばれてしまいます。

**修正方法:**

```python
def post_failure_tweet(habit_name: str, failures: int, timestamp: str):
    client = get_client()

    message = f"🚨 【報告】{habit_name}の目標を達成できませんでした。\n\n"
    if failures > 1:
        message += f"現在の連続失敗回数: {failures}回 😱\n\n"
    message += f"判定日時: {timestamp}"

    if client:
        try:
            response = client.create_tweet(text=message)
            print(f"Tweet posted successfully: {response}")
            return True
        except Exception as e:
            print(f"Error posting tweet: {e}")
            return False
    else:
        # ドライランモード (Dry-run mode)
        try:
            print(f"[DRY RUN - No Twitter API Keys] Would tweet:\n{message}")
        except UnicodeEncodeError:
            print(f"[DRY RUN - No Twitter API Keys] Would tweet:\n{message}".encode('cp932', errors='replace').decode('cp932'))
        return True
```

---

### 🐛 バグ #2（軽微）: main.py — スケジューラの間隔が粗い

**ファイル:** `main.py`  
**行数:** 61  
**深刻度:** 🟡 軽微 (Minor)

**問題:**  
スケジューラは60分ごとに実行されます。例えばBotが8:30に起動した場合、次の実行は9:30となり、**9:00の締め切りをチェックするのが30分遅れます**。起動直後の5秒後チェックで1回目は補完されますが、以降のチェックサイクルのタイミングはランダムです。

**改善案:**  
間隔を短く（例: 5〜10分）するか、`cron` トリガーで特定時刻（例: 9:05, 23:05）に実行する方が確実です。

```python
# 例: 5分ごとにチェックする場合
scheduler.add_job(check_habits_job, 'interval', minutes=5)

# 例: cronで特定時刻にチェックする場合
scheduler.add_job(check_habits_job, 'cron', hour=9, minute=5)
scheduler.add_job(check_habits_job, 'cron', hour=23, minute=5)
```

---

### 🐛 バグ #3（中程度）: database.py — 例外時のDB接続リーク

**ファイル:** `database.py`  
**全関数**  
**深刻度:** 🟠 中程度 (Moderate)

**問題:**  
DB接続を `conn = get_connection()` で取得した後、例外が発生すると `conn.close()` が呼ばれずに接続がリークします。  
SQLiteの場合、ファイルロックの問題は起きにくいですが、より堅牢にするためコンテキストマネージャを使うべきです。

**改善案:**

```python
# 現在のコード (問題あり)
def get_stats():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM user_stats WHERE id = 1')
    row = c.fetchone()
    conn.close()                # 例外が起きたらここに到達しない
    return dict(row) if row else {...}

# 修正後 (コンテキストマネージャを使用)
def get_stats():
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM user_stats WHERE id = 1')
        row = c.fetchone()
    return dict(row) if row else {...}
```

ただし `sqlite3.connect()` が返すオブジェクトはコンテキストマネージャとして使用できますが、`conn.close()` は自動では呼ばれないため、`contextlib.closing` の利用が推奨されます。

---

## 4. その他の改善提案 / Other Recommendations

### 4.1 requirements.txt — バージョン未固定

**現状:**
```
fastapi
uvicorn
tweepy
apscheduler
pydantic
```

**問題:** ライブラリのバージョンが固定されていないため、将来の依存ライブラリのアップデートで予期しない破壊的変更が入る可能性があります。

**改善案:** `pip freeze > requirements.txt` でバージョンを固定する、または手動で指定する。
```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
tweepy>=4.14.0
apscheduler>=3.10.0
pydantic>=2.0.0
```

---

### 4.2 /checkin エンドポイント — 認証機能なし

**問題:** `/checkin` は誰でもアクセス可能なオープンなエンドポイントです。悪意のある第三者が偽のチェックイン記録を送信したり、失敗ツイートを防いだりすることができます。

**改善案:** シンプルな認証（APIキーやHTTP Bearer Token）を追加することを推奨します。

```python
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Security

security = HTTPBearer()
SECRET_TOKEN = os.getenv("CHECKIN_SECRET_TOKEN")

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/checkin")
def checkin(payload: CheckinPayload, _: None = Depends(verify_token)):
    ...
```

---

### 4.3 タイムゾーン — 未指定

**問題:** `datetime.now()` はサーバーのローカルタイムゾーンに依存します。DockerコンテナのデフォルトタイムゾーンはUTC（協定世界時）であるため、Docker環境で動かした場合、締め切り時刻の判定がJSTより9時間ずれます。

**改善案:**
```python
# docker-compose.yml に追加
environment:
  - TZ=Asia/Tokyo

# または main.py でタイムゾーンを明示
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("Asia/Tokyo"))
```

---

### 4.4 テストがない

**問題:** テストファイルが存在しません。将来的なコード変更時にリグレッション（既存機能の破損）を検出できません。

**改善案:** `pytest` を使用した最低限のユニットテストを追加することを推奨します。特に以下のロジックはテストする価値があります:
- `database.py` の各関数
- `main.py` の `check_habits_job` ロジック
- `twitter.py` の `post_failure_tweet` のドライランモード

---

## 5. 総評 / Summary

| カテゴリ | 評価 | コメント |
|----------|------|---------|
| 機能実装 | ★★★★☆ | 主要機能はほぼ実装されているが、ドライランバグ（バグ#1）は修正必須 |
| コード品質 | ★★★☆☆ | 全体的に読みやすいが、DB接続管理とエラーハンドリングに改善余地あり |
| 安全性・セキュリティ | ★★☆☆☆ | 認証なし・バージョン未固定など、本番運用前に要対応 |
| テスト | ★☆☆☆☆ | テストが一切ない。最低限のユニットテスト追加を強く推奨 |
| ドキュメント | ★★★★★ | README.mdは非常に丁寧で分かりやすく、初心者にも優しい |

### 優先度別アクション / Actions by Priority

| 優先度 | 対応内容 |
|--------|---------|
| 🔴 今すぐ対応 | **バグ #1** `twitter.py` のドライランのデッドコードを修正する |
| 🟠 早めに対応 | **バグ #3** DB接続のリーク対策（`try/finally` またはコンテキストマネージャ）|
| 🟠 早めに対応 | `docker-compose.yml` に `TZ=Asia/Tokyo` を追加してタイムゾーンを明示する |
| 🟡 余裕があれば | **バグ #2** スケジューラの実行間隔を短くするか `cron` トリガーへ変更する |
| 🟡 余裕があれば | `requirements.txt` のバージョンを固定する |
| 🟢 将来的に | `/checkin` エンドポイントに認証機能を追加する |
| 🟢 将来的に | `pytest` を使ったユニットテストを追加する |

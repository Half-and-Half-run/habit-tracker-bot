import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
import database
import twitter
import line

# 各習慣の締め切り時刻（深夜0時からの経過分数で管理）
# "wake"（起床） -> 09:00（540分）
# "bath"（入浴） -> 23:00（1380分）
DEADLINES = {
    "wake": 9 * 60,  # 9:00 -> 深夜0時から540分後
    "bath": 23 * 60  # 23:00 -> 深夜0時から1380分後
}

# /checkin エンドポイントへのリクエストボディの型定義
# action: "wake"（起床）または "bath"（入浴）
# timestamp: 任意。省略した場合はサーバー現在時刻を使用
class CheckinPayload(BaseModel):
    action: str
    timestamp: Optional[str] = None

# バックグラウンドで定期的にジョブを実行するスケジューラ
scheduler = BackgroundScheduler()

def check_habits_job():
    """締め切り超過チェックジョブ（1時間ごとに自動実行される）
    
    現在時刻が各習慣の締め切りを過ぎており、かつまだ記録されていない場合に
    連続失敗回数を更新してTwitterに失敗をツイートする。
    ツイート済みフラグにより、同じ日に二重ツイートされることはない。
    """
    now = datetime.now()
    today_str = now.date().isoformat()
    # 現在時刻を「深夜0時からの経過分数」に変換して締め切りと比較する
    current_minutes = now.hour * 60 + now.minute
    
    # 今日の記録がDBになければ自動で作成する
    record = database.get_today_record(today_str)
    
    # --- 起床チェック ---
    if current_minutes >= DEADLINES["wake"]:
        # 締め切りを過ぎており、まだ記録がなく、ツイートもしていない場合
        if record["wake_time"] is None and record["wake_failed_tweeted"] == 0:
            # 連続失敗カウントを+1してツイートする
            database.update_consecutive_failures("wake", failed=True)
            stats = database.get_stats()
            # "wake" IDを渡して expressive なメッセージをトリガーする
            twitter.post_failure_tweet("wake", stats["wake_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            # LINE通知を送る
            line.post_failure_notification("wake", stats["wake_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            database.mark_tweeted("wake", today_str)
                
    # --- 入浴チェック ---
    if current_minutes >= DEADLINES["bath"]:
        # 締め切りを過ぎており、まだ記録がなく、ツイートもしていない場合
        if record["bath_time"] is None and record["bath_failed_tweeted"] == 0:
            # 連続失敗カウントを+1してツイートする
            database.update_consecutive_failures("bath", failed=True)
            stats = database.get_stats()
            # "bath" IDを渡して expressive なメッセージをトリガーする
            twitter.post_failure_tweet("bath", stats["bath_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            # LINE通知を送る
            line.post_failure_notification("bath", stats["bath_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            database.mark_tweeted("bath", today_str)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリ起動・停止時の処理（FastAPIのライフサイクル管理）"""
    # アプリ起動時にDBを初期化する（テーブルがなければ作成する）
    database.init_db()
    
    # スケジューラに定期ジョブを登録する（5分ごとに締め切りチェックを実行）
    scheduler.add_job(check_habits_job, 'interval', minutes=5)
    
    # サーバー起動直後（5秒後）にも一度チェックする
    # → オフライン中に締め切りを過ぎていた場合のキャッチアップ用
    from datetime import timedelta
    run_date = datetime.now() + timedelta(seconds=5)
    scheduler.add_job(check_habits_job, 'date', run_date=run_date)
    
    scheduler.start()
    print("バックグラウンドスケジューラを起動しました。")
    
    yield  # ← アプリが動作中の間ここで待機する
    
    # アプリ停止時にスケジューラを終了する
    scheduler.shutdown()
    print("バックグラウンドスケジューラを停止しました。")

app = FastAPI(lifespan=lifespan, title="Habit Tracker Webhook Bot")

@app.post("/checkin")
def checkin(payload: CheckinPayload):
    """習慣の達成を記録するエンドポイント
    
    スマホのショートカットやIFTTTなどからWebhookで呼び出す。
    同じ習慣を同じ日に2回送っても無視される（冪等性あり）。
    """
    # action が "wake" または "bath" 以外の場合はエラーを返す
    if payload.action not in ["wake", "bath"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'wake' or 'bath'.")
    
    # timestamp が省略された場合はサーバーの現在時刻を使う
    timestamp = payload.timestamp or datetime.now().isoformat()
    
    # DBに記録する（既に今日の記録がある場合は更新されない）
    updated = database.record_action(payload.action, timestamp)
    
        # 初回の記録成功 → 連続失敗カウントを0にリセットする
        database.update_consecutive_failures(payload.action, failed=False)
        # 達成をお祝いツイート/LINE通知する
        twitter.post_success_tweet(payload.action, timestamp)
        line.post_success_notification(payload.action, timestamp)
        return {"status": "success", "message": f"{payload.action} recorded successfully at {timestamp}."}
    else:
        # 今日はすでに記録済み → 何もしない
        return {"status": "ignored", "message": f"{payload.action} already recorded for today."}

@app.get("/status")
def status():
    """現在の状態を確認するエンドポイント（デバッグ・動作確認用）
    
    今日のチェックイン記録と連続失敗統計、締め切り設定を返す。
    """
    today_str = date.today().isoformat()
    record = database.get_today_record(today_str)
    stats = database.get_stats()
    return {
        "today_record": record,
        "stats": stats,
        "deadlines_minutes_from_midnight": DEADLINES
    }

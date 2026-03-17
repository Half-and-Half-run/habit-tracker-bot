import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
import database
import twitter
import line

# 各習慣の締め切り時刻（深夜0時からの経過分数）
DEADLINES = {
    "wake": 9 * 60,  # 09:00
    "bath": 23 * 60  # 23:00
}

class CheckinPayload(BaseModel):
    user_id: int  # 内部データベースのユーザーID 
    action: str
    timestamp: Optional[str] = None

scheduler = BackgroundScheduler()

def check_habits_job():
    """全ユーザーの習慣をチェックする定期ジョブ"""
    now = datetime.now()
    today_str = now.date().isoformat()
    current_minutes = now.hour * 60 + now.minute
    
    # 登録されている全ユーザーを取得
    users = database.get_all_users()
    
    for user in users:
        user_id = user['id']
        line_user_id = user['line_user_id']
        record = database.get_today_record(user_id, today_str)
        
        # --- 起床チェック ---
        if current_minutes >= DEADLINES["wake"]:
            if record["wake_time"] is None and record["wake_failed_tweeted"] == 0:
                database.update_consecutive_failures(user_id, "wake", failed=True)
                stats = database.get_stats(user_id)
                # Twitter への汎用投稿（管理アカウント用など）
                twitter.post_failure_tweet("wake", stats["wake_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
                # 個別の LINE 通知
                line.post_failure_notification(line_user_id, "wake", stats["wake_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
                database.mark_tweeted(user_id, "wake", today_str)
                    
        # --- 入浴チェック ---
        if current_minutes >= DEADLINES["bath"]:
            if record["bath_time"] is None and record["bath_failed_tweeted"] == 0:
                database.update_consecutive_failures(user_id, "bath", failed=True)
                stats = database.get_stats(user_id)
                twitter.post_failure_tweet("bath", stats["bath_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
                line.post_failure_notification(line_user_id, "bath", stats["bath_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
                database.mark_tweeted(user_id, "bath", today_str)

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler.add_job(check_habits_job, 'interval', minutes=5)
    scheduler.start()
    print("Multi-User Scheduler Started.")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="Multi-User Habit Tracker")

@app.post("/callback")
async def line_webhook(request: Request):
    """LINE Messaging API からの入力を受け取る Webhook エンドポイント"""
    body = await request.json()
    events = body.get("events", [])
    for event in events:
        # ユーザーIDを取得してデータベースに登録/取得
        source = event.get("source", {})
        line_user_id = source.get("userId")
        if line_user_id:
            user_id = database.get_or_create_user(line_user_id)
            print(f"User registered/detected: {user_id} (LINE: {line_user_id[:8]}...)")
            
            # フォローイベント（友達追加）への簡単な返信メッセージ
            if event.get("type") == "follow":
                print("Follow event detected.")
                # 本来はここで「登録完了！」などのメッセージを返信できる
    return {"status": "ok"}

@app.post("/checkin")
def checkin(payload: CheckinPayload):
    """習慣の達成を記録する。"""
    if payload.action not in ["wake", "bath"]:
        raise HTTPException(status_code=400, detail="Invalid action.")
    
    user_id = payload.user_id
    timestamp = payload.timestamp or datetime.now().isoformat()
    
    # ユーザーのLINE IDを取得（お祝い送信用）
    users = database.get_all_users()
    user_data = next((u for u in users if u['id'] == user_id), None)
    line_user_id = user_data['line_user_id'] if user_data else None

    # DBに記録
    updated = database.record_action(user_id, payload.action, timestamp)
    
    if updated:
        database.update_consecutive_failures(user_id, payload.action, failed=False)
        twitter.post_success_tweet(payload.action, timestamp)
        if line_user_id:
            line.post_success_notification(line_user_id, payload.action, timestamp)
        return {"status": "success", "message": f"{payload.action} recorded."}
    else:
        return {"status": "ignored", "message": "Already recorded."}

@app.get("/status/{user_id}")
def status(user_id: int):
    """特定ユーザーの状態を確認する。"""
    today_str = date.today().isoformat()
    record = database.get_today_record(user_id, today_str)
    stats = database.get_stats(user_id)
    return {
        "user_id": user_id,
        "today_record": record,
        "stats": stats
    }

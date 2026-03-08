import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
import database
import twitter

# Deadlines
# "wake" -> 09:00
# "bath" -> 23:00
DEADLINES = {
    "wake": 9 * 60, # 9:00 -> 540 minutes from midnight
    "bath": 23 * 60 # 23:00 -> 1380 minutes from midnight
}

class CheckinPayload(BaseModel):
    action: str
    timestamp: Optional[str] = None

scheduler = BackgroundScheduler()

def check_habits_job():
    now = datetime.now()
    today_str = now.date().isoformat()
    current_minutes = now.hour * 60 + now.minute
    
    # Ensure DB record exists for today
    record = database.get_today_record(today_str)
    
    # Check Wake status
    if current_minutes >= DEADLINES["wake"]:
        # Time passed deadline
        if record["wake_time"] is None and record["wake_failed_tweeted"] == 0:
            # Failed and hasn't been tweeted yet!
            database.update_consecutive_failures("wake", failed=True)
            stats = database.get_stats()
            success = twitter.post_failure_tweet("起床(朝9時)", stats["wake_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            if success:
                database.mark_tweeted("wake", today_str)
                
    # Check Bath status
    if current_minutes >= DEADLINES["bath"]:
        if record["bath_time"] is None and record["bath_failed_tweeted"] == 0:
            database.update_consecutive_failures("bath", failed=True)
            stats = database.get_stats()
            success = twitter.post_failure_tweet("入浴(夜23時)", stats["bath_consecutive_failures"], now.strftime("%Y-%m-%d %H:%M:%S"))
            if success:
                database.mark_tweeted("bath", today_str)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    database.init_db()
    
    # Start Scheduler
    # Run the check job every hour
    scheduler.add_job(check_habits_job, 'interval', minutes=60)
    
    # Do an initial check 5 seconds after startup just to catch up on anything missed while offline
    from datetime import timedelta
    run_date = datetime.now() + timedelta(seconds=5)
    scheduler.add_job(check_habits_job, 'date', run_date=run_date)
    
    scheduler.start()
    print("Background scheduler started.")
    
    yield
    
    # Shutdown Scheduler on stop
    scheduler.shutdown()
    print("Background scheduler stopped.")

app = FastAPI(lifespan=lifespan, title="Habit Tracker Webhook Bot")

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/checkin")
def checkin(payload: CheckinPayload):
    if payload.action not in ["wake", "bath"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'wake' or 'bath'.")
    
    timestamp = payload.timestamp or datetime.now().isoformat()
    
    # Record the action in DB (only updates if not already recorded today)
    updated = database.record_action(payload.action, timestamp)
    
    if updated:
        # User checked in today for the first time, reset their consecutive failures for this habit
        database.update_consecutive_failures(payload.action, failed=False)
        return {"status": "success", "message": f"{payload.action} recorded successfully at {timestamp}."}
    else:
        # Either duplicate or checkin after a failure has been fully recorded (but still duplicated)
        return {"status": "ignored", "message": f"{payload.action} already recorded for today."}

@app.get("/status")
def status():
    # Helper endpoint to view the current status
    today_str = date.today().isoformat()
    record = database.get_today_record(today_str)
    stats = database.get_stats()
    return {
        "today_record": record,
        "stats": stats,
        "deadlines_minutes_from_midnight": DEADLINES
    }

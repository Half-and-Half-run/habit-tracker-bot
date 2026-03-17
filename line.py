import os
import requests
import json

# LINE Messaging API の認証情報を環境変数から読み込む
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_push(message: str):
    """Common LINE push notification logic."""
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("--- [LINE Dry Run] ---")
        print(f"To: {LINE_USER_ID if LINE_USER_ID else 'UNDEFINED'}")
        # Use simple ASCII print for dry-run message
        try:
            print(f"Message: {message}")
        except UnicodeEncodeError:
            print(f"Message: {message.encode('ascii', errors='replace').decode('ascii')}")
        print("----------------------")
        return True

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        if response.status_code == 200:
            print("LINE push success.")
            return True
        else:
            print(f"LINE push failed (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"LINE push error: {e}")
        return False

def post_failure_notification(habit_id: str, failures: int, timestamp: str):
    """習慣の失敗をLINEに通知する。"""
    if habit_id == "wake":
        habit_display = "Kishou(9AM)"
        status_msg = "!!! Nido-ne Shitemasu !!!"
    else:
        habit_display = "Nyuuyoku(11PM)"
        status_msg = "!!! Ofuro Haitte naidesu !!!"
    
    message = f"{status_msg}\n\n[Warning] {habit_display} mission failed.\n"
    if failures > 1:
        message += f"Consecutive failures: {failures}\n"
    
    message += f"\nTime: {timestamp}"
    return send_line_push(message)

def post_success_notification(habit_id: str, timestamp: str):
    """習慣の達成をLINEでお祝い通知する。"""
    if habit_id == "wake":
        status_msg = "Good Morning! Wake up mission accomplished!"
    else:
        status_msg = "Bath mission accomplished!"
    
    message = f"{status_msg}\n\nGreat job!\nTime: {timestamp}"
    return send_line_push(message)

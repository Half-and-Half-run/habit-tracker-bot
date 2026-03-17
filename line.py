import os
import requests
import json

# LINE Messaging API の認証情報を環境変数から読み込む
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

def send_line_push(line_user_id: str, message: str):
    """LINE Messaging API を使って指定したユーザー宛にプッシュ通知を送る。
    
    line_user_id が UNDEFINED または認証情報がない場合はドライラン（ログ出力のみ）を行う。
    """
    if not LINE_CHANNEL_ACCESS_TOKEN or not line_user_id or line_user_id == "UNDEFINED":
        print("--- [LINE Dry Run] ---")
        print(f"To: {line_user_id or 'UNDEFINED'}")
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
        "to": line_user_id,
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
            print(f"LINE push success to {line_user_id[:8]}...")
            return True
        else:
            print(f"LINE push failed (Status: {response.status_code}) to {line_user_id[:8]}...")
            return False
    except Exception as e:
        print(f"LINE push error: {e}")
        return False

def post_failure_notification(line_user_id: str, habit_id: str, failures: int, timestamp: str):
    """習慣の失敗を個別のLINEユーザーに通知する。"""
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
    return send_line_push(line_user_id, message)

def post_success_notification(line_user_id: str, habit_id: str, timestamp: str):
    """習慣の達成を個別のLINEユーザーにお祝い通知する。"""
    if habit_id == "wake":
        status_msg = "Good Morning! Wake up mission accomplished!"
    else:
        status_msg = "Bath mission accomplished!"
    
    message = f"{status_msg}\n\nGreat job!\nTime: {timestamp}"
    return send_line_push(line_user_id, message)

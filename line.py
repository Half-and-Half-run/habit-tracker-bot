import os
import requests
import json

# LINE Messaging API の認証情報を環境変数から読み込む
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

def send_line_push(message: str):
    """LINE Messaging API を使って自分宛にプッシュ通知を送る。
    
    認証情報がない場合はドライラン（ログ出力のみ）を行う。
    """
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("--- [LINE Dry Run] ---")
        print(f"To: {LINE_USER_ID or 'UNDEFINED'}")
        print(f"Message: {message}")
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
            print("LINEプッシュ通知の送信に成功しました。")
            return True
        else:
            print(f"LINEプッシュ通知の送信に失敗しました (Status: {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"LINEプッシュ通知送信中にエラーが発生しました: {e}")
        return False

def post_failure_notification(habit_id: str, failures: int, timestamp: str):
    """習慣の失敗をLINEに通知する。"""
    if habit_id == "wake":
        habit_display = "起床(朝9時)"
        status_msg = "🚨 二度寝してます！ 🚨"
    else:
        habit_display = "入浴(夜23時)"
        status_msg = "🚨 まだお風呂入ってないです！ 🚨"
    
    message = f"{status_msg}\n\n【警告】{habit_display}の目標未達です。\n"
    if failures > 1:
        message += f"連続失敗: {failures}回目です...😱\n"
    
    message += f"\n判定日時: {timestamp}"
    return send_line_push(message)

def post_success_notification(habit_id: str, timestamp: str):
    """習慣の達成をLINEでお祝い通知する。"""
    if habit_id == "wake":
        status_msg = "🌞 おはようございます！起床ミッション達成！"
    else:
        status_msg = "🛁 お風呂ミッション達成！お疲れ様でした。"
    
    message = f"{status_msg}\n\n素晴らしい継続です！✨\n完了日時: {timestamp}"
    return send_line_push(message)

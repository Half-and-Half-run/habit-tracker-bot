import tweepy
import os

# Twitter API の認証情報を環境変数から読み込む
# .env ファイルまたはホスト環境の環境変数に設定しておく
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def get_client():
    """Twitter API v2 のクライアントを返す。
    
    認証情報が1つでも未設定の場合はドライランモードとして None を返す。
    """
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        print("警告: Twitter の認証情報が設定されていません。ドライランモードで動作します。")
        return None
    
    return tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )

def post_failure_tweet(habit_id: str, failures: int, timestamp: str):
    """習慣の失敗をTwitterにツイートする。"""
    client = get_client()

    if habit_id == "wake":
        habit_display = "Kishou(9AM)"
        status_msg = "!!! Nido-ne Shitemasu !!!" # 二度寝してます
    else:
        habit_display = "Nyuuyoku(11PM)"
        status_msg = "!!! Ofuro Haitte naidesu !!!" # お風呂入ってないです
    
    message = f"{status_msg}\n\n[Report] {habit_display} mission failed.\n"
    if failures > 1:
        message += f"Consecutive failures: {failures}\n"
        
    message += f"Time: {timestamp}"
    
    return _send_tweet(client, message)

def post_success_tweet(habit_id: str, timestamp: str):
    """習慣の達成をTwitterでお祝いツイートする。"""
    client = get_client()

    if habit_id == "wake":
        status_msg = "Good Morning! Wake up mission accomplished!"
    else:
        status_msg = "Bath mission accomplished!"
    
    message = f"{status_msg}\n\nGreat job!\nTime: {timestamp}"
    
    return _send_tweet(client, message)

def _send_tweet(client, message):
    """Common tweet sending logic."""
    # Simplified dry-run check
    is_dry_run = True
    if client and hasattr(client, 'consumer_key') and client.consumer_key:
        is_dry_run = False

    if not is_dry_run:
        try:
            response = client.create_tweet(text=message)
            print(f"Tweet success: {response}")
            return True
        except Exception as e:
            print(f"Tweet failed: {e}")
            return False
    else:
        print(f"[Dry Run] Message:\n{message}")
        return True

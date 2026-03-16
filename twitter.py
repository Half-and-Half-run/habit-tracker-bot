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
    """習慣の失敗をTwitterにツイートする。
    
    Args:
        habit_id: 習慣ID ("wake" または "bath")
        failures: 現在の連続失敗回数
        timestamp: 判定日時の文字列
    
    Returns:
        True: ツイート成功
    """
    client = get_client()

    # ユーザー指定の臨場感のあるメッセージ
    if habit_id == "wake":
        habit_display = "起床(朝9時)"
        status_msg = "🚨 🚨 🚨 二度寝してます！"
    else:
        habit_id = "bath"
        habit_display = "入浴(夜23時)"
        status_msg = "🚨 🚨 🚨 まだお風呂入ってないです！"
    
    # ツイート本文を組み立てる
    message = f"{status_msg}\n\n【報告】{habit_display}の目標を達成できませんでした。\n\n"
    if failures > 1:
        message += f"現在の連続失敗回数: {failures}回 😱\n\n"
        
    message += f"判定日時: {timestamp}"
    
    return _send_tweet(client, message)

def post_success_tweet(habit_id: str, timestamp: str):
    """習慣の達成をTwitterでお祝いツイートする。
    
    Args:
        habit_id: 習慣ID ("wake" または "bath")
        timestamp: 達成日時の文字列
    """
    client = get_client()

    if habit_id == "wake":
        status_msg = "🌞 おはようございます！起床目標を達成しました！"
    else:
        status_msg = "🛁 お風呂に入りました！今夜のミッション完了です！"
    
    message = f"{status_msg}\n\n今日も一歩前進です！✨\n達成日時: {timestamp}"
    
    return _send_tweet(client, message)

def _send_tweet(client, message):
    """共通のツイート送信処理"""
    if client:
        try:
            response = client.create_tweet(text=message)
            print(f"ツイートに成功しました: {response}")
            return True
        except Exception as e:
            print(f"ツイートに失敗しました: {e}")
            return False
    else:
        try:
            print(f"[ドライラン] ツイート予定内容:\n{message}")
        except UnicodeEncodeError:
            # Windowsのコマンドプロンプト等で絵文字が表示できない場合のフォールバック
            print(f"[ドライラン] ツイート予定内容:\n{message.encode('cp932', errors='replace').decode('cp932')}")
        return True

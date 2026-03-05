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

def post_failure_tweet(habit_name: str, failures: int, timestamp: str):
    """習慣の失敗をTwitterにツイートする。
    
    Args:
        habit_name: 習慣名（例: "起床(朝9時)"）
        failures: 現在の連続失敗回数
        timestamp: 判定日時の文字列
    
    Returns:
        True: ツイート成功（またはドライランで正常処理）
        False: ツイートに失敗した場合
    """
    client = get_client()
    
    # ツイート本文を組み立てる
    message = f"🚨 【報告】{habit_name}の目標を達成できませんでした。\n\n"
    if failures > 1:
        # 連続失敗が2回以上の場合はその回数も追加する
        message += f"現在の連続失敗回数: {failures}回 😱\n\n"
        
    message += f"判定日時: {timestamp}"
    
    if client:
        # 認証情報あり → 実際にツイートする
        try:
            response = client.create_tweet(text=message)
            print(f"ツイートに成功しました: {response}")
            return True
        except Exception as e:
            print(f"ツイートに失敗しました: {e}")
            return False
    else:
        # 認証情報なし → ドライランモード（ツイートせずにログだけ出す）
        try:
            print(f"[ドライラン - Twitter API キー未設定] ツイート予定内容:\n{message}")
        except UnicodeEncodeError:
            # Windows環境でUnicode文字を表示できない場合の代替処理
            print(f"[ドライラン - Twitter API キー未設定] ツイート予定内容:\n{message}".encode('cp932', errors='replace').decode('cp932'))
        return True

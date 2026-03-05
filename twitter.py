import tweepy
import os

# Keys from environment variables
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

def get_client():
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        print("WARNING: Twitter credentials not fully set. Running in dry-run mode.")
        return None
    
    return tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET
    )

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
        try:
            print(f"[DRY RUN - No Twitter API Keys] Would tweet:\n{message}")
        except UnicodeEncodeError:
            print(f"[DRY RUN - No Twitter API Keys] Would tweet:\n{message}".encode('cp932', errors='replace').decode('cp932'))
        return True

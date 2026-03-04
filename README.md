# 習慣化トラッキングBot (Habit Tracker Webhook Bot)

毎日やること（起床や入浴など）を記録し、もし設定した時間までに完了できなかった場合、自動でTwitterに「失敗しました」とツイートするBotです。
Google Antigravity（AIアシスタント）を使って作られたこのプロジェクトは、AIやプログラミングに初めて触れる方でも簡単に動かせるように丁寧に解説しています。

## 🌟 できること
- **素早い記録**: `/checkin` というURLにアクセス（Webhookを送信）するだけで習慣を記録できます。
- **自動ツイート**: 締め切り時間を過ぎても記録がないと、自動的にTwitterへ警告をツイートします。
- **簡単なデータ保存**: データベース（SQLite）を使って、日々の記録や失敗回数を手軽に保存します。
- **定期チェック**: 何もしなくても、Botが1時間に1回裏側で自動的にチェックしてくれます。

---

## 🛠 準備するもの
ご自身のパソコンで動かすには、**Python 3.11以上** が必要です。

### 1. プロジェクトの準備
このプロジェクトのフォルダを開きます。

### 2. 必要な部品（ライブラリ）のインストール
ターミナル（またはコマンドプロンプト／PowerShell）を開き、以下のコマンドを入力して実行（Enter）します。
```bash
pip install -r requirements.txt
```

### 3. Twitter APIキーの設定
Twitterと連携するため、環境変数（システムの設定値）にパスワードのようなもの（APIキー）をセットします。
（Dockerを使う場合は、不要です。後述の `.env` ファイルに書くだけでOKです）

**Windows (PowerShell) の場合:**
```powershell
$env:TWITTER_API_KEY="あなたの_api_key"
$env:TWITTER_API_SECRET="あなたの_api_secret"
$env:TWITTER_ACCESS_TOKEN="あなたの_access_token"
$env:TWITTER_ACCESS_TOKEN_SECRET="あなたの_access_token_secret"
```

**Mac / Linux の場合:**
```bash
export TWITTER_API_KEY="あなたの_api_key"
export TWITTER_API_SECRET="あなたの_api_secret"
export TWITTER_ACCESS_TOKEN="あなたの_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="あなたの_access_token_secret"
```

---

## 🚀 起動のしかた（パソコンで直接動かす場合）

さっそくBotを起動してみましょう。ターミナルで以下を入力します。
```bash
python -m uvicorn main:app --reload
```
これでサーバーが `http://127.0.0.1:8000` で動き始めます！

### 外部からアクセスできるようにする（ngrokの利用）
IFTTT、iOSのショートカット機能、TaskerなどのスマホアプリからこのBotに記録（Webhook）を送りたい場合は、外部に公開するURLが必要です。`ngrok` というツールを使うと簡単です。
別のターミナルを開いて、以下を実行します。
```bash
ngrok http 8000
```
すると `https://<ランダム文字>.ngrok-free.app` のようなURLが表示されます。これがあなたのBotの窓口になります！スマホアプリ等からは `https://<ランダム文字>.ngrok-free.app/checkin` に送信するように設定してください。

---

## 🐳 Dockerを使って起動する（おすすめ！）
サーバーに置いてずっと動かしておきたい方や、環境を汚したくない方におすすめの、もっと簡単な方法です。

1. このフォルダの中に `.env` という名前のファイルを作り、用意したTwitterのキーを書き込みます。
   ```env
   TWITTER_API_KEY=あなたのキー
   TWITTER_API_SECRET=あなたのシークレット
   TWITTER_ACCESS_TOKEN=あなたのトークン
   TWITTER_ACCESS_TOKEN_SECRET=あなたのトークンシークレット
   ```
2. 以下のコマンドで起動します！
   ```bash
   docker-compose up -d
   ```
   これでBotが背後で動き続けます。データは自動的に `./data` フォルダに保存されるので、PCを再起動したりしても安心です。

---

## ✅ 動作確認（テストしてみよう）
Botが動いているか、手動でテストすることができます。ターミナルをもう一つ開き、`curl` コマンドを使って通信してみましょう。

**(Mac/Linux/WSL) 「起きたよ（起床）」と記録する**
```bash
curl -X POST http://127.0.0.1:8000/checkin \
     -H "Content-Type: application/json" \
     -d '{"action": "wake"}'
```

**(Windows PowerShell) 「起きたよ（起床）」と記録する**
WindowsのPowerShellの場合はこちらを使ってください：
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/checkin -Method Post -ContentType "application/json" -Body '{"action": "wake"}'
```

**現在のステータスを確認する**
```bash
curl http://127.0.0.1:8000/status
```

少し難しく見えるかもしれませんが、この手順通りに順番にコピー＆ペーストしていけば大丈夫です。まずは「起動のしかた」を見ながら、手元で動かしてみてください！

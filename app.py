from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage
import json, os, requests

# ===== LINE設定 =====
CHANNEL_ACCESS_TOKEN = "v9oIjz8ugck0dRBpZ43O4MY9El4mrqwfK6XgmxSBAbIDr8DH99PLYlnBp6Ml4XqYlPaTyrMkrpx9osdAt3PPra42Zu0q6C5WhjRNxqKcvZdcjS4vT1uMMJH2/1XHtKy5wQT/J9YVuxeK4O7+9JP54QdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "e5fd1ba729102842beaa4f76b075c7c8"

# ===== スプレッドシート設定 =====
API_KEY = "ここにAPIキー"
SHEET_ID = "1eBsL99sUIF9RdihQ5g1QjPPj12pZXPQG"
SHEET_NAME = "2026年度_時間割"

DATA_FILE = "users.json"

app = Flask(__name__)
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== 学校データ =====
SCHOOLS = {
    "石山高校":{
        "1年":["1-1","1-2","1-3","1-4","1-5","1-6","1-7","1-8","1-9"],
        "2年":["2-1","2-2","2-3","2-4","2-5","2-6","2-7","2-8","2-9"],
        "3年":{"3-1","3-2","3-3","3-4","3-5","3-6","3-7","3-8","3-9"}
    }
}

#前に
day_map = {
    "月": "月曜日",
    "火": "火曜日",
    "水": "水曜日",
    "木": "木曜日",
    "金": "金曜日",
}

school_map = {
    "石山高校": "石山"
}

day = day_map.get(day, day)
school = school_map.get(school, school)

# ===== スプレッドシート取得 =====
def get_timetable(school, cls, day):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{SHEET_NAME}?key={API_KEY}"
    
    res = requests.get(url)
    data = res.json()

    print("=== 全データ ===")
    for row in rows[1:]:
        print(row)

    print("検索条件:", school, cls, day)

    rows = data.get("values", [])
    if not rows:
        return None

    header = rows[0]

    for row in rows[1:]:
        row_dict = dict(zip(header, row))

        if (
            str(row_dict.get("school","")).strip() == school.strip() and
            str(row_dict.get("class","")).strip() == cls.strip() and
            str(row_dict.get("day","")).strip() == day.strip()
        ):
            return [row_dict.get(str(i), "") for i in range(1, 8)]

    return None

# ===== JSON操作 =====
def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== Flex =====
def button_flex(title, buttons):
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg"},
                *[
                    {
                        "type": "button",
                        "action": {"type": "message", "label": b, "text": b},
                        "style": "primary",
                        "margin": "md"
                    } for b in buttons
                ]
            ]
        }
    }

# ===== Webhook =====
@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature")

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(e)

    return "OK"

# ===== メッセージ処理 =====
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    users = load_users()

    # 時間割
    if text == "時間割":
        if user_id not in users:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="先に個人情報登録してください"))
            return

        flex = button_flex("曜日を選択", ["月", "火", "水", "木", "金"])
        line_bot_api.reply_message(event.reply_token, FlexSendMessage("曜日", flex))
        return

    # 登録
    if text == "個人情報登録":
        flex = button_flex("学校を選択", list(SCHOOLS.keys()))
        line_bot_api.reply_message(event.reply_token, FlexSendMessage("学校", flex))
        return

    # 学校
    if text in SCHOOLS:
        users[user_id] = {"school": text}
        save_users(users)
        flex = button_flex("学年を選択", list(SCHOOLS[text].keys()))
        line_bot_api.reply_message(event.reply_token, FlexSendMessage("学年", flex))
        return

    # 学年
    if user_id in users and "school" in users[user_id]:
        school = users[user_id]["school"]
        if text in SCHOOLS[school]:
            save_users(users)
            flex = button_flex("クラスを選択", SCHOOLS[school][text])
            line_bot_api.reply_message(event.reply_token, FlexSendMessage("クラス", flex))
            return

    # クラス
    if user_id in users and "school" in users[user_id]:
        school = users[user_id]["school"]
        if text in SCHOOLS[school].get("2年", []) or text in SCHOOLS[school].get("1年", []) or text in SCHOOLS[school].get("3年", []):
            users[user_id]["class"] = text
            save_users(users)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="登録が完了しました")
            )
            return

    # 曜日
    if text in ["月","火","水","木","金"]:
        if user_id not in users or "class" not in users[user_id]:
            return

        school = users[user_id]["school"]
        cls = users[user_id]["class"]

        day_map = {
            "月": "月曜日",
            "火": "火曜日",
            "水": "水曜日",
            "木": "木曜日",
            "金": "金曜日",
        }

        day = day_map[text]

        lessons = get_timetable(school, cls, text)

        if not lessons:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="データが見つかりません"))
            return

        msg = f"{cls} {text}曜\n"
        for i, s in enumerate(lessons, 1):
            msg += f"{i}限：{s}\n"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg.strip()))
        return

# ===== 起動 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
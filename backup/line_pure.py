from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

import google.generativeai as genai
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# LINE Bot Config
configuration = Configuration(access_token='kjoDJiMr9t76qcUAy8BkYWVo1+tpP/su3tYLmvUrI6R67nLGarVh8yOTWJJDJzL6L7fJKO/FCL6SKkSoCYWUoQAiPyFeLEklsS/31cEWZZ3lUW9TMD4ZwcqnI+p4+mV3u/Zy4KNR7yyOoBDdtW1/fAdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('fcee06db289c6014ee1d3dd45fdf96b8')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Gemini Config
# genai.configure(api_key="AIzaSyAO3zEB8PxnOdlJty7znQLSeMFcgE9tdiY")
genai.configure(api_key=GEMINI_API_KEY)
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 1024,
    "response_mime_type": "text/plain",
}

@app.get('/hello')
def hello_world():
    return {"hello" : "world"}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature.")
        abort(400)

    return 'OK'

user_sessions = {}
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    reply_text = ""

    if user_message in ['สวัสดี', 'นี่ใคร'] or user_message.startswith('สวัสดี'):
        reply_text = "สวัสดี นี่ต้นเองนะ"
    else:
        reply_text = chat_with_gemini(user_id, user_message)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

user_gemini_sessions = {}

def get_or_create_chat_session(user_id):
    if user_id not in user_gemini_sessions:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=generation_config,
        )
        user_gemini_sessions[user_id] = model.start_chat(history=[])
    return user_gemini_sessions[user_id]


def chat_with_gemini(user_id, user_message):
    chat_session = get_or_create_chat_session(user_id)
    response = chat_session.send_message(user_message)
    print('Gemini Response:', response.text)
    return response.text

if __name__ == "__main__":
    app.run(port=5000)

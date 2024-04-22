import hashlib

from fastapi import FastAPI, Body
from typing import Any
from pydantic import BaseModel
import asyncio
import uvicorn
import orjson
from fastapi import Response

from avito.schema.messenger.methods import SendMessage, ChatRead, PostWebhook
from avito.schema.messenger.models import WebhookMessage, MessageToSend, MessageContent
from bot import HotelBot
from config import NGROK_TUNNEL_URL
import os
import gspread
from avito import Avito
from googlesheets import BookingDataBase
from yandexgpt import YandexGPT

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN = os.getenv("TOKEN", None)
OAuthYandex = os.getenv("OAuthYandex")
IAMYandex = os.getenv("IAMYandex:", None)
ME_ID = 168565395

app = FastAPI()
WEBHOOK_PATH = f"/bot/{TOKEN}/webhook"
WEBHOOK_URL = f"{NGROK_TUNNEL_URL}{WEBHOOK_PATH}"
gspread_account_file = "service_account.json"

avito = Avito(TOKEN, CLIENT_ID, CLIENT_SECRET)
gpt = YandexGPT(folder_id="b1gmokkhlfagg82cirvf")
booking_data_base = BookingDataBase(file_account=gspread_account_file, sheet_name="Бронирование гостиницы Воронеж")
bot = HotelBot(avito=avito, yandexgpt=gpt, booking_data_base=booking_data_base)

handled_webhooks = {}

def generate_webhook_hash(author_id, timestamp, text):
    # Конкатенация значений ключевых полей вебхука
    combined_data = f"{author_id}_{timestamp}_{text}"

    # Хэширование комбинированных данных с использованием SHA-256
    webhook_hash = hashlib.sha256(combined_data.encode()).hexdigest()

    return webhook_hash

def need_to_handle_webhook(webhook_hash):
    if webhook_hash in handled_webhooks:
        print(f"Webhook {webhook_hash} has already been handled. Skipping.")
        return False
    else:
        print(f"Handling webhook {webhook_hash}")
        handled_webhooks[webhook_hash] = True
        return True
@app.on_event("startup")
async def on_startup():
    # Подключаем бота к базе данных sql
    await bot.connect_database()
    # Создаем новый объект авито сдк
    # Проверяем наличие токена, если его нет, получаем его и записываем в переменных системы
    if TOKEN == None:
        token = await avito.init_token_if_needed()
        os.environ["TOKEN"] = token.access_token
    # Получаем токен для YandexGpt
    gpt.init_access_token(oauth_token=OAuthYandex, request_url="https://iam.api.cloud.yandex.net/iam/v1/tokens")
    # ---
    # Проверяем наши вебхуки

    # Удаляем все лишние url
    await avito.unsubscribe_all()

    subscriptions = await avito.get_subscriptions()
    subscriptions = subscriptions.subscriptions
    right_sub = any(subscription.url == WEBHOOK_URL for subscription in subscriptions)
    if not right_sub:
         await avito.set_webhook(WEBHOOK_URL)
    # ---

@app.post(WEBHOOK_PATH)
async def bot_webhook(body = Body()):
    webhook_message = body['payload']['value']
    received_message = WebhookMessage.model_validate(webhook_message, context={"avito": avito})

    # Проверяем полученные данные с вебхука. Необходимо, чтобы сообщение было от пользователя, а нет от нас
    if received_message.author_id != ME_ID and received_message.content.text != None and received_message.read ==  None :
        # webhook_hash = generate_webhook_hash(author_id=received_message.author_id, timestamp=received_message.created, text=received_message.content.text)
        if need_to_handle_webhook(received_message.id):
            #Формируем ответное сообщение
            await bot.process_message(message=received_message)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=False)
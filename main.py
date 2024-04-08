from fastapi import FastAPI, Body
from typing import Any
from pydantic import BaseModel
import asyncio
import uvicorn
import orjson
from fastapi import Response

from avito.schema.messenger.methods import SendMessage, ChatRead, PostWebhook
from avito.schema.messenger.models import WebhookMessage, MessageToSend
from bot import HotelBot
from config import NGROK_TUNNEL_URL
import os
from avito import Avito
from openai import OpenAI

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TOKEN = os.getenv("TOKEN", None)
ME_ID = 168565395

app = FastAPI()
WEBHOOK_PATH = f"/bot/{TOKEN}/webhook"
WEBHOOK_URL = f"{NGROK_TUNNEL_URL}{WEBHOOK_PATH}"
avito = Avito(TOKEN, CLIENT_ID, CLIENT_SECRET)
bot = HotelBot(avito=avito)
@app.on_event("startup")
async def on_startup():
    # Создаем новый объект авито сдк
    # Проверяем наличие токена, если его нет, получаем его и записываем в переменных системы
    if TOKEN == None:
        token = await avito.init_token_if_needed()
        os.environ["TOKEN"] = token.access_token
    # ---
    # Проверяем наши вебхуки
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
    if received_message.author_id != ME_ID:
        # Помечаем сообщение в чате прочитанным
        chat_read = received_message.read_message_chat()
        await avito.read_chat(chat_read)
        #
        #Формируем ответное сообщение
        await bot.process_message(message=received_message)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, debug=True)
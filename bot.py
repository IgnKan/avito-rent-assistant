import json
import os
from avito import Avito
from avito.schema.messenger.methods import SendMessage
from avito.schema.messenger.models import MessageToSend, WebhookMessage
from openai import OpenAI


class HotelBot():
    def __init__(self, avito: Avito, open_ai: OpenAI):
        self.avito = avito
        self.open_ai = open_ai
        self.bot_message: str | None = None

    async def process_message(self, message: WebhookMessage):
        message_text = message.content.text
        message_text = await self.prepare_message(message=message_text)

        user_action = await self.define_user_action(message_text)
        match user_action:
            case "Отстань!":
                self.bot_message = "Хорошо, больше я вас не побеспокою."
            case "Ассистент!":
                self.bot_message = "Я здесь!"
            case "Аренда":
                self.bot_message = "Что вас интересует?"
            case _:
                self.bot_message = "Не понял!"

        await self.avito.send_message(message.answer(self.bot_message))

    async def prepare_message(self, message: str):
        prepared_message = message.strip()
        return prepared_message

    async def define_user_action(self, message_from_user: str):
        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        message_to_openAI = messages['defin_user_action_promt'].format(context=message_from_user)
        responce = self.open_ai.completions.create(
            model="gpt-3.5-turbo",
            prompt=message_to_openAI,
            temperature=0.7
        )
        return responce


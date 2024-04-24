import asyncio
import enum
import json
import pymysql
import gspread
import os
from avito import Avito
from avito.schema.messenger.methods import SendMessage
from avito.schema.messenger.models import MessageToSend, WebhookMessage
from googlesheets import BookingDataBase
from yandexgpt import YandexGPT
from config import host, user, password, db_name
from loguru import logger
from datetime import datetime

from langchain_community.vectorstores import Chroma
from langchain.evaluation import load_evaluator
from langchain_community.embeddings import SentenceTransformerEmbeddings
from rag.RAGGenerator import YandexGptEmbeddingFunction


CHROMA_PATH = "rag/chroma"

class ProfileStatesGroup(enum.Enum):
    chat_begin = 1

    get_rent_date = 6
    confirm_rent_date = 7
    get_rent_people_number = 8
    get_user_contact = 9
    confirm_rent = 10
    waiting_3_days = 11

    user_off_assistant = 20



class HotelBot:
    def __init__(self, avito: Avito, yandexgpt: YandexGPT, booking_data_base: BookingDataBase):
        self.avito = avito
        self.yandexgpt = yandexgpt
        self.booking_data_base = booking_data_base
        self.bot_message: str | None = "Не могу понять, что вы хотите. Попробуйте сформулировать иначе"
        self.database_connection = None
        self.message_from_user: str | None = None
        self.user_want_to_activate_assistant = False
        self.was_handled = False

        self.embedding_function = None

    def __del__(self):
        self.database_connection.close()

    # Fsm mashine Этот костыль-декоратор нужен чтобы решать выполянть определнное действие пользователя (запускать функцию или нет) взависимости от состояния пользователя и его команды
    def message_handler(command, state=None):
        def inner_decorator(func):
            def wrapped(*args, **kwargs):
                if args[0].was_handled:
                    return wrapped
                else:
                    user_command = kwargs['command']
                    user_state = kwargs['state']
                    user_id = kwargs['user_id']
                    if state:
                        if state != user_state:
                            return
                        elif user_command.find(command) != -1:
                            func(*args, command=user_command, state=user_state, user_id=user_id)
                    elif user_command.find(command) != -1:
                        func(*args, command=user_command, state=user_state, user_id=user_id)

            return wrapped

        return inner_decorator

    async def process_message(self, message: WebhookMessage):
        message_text = message.content.text
        self.message_from_user = message_text
        state = self.get_user_chat_position(user_id=message.author_id)

        logger.debug("User_state - " + state)

        if state == None:
            with open('messages.json', 'r', encoding='utf-8') as file:
                messages = json.load(file)
            self.bot_message = messages['greetings']['welcome_message_for_new_user'].replace('\\n', '\n')
            self.set_user_chat_position(user_id=message.author_id, chat_position=ProfileStatesGroup.chat_begin.name)
            await self.send_bot_message(message_from_webhook=message, read_chat=True)
            return
        else:
            user_action = self.define_user_action(message_from_user=message_text)
            self.start_pooling(command_from_user=user_action, state=state, user_id=message.author_id)
            if state != ProfileStatesGroup.user_off_assistant.name or self.user_want_to_activate_assistant == True:
                await self.send_bot_message(message_from_webhook=message, read_chat=True)
                self.user_want_to_activate_assistant = False
                self.bot_message = "Не могу понять, что вы хотите. Попробуйте сформулировать иначе"
                self.was_handled = False

    @message_handler(state=ProfileStatesGroup.user_off_assistant.name, command='включить ассистента')
    def start_assistant(self, command, state, user_id):
        self.bot_message = "Ассистент активирован!"
        self.set_user_chat_position(user_id=user_id,
                                    chat_position=ProfileStatesGroup.chat_begin.name)
        self.user_want_to_activate_assistant = True
        self.was_handled = True
        return

    @message_handler(command='отключить ассистента')
    def off_assistant(self, command, state, user_id):
        self.bot_message = "Асситент отключен! Чат только с владельцем."
        self.set_user_chat_position(user_id=user_id,
                                    chat_position=ProfileStatesGroup.user_off_assistant.name)
        self.was_handled = True
        return

    @message_handler(command='инструкция к ассистенту')
    def get_assistant_instruction(self, command, state, user_id):

        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        self.bot_message = messages['greetings']['welcome_message_for_new_user'].replace('\\n', '\n')
        self.was_handled = True

        return

    @message_handler(command='сбросить состояние ассистента')
    def reset_asisstent(self, command, state, user_id):
        self.bot_message = "Ассистент сброшен!"
        self.set_user_chat_position(user_id=user_id,
                                    chat_position=ProfileStatesGroup.chat_begin.name)
        self.was_handled = True
        return

    @message_handler(command='создать бронирование', state=ProfileStatesGroup.chat_begin.name)
    def create_new_booking(self, command, state, user_id):
        user_booking = self.booking_data_base.find_user_booking(user_id=str(user_id))

        if user_booking == -1:
            self.bot_message = "Какой период вас интересует?"
            self.set_user_chat_position(user_id=user_id,
                                                    chat_position=ProfileStatesGroup.get_rent_date.name)
        else:
            self.bot_message = "Вы уже оформили бронирование. Сейчас каждый пользователь может иметь только одно бронирование. Ваше бронирование - " + str(user_booking)
        self.was_handled = True
        return

    @message_handler(command='изменить бронирование', state=ProfileStatesGroup.chat_begin.name)
    def manage_booking(self, command, state, user_id):
        user_booking = self.booking_data_base.find_user_booking(user_id=str(user_id))
        if user_booking == -1:
            self.bot_message = "У вас нет бронирования, которое можно изменить. Может быть вы хотите сначала создать бронирование?"
        else:
            self.bot_message = "Ваше бронирование - "+ str(user_booking) + "\nЧто вы хотите изменить?"

    @message_handler(command='удалить бронирование', state=ProfileStatesGroup.chat_begin.name)
    def delete_booking(self, command, state, user_id):
        user_booking = self.booking_data_base.find_user_booking(user_id=str(user_id))
        if user_booking == -1:
            self.bot_message = "У вас нет бронирования, которое можно удалить. Может быть вы хотите сначала создать бронирование?"
        else:
            self.bot_message = "Ваше бронирование - " + str(user_booking) + "\nВы уверены, что хотите его отменить?"

    @message_handler(command="none", state=ProfileStatesGroup.get_rent_date.name)
    def get_rent_date(self, command, state, user_id):
        date = self.define_user_rent_date(message_from_user=self.message_from_user)
        try:
            parsed_date = self.parse_date_range(date_range=date)
            self.bot_message = "Вас интересует период: C {start_date} По {last_date}?".format(start_date = parsed_date["start_date"], last_date = parsed_date["last_date"])
            self.set_user_chat_position(user_id=user_id,
                                    chat_position=ProfileStatesGroup.confirm_rent_date.name)

        except Exception as ex:
            self.bot_message = date

        self.was_handled = True
        return

    @message_handler(command="none", state=ProfileStatesGroup.confirm_rent_date.name)
    def confirm_rent_date(self, command, state, user_id):
        confirm = self.define_user_confirm(message_from_user=self.message_from_user)
        if confirm != '0':
            if confirm.find('да') != -1:
                    self.bot_message = "Сколько будет людей?"
                    self.set_user_chat_position(user_id=user_id, chat_position=ProfileStatesGroup.get_rent_people_number.name)
            if confirm.find('нет') != -1:
                self.bot_message = "Введите нужную вам дату. Если я распознаю ее не правильно введите ее по другому."
                self.set_user_chat_position(user_id=user_id,
                                            chat_position=ProfileStatesGroup.get_rent_date.name)
        else:
            self.bot_message = "Не могу понять ваш ответ. Сформулируйте, точнее"

        self.was_handled = True
        return

    @message_handler(command="none", state=ProfileStatesGroup.get_rent_people_number.name)
    def get_rent_people_number(self, command, state, user_id):
        people_number = self.get_people_number(message_from_user=command)

        try:
            people_number = float(people_number)
            self.bot_message = str(people_number)

        except Exception as ex:
            self.bot_message = people_number



    @message_handler(command="вопрос по бронированию")
    def answer_the_rent_question(self, command, state, user_id):
        answer = self.answer_user_question(message_from_user=self.message_from_user)
        self.bot_message = answer
        self.was_handled = True
        return

    def start_pooling(self, command_from_user, state, user_id):
        self.start_assistant(command=command_from_user, state=state, user_id=user_id)
        self.off_assistant(command=command_from_user, state=state, user_id=user_id)
        self.reset_asisstent(command=command_from_user, state=state, user_id=user_id)

        # Необходимо еще раз проверить состояние бота. Так как клиент мог его сбросить
        user_state = self.get_user_chat_position(user_id=user_id)

        self.delete_booking(command=command_from_user, state=user_state, user_id=user_id)
        self.manage_booking(command=command_from_user, state=user_state, user_id=user_id)

        self.answer_the_rent_question(command=command_from_user, state=user_state, user_id=user_id)
        self.create_new_booking(command=command_from_user, state=user_state, user_id=user_id)
        self.get_rent_date(command='none', state=user_state, user_id=user_id)
        self.confirm_rent_date(command='none', state=user_state, user_id=user_id)
        self.get_assistant_instruction(command=command_from_user, state=user_state, user_id=user_id)

    def parse_date_range(self, date_range: str):
        # Извлекаем даты начала и конца из строки
        start_date, end_date = date_range.split(" по ")

        # Преобразуем даты в объекты datetime
        start_date = start_date.removeprefix("с ")
        start_date = start_date.removeprefix("C ")
        start_date = start_date.removesuffix(" ")
        end_date = end_date.removesuffix(".")

        current_date = datetime.strptime(start_date, '%d-%m-%y').date()
        last_date = datetime.strptime(end_date, '%d-%m-%y').date()

        # Возвращаем список-ключ значение
        return {"start_date": current_date, "last_date": last_date}

    def get_user_chat_position(self, user_id):
        if user_id is not None:
            try:
                with self.database_connection.cursor() as cursor:
                    select_user_chat_position = "SELECT chat_position FROM user_chat_position WHERE user_id = {user_id}".format(
                        user_id=user_id)
                    cursor.execute(select_user_chat_position)
                    rows = cursor.fetchall()

                    return rows[0]['chat_position'] if rows is not None else None
            except Exception as ex:
                logger.error(ex)

    def set_user_chat_position(self, user_id: str, chat_position: str):
        if user_id is not None and chat_position is not None:
            try:
                with self.database_connection.cursor() as cursor:
                    set_user_chat_position = "INSERT INTO user_chat_position (user_id, chat_position) VALUES ({user_id}, '{chat_position}') ON DUPLICATE KEY UPDATE chat_position = '{chat_position}'".format(
                        user_id=user_id, chat_position=chat_position)
                    cursor.execute(set_user_chat_position)
                    self.database_connection.commit()
            except Exception as ex:
                logger.error(ex)

    async def connect_database(self):
        try:
            logger.info("Trying connect to database...")
            connection = pymysql.connect(
                host=host,
                port=3306,
                user=user,
                password=password,
                database=db_name,
                cursorclass=pymysql.cursors.DictCursor
            )
            logger.info("Successfully connected!")
            self.database_connection = connection
        except Exception as ex:
            logger.error("Connection refused...")
            logger.error(ex)

    async def send_bot_message(self, message_from_webhook, read_chat: bool):
        # Чтение чата
        if read_chat:
            chat_read = message_from_webhook.read_message_chat()
            await self.avito.read_chat(chat_read)
        #
        # Отправка сообщения.
        self.bot_message = self.bot_message.replace('\\n', '\n')
        await self.avito.send_message(message_from_webhook.answer(self.bot_message))

    def define_user_action(self, message_from_user: str):
        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        promt = messages['yandex_gpt']['define_user_action_promt']
        message = [
            {
                "role": "system",
                "text": promt
            },
            {
                "role": "user",
                "text": "Сообщение пользователя: " + message_from_user
            }
        ]
        result = self.yandexgpt.make_request(message)

        if result.find("0") != -1:
            result = "None"
        return result.lower()

    def define_user_confirm(self, message_from_user: str):
        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        promt = messages['yandex_gpt']['confirm_user_input']
        message = [
            {
                "role": "system",
                "text": promt
            },
            {
                "role": "user",
                "text": "Сообщение от пользователя:" + message_from_user
            }
        ]
        result = self.yandexgpt.make_request(message)
        return result.lower()

    def define_user_rent_date(self, message_from_user: str):
        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        promt = messages['yandex_gpt']['define_rent_date_promt']
        message = [
            {
                "role": "system",
                "text": promt.format(current_year=datetime.now().year, current_date=datetime.now().date())
            },
            {
                "role": "user",
                "text": "Сообщение пользователя: " + message_from_user
            }
        ]
        result = self.yandexgpt.make_request(message)
        return result.lower()


    def answer_user_question(self, message_from_user: str):
        # Create CLI.

        # Prepare the DB.
        db = Chroma(persist_directory=CHROMA_PATH, embedding_function=self.embedding_function)

        # Search the DB.
        results = db.similarity_search_with_relevance_scores(message_from_user, k=8)
        if len(results) == 0 or results[0][1] < 0.7:
            print("Unable to find matching results.")

        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])

        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        promt = messages['yandex_gpt']['answer_user_question_promt']
        message = [
            {
                "role": "system",
                "text": promt.format(context=context_text)
            },
            {
                "role": "user",
                "text": "Вопрос пользователя: " + message_from_user
            }
        ]
        result = self.yandexgpt.make_request(message)
        return result

    def get_people_number(self, message_from_user: str):

        with open('messages.json', 'r', encoding='utf-8') as file:
            messages = json.load(file)
        promt = messages['yandex_gpt']['get_user_people_number']
        message = [
            {
                "role": "system",
                "text": promt
            },
            {
                "role": "user",
                "text": "Число пользователя: " + message_from_user
            }
        ]
        result = self.yandexgpt.make_request(message)
        return result

    def prepare_message(self, message: str):
        prepared_message = message.strip()
        return prepared_message










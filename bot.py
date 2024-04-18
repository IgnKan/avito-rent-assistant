import asyncio
import enum
import json
import pymysql
import os
from avito import Avito
from avito.schema.messenger.methods import SendMessage
from avito.schema.messenger.models import MessageToSend, WebhookMessage
from yandexgpt import YandexGPT
from config import host, user, password, db_name
from loguru import logger

class ProfileStatesGroup(enum.Enum):
    chat_begin = 1

    get_rent_date = 6
    confirm_rent_date = 7
    get_rent_people_number = 8
    get_user_contact = 9
    confirm_rent = 10
    waiting_3_days_before_invite = 11

    user_off_assistent = 20



class HotelBot:
    def __init__(self, avito: Avito, yandexgpt: YandexGPT):
        self.avito = avito
        self.yandexgpt = yandexgpt
        self.bot_message: str | None = None
        self.database_connection = None
        self.state = None

    def __del__(self):
        self.database_connection.close()
    def message_handler(command, state=None):
        def inner_decorator(f):
            def wraped(*args):
                user_command = args[0]
                user_state = args[1]
                if state:
                    if (state.chat_begin.name != user_state):
                        None
                elif (user_command.find(command) != -1):
                    f()

        return inner_decorator

    def process_message(self, message: WebhookMessage):
        message_text = message.content.text
        state = await self.get_user_chat_position(user_id=message.author_id)

        if state == None:
            with open('messages.json', 'r', encoding='utf-8') as file:
                messages = json.load(file)
            self.bot_message = messages['greetings']['welcome_message_for_new_user'].replace('\\n', '\n')
            await self.set_user_chat_position(user_id=message.author_id, chat_position=ProfileStatesGroup.chat_begin.name)
            await self.send_bot_message(message_from_webhook=message, read_chat=True)
            return
        else:
            message_from_user = await self.define_user_action(message_from_user=message_text)
            await self.start_pooling(message_from_user=message_from_user, state=state, user_id=message.author_id)
            await self.send_bot_message(message_from_webhook=message, read_chat=True)

    def start_pooling(self, message_from_user, state, user_id):
        await self.start_assistent(command=message_from_user, state=state, user_id=user_id)
        await self.off_assisstent(command=message_from_user, state=state, user_id=user_id)

    @message_handler(state=ProfileStatesGroup.user_off_assistent.name, command='Активировать ассистента')
    async def start_assistent(self, command, state, user_id):
            self.bot_message = "Ассистент активирован!"
            await self.set_user_chat_position(user_id=user_id,
                                              chat_position=ProfileStatesGroup.chat_begin.name)

    @message_handler(command='Отключить ассистента')
    async def off_assisstent(self, command, state, user_id):
        self.bot_message = "Асситент отключен! Чат только с владельцем. Включить ассистента команда (\"/assistent_on\") или сообщение по типу: Включить ассистента"
        await self.set_user_chat_position(user_id=user_id,
                                          chat_position=ProfileStatesGroup.user_off_assistent.name)

    @message_handler(command='Сбросить состояние ассистента')
    async def reset_asisstent(self, command, state, user_id):
        self.bot_message = "Ассистент сброшен!"
        await self.set_user_chat_position(user_id=user_id,
                                          chat_position=ProfileStatesGroup.chat_begin.name)

    # async def create_booking(self, commands=['Новое бронирование'], state=ProfileStatesGroup):
    #     if state != ProfileStatesGroup.chat_begin.name:
    #         None
    #     else:
    #         self.bot_message = "Создание нового бронирования: \n Какая дата вас интересует?"
    #         await self.set_user_chat_position(user_id=user_id,
    #                                         chat_position=ProfileStatesGroup.get_rent_date.name)
    # async def get_rent_date(self, message, state=ProfileStatesGroup):
    #     if state != ProfileStatesGroup.get_rent_date.name:
    #         None
    #     else:
    #         rent_date = self.define_user_rent_date(message_from_user=message)
    #         if rent_date:
    #             if rent_date != 0:
    # #                 Валидация введенной даты
    #                 print("Валидация введенной даты")
    #             else:
    #                 print("Дата не ясна")
    #
    #
    #
    #
    # # 1. Проверяем ввел ли пользователь команду. 2. Проверяем состояние чата с пользователем. 3. Обрабатываем все остальное
    # async def process_message(self, message: WebhookMessage):
    #     message_text = message.content.text
    #     state = await self.get_user_chat_position(user_id=message.author_id)
    #
    #     # Проверяем новый ли это пользователь
    #     if state == None:
    #         with open('messages.json', 'r', encoding='utf-8') as file:
    #             messages = json.load(file)
    #         self.bot_message = messages['greetings']['welcome_message_for_new_user'].replace('\\n', '\n')
    #         await self.set_user_chat_position(user_id=message.author_id, chat_position=ProfileStatesGroup.chat_begin.name)
    #         await self.send_bot_message(message_from_webhook=message, read_chat=True)
    #         return
    #
    #     # Если пользователь отключил ассистента в чате
    #     if user_chat_position == ProfileStatesGroup.user_off_assistent.name:
    #         # Мы не помечаем сообщения прочитанными и не пишем ему ничего в ответ, пока он не введет команду для активации ассистента
    #         message_from_user = await self.prepare_message(message_text)
    #         user_want_to_activate_assistent = await self.user_want_to_activate_assistent(message_from_user=message_from_user)
    #         if user_want_to_activate_assistent:
    #             command = "/assistent_on"
    #             await self.process_user_command(command=command, author_id=message.author_id)
    #             await self.send_bot_message(message_from_webhook=message, read_chat=True)
    #             return
    #         else:
    #             return
    #     # Ассистент активен
    #     else:
    #         # Проверяем не хочет ли пользователь отключить ассистента
    #         user_want_to_deactivate_assistent = await self.user_want_to_activate_assistent(message_from_user=message_text)
    #         if user_want_to_deactivate_assistent:
    #             command = "/assistent_off"
    #             await self.process_user_command(command=command, author_id=message.author_id)
    #             await self.send_bot_message(message_from_webhook=message, read_chat=True)
    #             return
    #         # Проверяем не хочет ли пользователь ассистента сбросить
    #         user_want_to_reset_assistent = await self.user_want_to_reset_assistent(message_from_user=message_text)
    #         if user_want_to_reset_assistent:
    #             command = "/res"
    #             await self.process_user_command(command=command, author_id=message.author_id)
    #             await self.send_bot_message(message_from_webhook=message, read_chat=True)
    #             return
    #         # Если другое то
    #         # Проверяем на чем остановился пользователь при общении с ботом
    #         if user_chat_position == ProfileStatesGroup.chat_begin.name:
    #             # Удаляем лишние пробелы из сообщения пользователя
    #             command = await self.prepare_message(message=message_text)
    #             # Обрабатываем команду пользователя
    #             await self.process_user_command(command=command, author_id=message.author_id)
    #             await self.send_bot_message(message_from_webhook=message, read_chat=True)
    #         # Игнорируем любые запросы пользователя пока он не введет дату
    #         elif user_chat_position == ProfileStatesGroup.get_rent_date.name:
    #             user_rent_date = await self.define_user_rent_date(message_from_user=message_text)
    #             if user_rent_date != 0:
    #                 self.bot_message = "Вас интересует период: {period}? Да / Нет".format(period=user_rent_date)
    #                 await self.set_user_chat_position(user_id=message.author_id,
    #                                                   chat_position=ProfileStatesGroup.confirm_rent_date.name)
    #                 self.send_bot_message(message_from_webhook=message, read_chat=True)
    #                 return
    #             else:
    #                 self.bot_message = "Введите интересующий вас переиод точнее, либо по другому. Система не может распознать нужные вам даты"
    #                 self.send_bot_message(message_from_webhook=message, read_chat=True)
    #                 return
    #         elif user_chat_position == ProfileStatesGroup.confirm_rent_date.name:
    #             self.bot_message = "Хорошо, уже проверяю"
    #             self.send_bot_message(message_from_webhook=message, read_chat=True)
    #             return

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



    # async def process_user_command(self, command: str, author_id: str):
    #     match command:            # Если пользователь ввел не команду, то передаем ее на распознавание yandexgpt
    #         case _:
    #             user_action = await self.define_user_action(message_from_user=command)
    #             if user_action.find("Создать бронирование")!= -1:
    #                 self.bot_message = "Создание нового бронирования: \nКакая дата вас интересует?"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.get_rent_date.name)
    #
    #             elif user_action.find("Изменить бронирование")!= -1:
    #                 self.bot_message = "Редактирование бронирования: \nПоиск существующего бронирования..."
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.mod_rent.name)
    #             elif user_action.find("Удалить бронирование")!= -1:
    #                 self.bot_message = "Удалить бронирование: \nПоиск существующего бронирования..."
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.del_rent.name)
    #             elif user_action.find("Условия аренды")!= -1:
    #                 self.bot_message = "Условия аренды:"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.chat_begin.name)
    #             elif user_action.find("Условия проживания")!= -1:
    #                 self.bot_message = "Условия проживания:"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.ask_question.name)
    #             elif user_action.find("Построение маршрута")!= -1:
    #                 self.bot_message = "Построение маршрута: \n Откуда вы поедете?"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.build_route.name)
    #             elif user_action.find("Отключить ассистента")!= -1:
    #                 self.bot_message = "Асситент отключен! Чат только с владельцем. Включить ассистента команда (\"/assistent_on\") или сообщение по типу: Включить ассистента"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.user_off_assistent.name)
    #             elif user_action.find("Включить ассистента")!= -1:
    #                 self.bot_message = "Ассистент активирован!"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.chat_begin.name)
    #             elif user_action.find("Сбросить состояние ассистента")!= -1:
    #                 self.bot_message = "Ассистент сброшен!"
    #                 await self.set_user_chat_position(user_id=author_id,
    #                                                   chat_position=ProfileStatesGroup.chat_begin.name)
    #             else:
    #                 self.bot_message = "Не могу понять, что вы хотите, попробуйте иначе сформулировать запрос."


async def send_bot_message(self, message_from_webhook, read_chat: bool, bot_message: str):
        # Чтение чата
        if read_chat:
            chat_read = message_from_webhook.read_message_chat()
            await self.avito.read_chat(chat_read)
        #
        # Отправка сообщения.
        await self.avito.send_message(message_from_webhook.answer(bot_message))


async def get_user_chat_position(database_connection, user_id: str):
    if user_id is not None:
        try:
            with database_connection.cursor() as cursor:
                select_user_chat_position = "SELECT chat_position FROM user_chat_position WHERE user_id = {user_id}".format(
                    user_id=user_id)
                cursor.execute(select_user_chat_position)
                rows = cursor.fetchall()

                return rows[0]['chat_position'] if rows is not None else None
        except Exception as ex:
            logger.error(ex)

async def set_user_chat_position(database_connection, user_id: str, chat_position: str):
     if user_id is not None and chat_position is not None:
         try:
             with database_connection.cursor() as cursor:
                 set_user_chat_position = "INSERT INTO user_chat_position (user_id, chat_position) VALUES ({user_id}, '{chat_position}') ON DUPLICATE KEY UPDATE chat_position = '{chat_position}'".format(
                     user_id=user_id, chat_position=chat_position)
                 cursor.execute(set_user_chat_position)
                 database_connection.commit()
         except Exception as ex:
             logger.error(ex)

async def define_user_action(yandexgpt, message_from_user: str):
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
            "text": message_from_user
        }
    ]
    user_action = yandexgpt.make_request(message)
    return user_action

async def define_user_rent_date(yandexgpt, message_from_user: str):
     with open('messages.json', 'r', encoding='utf-8') as file:
         messages = json.load(file)
     promt = messages['yandex_gpt']['define_rent_date_promt']
     message = [
         {
             "role": "system",
             "text": promt
         },
         {
             "role": "user",
             "text": message_from_user
         }
     ]
     user_action = yandexgpt.make_request(message)
     return user_action

async def prepare_message(self, message: str):
    prepared_message = message.strip()
    return prepared_message

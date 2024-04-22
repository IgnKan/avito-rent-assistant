import gspread

from bot import ProfileStatesGroup
import googlesheets
from googlesheets import BookingDataBase


def message_handler(command, state=None):
    def inner_decorator(func):
        def wrapped(*args, **kwargs):
            user_command = args[0]
            user_state = args[1]
            if state:
                if state.chat_begin.name != user_state:
                    return
            elif user_command.find(command) != -1:
                func(*args)
        return wrapped
    return inner_decorator

@message_handler(state=ProfileStatesGroup.user_off_assistent.name, command='Активировать ассистента')
def start_assistent(command, state, user_id):
    print("Ассистент активирован!")

def start_pooling(message_from_user, state, user_id):
    start_assistent(message_from_user, state, user_id)

gspread_account_file = "service_account.json"

def test_gs_pred():
    gc = gspread.service_account(gspread_account_file)
    # Open a sheet from a spreadsheet in one go
    wks = gc.open("Бронирование гостиницы Воронеж").sheet1

    # Update a range of cells using the top left corner address\
    values_list = wks.get_all_values()
    empty_indices = [i for i, sublist in enumerate(values_list) if all(x == '' for x in sublist)]
    print(f"Индексы списков с пустыми строками: {empty_indices}")

if __name__ == "__main__":
    booking_data_base = BookingDataBase(file_account=gspread_account_file, sheet_name="Бронирование гостиницы Воронеж")
    booking_data_base.add_booking("19", "29/04/24", "16/05/24", 2, "Gf", "Vk-com")

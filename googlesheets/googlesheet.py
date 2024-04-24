import gspread

# Будем работать с локальной копией "Базы данных" обновлять ее будем по вебхуку если ее изменит владелец.
class BookingDataBase:

    def __init__(self, file_account, sheet_name: str) -> None:
        self.gc = gspread.service_account(file_account)
        self.wks = self.gc.open(sheet_name).sheet1
        self.booking_records = self.wks.get_all_values()

        self.had_change = False

    def add_booking(self, user_id, booking_start_date, booking_last_date, people_number, user_avito_name, user_contact):
        free_row = self.find_free_row()
        if not self.find_user_booking(user_id=user_id):
             self.wks.update([[user_avito_name, booking_start_date, booking_last_date, people_number, user_contact, user_id]], "A" + str(free_row))
        else:
            return -1

    def delete_booking(self, user_id, booking_start_date, booking_last_date):

        self.update_remote_database()
        pass

    def find_free_booking(self, booking_start_date, booking_last_date, people_number):
        pass

    def manage_booking(self, user_id, booking_date, new_booking_date, new_people_number, new_user_contact):
        pass

    def find_user_booking(self, user_id):
        for sublist in self.booking_records:
            if user_id in sublist:
                return sublist
        return None


    def get_all_booking_records(self, ):
        pass

    def update_remote_database(self):
        pass

    # Запись считается пустой, если нет всего
    def find_free_row(self):
        # Получаем все незаполненные строки
        empty_indices = [i for i, sublist in enumerate(self.booking_records) if all(x == '' for x in sublist)]

        return empty_indices[0] + 1


if __name__ == "__main__":
    booking_base = BookingDataBase("../service_account.json", sheet_name="Бронирование гостиницы Воронеж")
    user_booking = booking_base.find_user_booking(user_id = '360445272')
    print(user_booking)
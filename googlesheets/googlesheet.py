import gspread

# Будем работать с локальной копией "Базы данных" обновлять ее будем по вебхуку если ее изменит владелец.
class BookingDataBase:

    def __init__(self, file_account, sheet_name: str) -> None:
        self.gc = gspread.service_account(file_account)
        self.wks = self.gc.open(sheet_name).sheet1
        self.booking_records = self.wks.get_all_values()

        self.had_change = False

    def add_booking(self, user_id, booking_begin_date, booking_end_date, people_number, user_avito_name, user_contact):
        free_row = self.find_free_row()
        if not self.find_booking(user_id=user_id, booking_begin_date=booking_begin_date, booking_end_date=booking_end_date):
             self.wks.update([[user_avito_name, booking_begin_date, booking_end_date, people_number, user_contact, user_id]], "A" + str(free_row))
        else:
            return -1

    def delete_booking(self, user_id, booking_begin_date, booking_end_date):

        self.update_remote_database()
        pass

    def find_free_booking(self, booking_date, people_number):
        pass

    def manage_booking(self, user_id, booking_date, new_booking_date, new_people_number, new_user_contact):
        self.update_remote_database()
        pass

    def find_booking(self, user_id, booking_begin_date, booking_end_date):
        for sublist in self.booking_records:
            if user_id in sublist and booking_begin_date in sublist and booking_end_date in sublist:
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

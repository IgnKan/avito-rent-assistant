from bot import ProfileStatesGroup

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

if __name__ == "__main__":
    start_pooling(message_from_user="sosy hui", state=ProfileStatesGroup.user_off_assistent.name, user_id=5)
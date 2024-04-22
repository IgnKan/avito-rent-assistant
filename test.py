import argparse

import gspread
from langchain_community.vectorstores import Chroma

from bot import ProfileStatesGroup
import googlesheets
from googlesheets import BookingDataBase
from langchain.evaluation import load_evaluator
from langchain_community.embeddings import SentenceTransformerEmbeddings

embedding_function = SentenceTransformerEmbeddings(model_name="paraphrase-multilingual-mpnet-base-v2")

CHROMA_PATH = "rag/chroma"
DATA_PATH = "../docs"

PROMPT_TEMPLATE = """
    Answer the question based only on the following context:

    {context}

    ---

    Answer the question based on the above context: {question}
    """



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

    # Create CLI.
    query_text = "Можно с домашними животными??"

    # Prepare the DB.
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)

    # Search the DB.
    results = db.similarity_search_with_relevance_scores(query_text, k=2)
    if len(results) == 0 or results[0][1] < 0.7:
        print(f"Unable to find matching results.")

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt = PROMPT_TEMPLATE.format(context=context_text, question=query_text)
    print(prompt)

from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain.vectorstores.chroma import Chroma
from chromadb import Documents, EmbeddingFunction, Embeddings
import time
import requests
from loguru import logger

import os
import shutil


class YandexGptEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:

        embeddings = self.embed_documents(input)
        # embed the documents somehow

        return embeddings

    def __init__(self, iam_token=None, folder_id=None, sleep_interval=0.5):
        self.iam_token = iam_token
        self.sleep_interval = sleep_interval
        self.folder_id = folder_id
        self.headers = {'Authorization': 'Bearer ' + self.iam_token, "x-folder-id": self.folder_id}

    def embed_document(self, text):
        j = {
            "model": "general:embedding",
            "embedding_type": "EMBEDDING_TYPE_DOCUMENT",
            "text": text
        }
        res = requests.post("https://llm.api.cloud.yandex.net/llm/v1alpha/embedding",

                            json=j, headers=self.headers)
        vec = res.json()['embedding']
        return vec

    def embed_documents(self, texts):
        res = []
        for x in texts:
            res.append(self.embed_document(x))
            time.sleep(self.sleep_interval)
        return res

    def embed_query(self, text):
        j = {
            "model": "general:embedding",
            "embedding_type": "EMBEDDING_TYPE_QUERY",
            "text": text
        }
        logger.debug("Request [yandexEmbedding]: " + text)
        try:
            res = requests.post("https://llm.api.cloud.yandex.net/llm/v1alpha/embedding",
                                json=j, headers=self.headers)
            vec = res.json()['embedding']
            time.sleep(self.sleep_interval)
            return vec
        except Exception as ex:
            logger.error("Response [yandexEmbeddings]: " + ex.__str__())

    # def init_access_token(self, oauth_token: str, request_url: str) -> None:
    #     if oauth_token:
    #
    #         headers = {
    #             "Content-Type": "application/json"
    #         }
    #
    #         promt = {
    #             "yandexPassportOauthToken": oauth_token
    #         }
    #         try:
    #             response = requests.post(request_url,
    #                                      headers=headers,
    #                                      json=promt)
    #
    #         except requests.RequestException as error:
    #             logger.error(error)
    #         else:
    #             self.iam_token = response.json()["iamToken"]


from chromadb.utils import embedding_functions

# create the open-source embedding function



CHROMA_PATH = "chroma"
DATA_PATH = "../docs"


def main():
    generate_data_store()


def generate_data_store():
    documents = load_documents()
    chunks = split_text(documents)
    save_to_chroma(chunks)


def load_documents():
    loader = DirectoryLoader(DATA_PATH, glob="*.txt")
    documents = loader.load()
    return documents


def split_text(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=150,
        chunk_overlap=150,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")

    document = chunks[10]
    print(document.page_content)
    print(document.metadata)

    return chunks


def save_to_chroma(chunks: list[Document]):
    embedding_function = YandexGptEmbeddingFunction(
        iam_token="t1.9euelZrKlJCenMnNz5aYy5SUzpPMz-3rnpWaipPGk5Cbm86UlpHJys_Mj5rl8_dKBGFO-e8EJQZy_t3z9wozXk757wQlBnL-zef1656VmpGTjpqdjsrOi5ySyZiRzJme7_zF656VmpGTjpqdjsrOi5ySyZiRzJme.5saOlFwfsZUUL4EBe7oBJMic3V0NN11bVw2lW5aTSw0z-TL5VjmNVh6fL8zxsAD-Z6QQ3UTY--6uaBSDLgurDw",
        folder_id="b1gmokkhlfagg82cirvf")
    # Clear out the database first.
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)

    # Create a new DB from the documents.
    db = Chroma.from_documents(
        chunks, embedding_function, persist_directory=CHROMA_PATH
    )
    db.persist()
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")


if __name__ == "__main__":
    main()

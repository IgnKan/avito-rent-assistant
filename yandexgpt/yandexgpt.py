from pprint import pprint

import requests
import configparser
import logging
from loguru import logger


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s @ %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)
logger = logging.getLogger(name="YaGPT-API")


class YandexGPT:
    def __init__(self, folder_id: str, request_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion", model: str = "yandexgpt") -> None:
        self.api_key = None
        self.folder_id = folder_id
        self.request_url = request_url
        self.model = model

    def generate_promt(self,
                        message: list,
                        stream: bool = False,
                        temperature: float = 0.2,
                        max_tokens: int = 4000) -> dict:
        prompt = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}/latest",
            "completionOptions": {
                "stream": stream,
                "temperature": temperature,
                "maxTokens": f"{max_tokens}"
            },
            "messages": message
        }
        return prompt

    def make_request(self,
                     user_message: list,
                     stream: bool = False,
                     temperature: float = 0.2,
                     max_tokens: int = 4000
                     ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            logger.debug(
                f"Request [yandexgpt]: {self.request_url} | {self.model}")
            response = requests.post(self.request_url,
                                     headers=headers,
                                     json=self.generate_promt(user_message,
                                                               stream=stream,
                                                               temperature=temperature,
                                                               max_tokens=max_tokens))
        except requests.RequestException as error:
            logger.error(error)
        else:
            answer = response.json()
            logger.debug(f"Response [yandexgpt]: {self.request_url} | {self.model} | {answer}")
            return self.get_answer_text(answer)
        return ""

    def get_answer_text(self, answer) -> str:
        if answer:
            try:
                result = answer["result"]["alternatives"][0]["message"]["text"]
            except KeyError as error:
                logger.error(error)
            else:
                return result
        return ""

    def init_access_token(self, oauth_token: str, request_url: str) -> None:
        if oauth_token:

            headers = {
                "Content-Type": "application/json"
            }

            promt = {
                "yandexPassportOauthToken": oauth_token
            }
            try:
                response = requests.post(request_url,
                                     headers=headers,
                                     json=promt)

            except requests.RequestException as error:
                logger.error(error)
            else:
                self.api_key = response.json()["iamToken"]

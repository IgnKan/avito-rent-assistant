import os
from pprint import pprint

from yandexgpt import YandexGPT

OAuthYandex = os.getenv("OAuthYandex")
IAMYandex = os.getenv("IAMYandex:", None)

if __name__ == "__main__":


    gpt = YandexGPT(folder_id="b1gmokkhlfagg82cirvf")
    gpt.init_access_token(oauth_token=OAuthYandex, request_url="https://iam.api.cloud.yandex.net/iam/v1/tokens")
    message = [{
        "role": "user",
        "text": "Привет, давай знакомиться"
    }]
    answer = gpt.make_request(message)
    print(answer)

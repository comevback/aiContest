import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
)

resp = client.chat.completions.create(
    model=AZURE_OPENAI_DEPLOYMENT_NAME,
    messages=[{"role": "user", "content": "用一句话介绍Azure OpenAI"}]
)
print(resp.choices[0].message.content)
# openai/

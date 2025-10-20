import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint="https://after-mgzd767o-eastus2.cognitiveservices.azure.com/",
    api_version="2024-12-01-preview"
)

resp = client.chat.completions.create(
    model="gpt-4o-mini",  # 写部署名
    messages=[{"role": "user", "content": "用一句话介绍Azure OpenAI"}]
)
print(resp.choices[0].message.content)
# openai/

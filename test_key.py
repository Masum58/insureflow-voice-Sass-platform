import os
from dotenv import load_dotenv
import requests

# Load .env file
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if not api_key or api_key.strip() == "":
    print("Error: OPENAI_API_KEY is missing in your .env file!")
    exit()

print(f"Testing API Key: {api_key[:10]}...{api_key[-5:]}")

# Send request to OpenAI API to check
headers = {"Authorization": f"Bearer {api_key}"}
response = requests.get("https://api.openai.com/v1/models", headers=headers)

if response.status_code == 200:
    print("[SUCCESS]: Your OpenAI API Key is VALID and working perfectly!")
else:
    error_msg = response.json().get("error", {}).get("message", "Unknown Error")
    print(f"[FAILED]: Your API Key is INVALID.\nReason: {error_msg}")

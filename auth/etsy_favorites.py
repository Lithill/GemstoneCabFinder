import os
import requests
from dotenv import load_dotenv
import json

with open("etsy_tokens.json", "r") as file:
    token_data = json.load(file)

access_token = token_data["access_token"]

# Etsy access tokens begin with the user's numeric ID.
user_id = access_token.split(".", 1)[0]

print("Access token loaded successfully.")
print("Etsy user ID identified:", user_id.isdigit())

load_dotenv()

api_key = os.getenv("ETSY_API_KEY")
shared_secret = os.getenv("ETSY_SHARED_SECRET")

url = "https://openapi.etsy.com/v3/application/openapi-ping"

response = requests.get(
    url,
    headers={
        "x-api-key": f"{api_key}:{shared_secret}",
        "Authorization": f"Bearer {access_token}",
    },
    params={"limit": 100},
    timeout=30,
)

print("HTTP status:", response.status_code)

if response.status_code == 200:
    data = response.json()
    print("Favourite shops returned:", len(data.get("results", [])))
    print("Total favourite shops:", data.get("count", "Not provided"))
else:
    print("Etsy returned an error.")
    print("Error details:", response.text[:1000])
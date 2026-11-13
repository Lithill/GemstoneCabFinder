import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ETSY_API_KEY")
REDIRECT_URI = "http://localhost:8000/callback"

# Load the saved authorisation code
with open("etsy_oauth_code.json", "r") as file:
    saved_code = json.load(file)

# Load the matching PKCE verifier
with open("etsy_oauth_state.json", "r") as file:
    saved_security = json.load(file)

# Exchange the code for an Etsy access token
response = requests.post(
    "https://api.etsy.com/v3/public/oauth/token",
    data={
        "grant_type": "authorization_code",
        "client_id": API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": saved_code["code"],
        "code_verifier": saved_security["code_verifier"],
    },
    timeout=30,
)

if response.status_code == 200:
    token_data = response.json()

    with open("etsy_tokens.json", "w") as file:
        json.dump(token_data, file)

    print("SUCCESS: Etsy access token saved!")
else:
    print("Token exchange failed.")
    print("HTTP status:", response.status_code)
    print("Check that the authorisation code is still valid.")
import os
import secrets
import hashlib
import base64

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ETSY_API_KEY")
REDIRECT_URI = "http://localhost:8000/callback"

# Create a secure PKCE code verifier
code_verifier = secrets.token_urlsafe(64)

# Create the matching PKCE code challenge
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode("utf-8")).digest()
).decode("utf-8").rstrip("=")

# Create a random security state
state = secrets.token_urlsafe(32)

# Build Etsy's authorisation URL
auth_url = requests.Request(
    "GET",
    "https://www.etsy.com/oauth/connect",
    params={
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "shops_r favorites_r",
        "client_id": API_KEY,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    },
).prepare().url

import json

# Save security values for the next authorisation step
with open("etsy_oauth_state.json", "w") as file:
    json.dump({
        "code_verifier": code_verifier,
        "state": state,
    }, file)

print("OAuth security information saved.")

print("Etsy authorisation URL created.")

print()
print("Open this URL in your browser:")
print(auth_url)

print("Etsy authorisation setup loaded.")

if API_KEY:
    print("Etsy API key found.")
else:
    print("ERROR: Etsy API key not found.")
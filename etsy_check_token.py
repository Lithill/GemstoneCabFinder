import json

with open("etsy_tokens.json", "r") as file:
    token_data = json.load(file)

print("Access token present:", bool(token_data.get("access_token")))
print("Refresh token present:", bool(token_data.get("refresh_token")))
print("Token type:", token_data.get("token_type", "Not specified"))
print("Scopes recorded:", token_data.get("scope", "Not included"))
print("Expires in:", token_data.get("expires_in", "Not included"))
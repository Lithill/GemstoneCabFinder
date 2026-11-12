import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


class EtsyCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)

        if parsed_url.path != "/callback":
            self.send_error(404)
            return

        parameters = parse_qs(parsed_url.query)

        if "code" in parameters and "state" in parameters:
            # Load the saved security information
            with open("etsy_oauth_state.json", "r") as file:
                saved_security = json.load(file)

            received_state = parameters["state"][0]

            # Check that the security state matches
            if received_state != saved_security["state"]:
                print("SECURITY ERROR: Etsy state does not match.")
                self.send_error(400, "Security state mismatch")
                return

            # Save the authorisation code for the token exchange
            with open("etsy_oauth_code.json", "w") as file:
                json.dump({
                    "code": parameters["code"][0]
                }, file)

            print("Authorisation code saved.")

            print("Etsy authorisation response received.")
            print("Authorisation code present: Yes")
            print("Security state verified: Yes")

            message = (
                "Etsy authorisation response received. "
                "You can close this tab."
            )

        else:
            print("Etsy callback received, but required values are missing.")
            message = "Etsy callback received, but required values are missing."

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))


print("Waiting for Etsy on http://localhost:8000/callback")
HTTPServer(("localhost", 8000), EtsyCallbackHandler).serve_forever()
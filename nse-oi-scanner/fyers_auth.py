"""
fyers_auth.py  —  refresh the daily Fyers access token.
Equivalent of your old  run_login.bat.

Fyers access tokens expire every day, so run this each morning before the scanner.

    python fyers_auth.py

It prints a login URL, you open it, log in, and paste back the redirect URL (or just
the auth_code from it). The access token is saved to access_token.txt for the scanner.
"""
import sys

try:
    import config
except ImportError:
    sys.exit("!! Copy config.example.py to config.py and fill in your Fyers keys first.")


def main():
    try:
        from fyers_apiv3 import fyersModel
    except ImportError:
        sys.exit("!! Install the SDK:  pip install fyers-apiv3")

    session = fyersModel.SessionModel(
        client_id=config.CLIENT_ID,
        secret_key=config.SECRET_KEY,
        redirect_uri=config.REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
    )

    print("\n1) Open this URL, log in to Fyers, and approve:\n")
    print("   " + session.generate_authcode() + "\n")
    raw = input("2) Paste the FULL redirect URL (or just the auth_code): ").strip()

    # accept either the whole redirect URL or a bare auth_code
    auth_code = raw
    if "auth_code=" in raw:
        auth_code = raw.split("auth_code=")[1].split("&")[0]

    session.set_token(auth_code)
    resp = session.generate_token()
    token = resp.get("access_token")
    if not token:
        sys.exit(f"!! Token generation failed: {resp}")

    with open(config.TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"\n[OK] Access token saved to {config.TOKEN_FILE}. Good for today.")


if __name__ == "__main__":
    main()

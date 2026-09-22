"""
setup.py  —  foolproof config builder. No Notepad, no syntax traps.

    python setup.py

Paste your 3 Fyers values when asked; it writes config.py for you (keeping the
rest of the defaults). config.py is git-ignored, so your secret never leaves your PC.
"""
import os, re

TEMPLATE = "config.example.py"
OUT = "config.py"


def main():
    print("\n=== Fyers Scanner setup ===")
    print("From  myapi.fyers.in -> Dashboard -> your App  (copy each value):\n")
    # The example is a SHAPE, not a real App ID. It used to be the owner's own, which put
    # a live account identifier in a public repository - harmless-looking next to a
    # "Secret ID" prompt, and still the half of a credential pair that names the account.
    cid = input("  App ID        (e.g. ABCD1234-100)  : ").strip().strip('"')
    sec = input("  Secret ID                          : ").strip().strip('"')
    red = input("  Redirect URL  (the FULL url)       : ").strip().strip('"')

    if not (cid and sec and red):
        print("\n!! All three are required. Nothing written. Run again.")
        return

    if os.path.exists(TEMPLATE):
        with open(TEMPLATE) as f:
            text = f.read()
        text = re.sub(r'CLIENT_ID\s*=\s*".*?"',    f'CLIENT_ID    = "{cid}"', text, count=1)
        text = re.sub(r'SECRET_KEY\s*=\s*".*?"',   f'SECRET_KEY   = "{sec}"', text, count=1)
        text = re.sub(r'REDIRECT_URI\s*=\s*".*?"', f'REDIRECT_URI = "{red}"', text, count=1)
    else:
        text = (f'CLIENT_ID    = "{cid}"\nSECRET_KEY   = "{sec}"\nREDIRECT_URI = "{red}"\n'
                'UNIVERSE = ["NSE:NIFTY25JULFUT"]\nMIN_OI_CHANGE_PCT = 5.0\nTOP_N = 15\n'
                'POLL_SECONDS = 300\nTOKEN_FILE = "access_token.txt"\nBASELINE_FILE = "oi_baseline.json"\n'
                'OC_STRIKES = 10\nBAN_LIST = []\nTELEGRAM_TOKEN = ""\nTELEGRAM_CHAT = ""\n')

    with open(OUT, "w") as f:
        f.write(text)
    print(f"\n[OK] {OUT} written. Your keys are saved locally (git-ignored).")
    print("Next:  python fyers_auth.py   ->  then:  streamlit run app.py\n")


if __name__ == "__main__":
    main()

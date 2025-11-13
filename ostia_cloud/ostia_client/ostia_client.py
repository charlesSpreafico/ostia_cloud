import json
import pathlib
import sys
import requests

BASE_DIR = pathlib.Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
TOKEN_PATH = BASE_DIR / "token.json"


def load_config():
    if not CONFIG_PATH.exists():
        print("config.json non trovato. Configurare prima il client.")
        sys.exit(1)
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_token(token_data: dict):
    with TOKEN_PATH.open("w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)
    print("Token salvato in token.json")


def load_token():
    if not TOKEN_PATH.exists():
        print("token.json non trovato. Eseguire prima il login.")
        sys.exit(1)
    with TOKEN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def cmd_login():
    cfg = load_config()
    url = cfg["auth_url"].rstrip("/") + "/login"

    payload = {
        "tenant_id": cfg["tenant_id"],
        "email": cfg["email"],
        "password": cfg["password"],
        "client_id": cfg["client_id"],
    }

    print(f"Chiamo {url} ...")
    resp = requests.post(url, json=payload)
    if resp.status_code != 200:
        print(f"ERRORE login: {resp.status_code} {resp.text}")
        sys.exit(1)

    data = resp.json()
    save_token(data)
    print("Login OK")
    print(f"tenant_id: {data.get('tenant_id')}")
    print(f"client_id: {data.get('client_id')}")
    print(f"user_id:   {data.get('user_id')}")


def cmd_me():
    cfg = load_config()
    token_data = load_token()
    access_token = token_data.get("access_token")
    if not access_token:
        print("token.json non contiene access_token, rifare login.")
        sys.exit(1)

    url = cfg["auth_url"].rstrip("/") + "/me"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    print(f"Chiamo {url} ...")
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}")
    print(resp.text)


def usage():
    print("Utilizzo:")
    print("  python ostia_client.py login   -> esegue login e salva token")
    print("  python ostia_client.py me      -> chiama /me usando il token salvato")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "login":
        cmd_login()
    elif cmd == "me":
        cmd_me()
    else:
        usage()


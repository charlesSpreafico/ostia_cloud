import json
import os
import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

import requests

# Cartella dati applicazione: %APPDATA%\OstiaClient\
def get_data_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if not appdata:
        # fallback se APPDATA non è disponibile
        base = Path.home() / "OstiaClient"
    else:
        base = Path(appdata) / "OstiaClient"
    base.mkdir(parents=True, exist_ok=True)
    return base


DATA_DIR = get_data_dir()
CONFIG_PATH = DATA_DIR / "config.json"
TOKEN_PATH = DATA_DIR / "token.json"


def load_config():
    if CONFIG_PATH.exists():
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg: dict):
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def save_token(token_data: dict):
    with TOKEN_PATH.open("w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


class OstiaClientGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Ostia Client")

        self.cfg = load_config()

        # Valori di default sensati per il tuo ambiente
        self.auth_url_var = tk.StringVar(
            value=self.cfg.get("auth_url", "https://ostia-auth-658895913530.europe-west1.run.app")
        )
        self.tenant_id_var = tk.StringVar(
            value=self.cfg.get("tenant_id", "TENANT_001")
        )
        self.client_id_var = tk.StringVar(
            value=self.cfg.get("client_id", "CLIENT_001")
        )
        self.email_var = tk.StringVar(
            value=self.cfg.get("email", "user@client1.it")
        )
        # Per POC la password la teniamo in chiaro nel config
        self.password_var = tk.StringVar(
            value=self.cfg.get("password", "")
        )

        row = 0

        tk.Label(root, text="Auth URL:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(root, textvariable=self.auth_url_var, width=60).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        tk.Label(root, text="Tenant ID:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(root, textvariable=self.tenant_id_var, width=30).grid(row=row, column=1, padx=5, pady=5, sticky="w")
        row += 1

        tk.Label(root, text="Client ID:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(root, textvariable=self.client_id_var, width=30).grid(row=row, column=1, padx=5, pady=5, sticky="w")
        row += 1

        tk.Label(root, text="Email:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(root, textvariable=self.email_var, width=40).grid(row=row, column=1, padx=5, pady=5, sticky="w")
        row += 1

        tk.Label(root, text="Password:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        tk.Entry(root, textvariable=self.password_var, width=40, show="*").grid(row=row, column=1, padx=5, pady=5, sticky="w")
        row += 1

        # Pulsanti
        btn_frame = tk.Frame(root)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)

        tk.Button(btn_frame, text="Salva Config", command=self.on_save_config).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Test Login", command=self.on_test_login).pack(side=tk.LEFT, padx=5)

        # Etichetta info posizione file
        row += 1
        tk.Label(
            root,
            text=f"Config path: {CONFIG_PATH}",
            fg="grey",
            font=("Segoe UI", 8)
        ).grid(row=row, column=0, columnspan=2, padx=5, pady=5)

    def on_save_config(self):
        cfg = {
            "auth_url": self.auth_url_var.get().strip(),
            "tenant_id": self.tenant_id_var.get().strip(),
            "client_id": self.client_id_var.get().strip(),
            "email": self.email_var.get().strip(),
            "password": self.password_var.get(),
        }
        save_config(cfg)
        messagebox.showinfo("Config", "Configurazione salvata.")

    def on_test_login(self):
        auth_url = self.auth_url_var.get().strip().rstrip("/")
        tenant_id = self.tenant_id_var.get().strip()
        client_id = self.client_id_var.get().strip()
        email = self.email_var.get().strip()
        password = self.password_var.get()

        if not auth_url or not tenant_id or not client_id or not email or not password:
            messagebox.showerror("Errore", "Compila tutti i campi.")
            return

        payload = {
            "tenant_id": tenant_id,
            "email": email,
            "password": password,
            "client_id": client_id,
        }

        try:
            url = auth_url + "/login"
            resp = requests.post(url, json=payload, timeout=10)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore di connessione:\n{e}")
            return

        if resp.status_code != 200:
            msg = f"Login KO\nStatus: {resp.status_code}\nBody: {resp.text}"
            messagebox.showerror("Login fallito", msg)
            return

        data = resp.json()
        save_token(data)
        msg = (
            "Login OK\n"
            f"tenant_id: {data.get('tenant_id')}\n"
            f"client_id: {data.get('client_id')}\n"
            f"user_id: {data.get('user_id')}"
        )
        messagebox.showinfo("Login riuscito", msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = OstiaClientGUI(root)
    root.mainloop()

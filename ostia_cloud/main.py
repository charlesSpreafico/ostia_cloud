import os
import time
import jwt
import psycopg2
import requests
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

PROJECT_ID = os.getenv("GCP_PROJECT", "ostia-478108")

DB_NAME = "ostia_core"
DB_USER = "postgres"
DB_PASSWORD = os.getenv("OSTIA_DB_PASSWORD")
DB_HOST = os.getenv("OSTIA_DB_HOST", "/cloudsql/ostia-478108:europe-west1:testsql")

JWT_SECRET = os.getenv("OSTIA_JWT_SECRET", "dev-secret-change-me")
JWT_ISSUER = "https://auth.ostia.cloud"
JWT_AUDIENCE = "ostia-clients"

IDP_API_KEY = os.getenv("OSTIA_WEB_API_KEY")


def get_db_conn():
    if not DB_PASSWORD:
        raise RuntimeError("OSTIA_DB_PASSWORD not set")
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


class LoginRequest(BaseModel):
    tenant_id: str
    email: str
    password: str
    client_id: Optional[str] = None
    db_profile: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    tenant_id: str
    client_id: str
    user_id: str


def verify_with_identity_platform(email: str, password: str):
    if not IDP_API_KEY:
        raise HTTPException(status_code=500, detail="Identity Platform API key not configured")

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={IDP_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True,
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    data = r.json()
    return data["localId"], data["email"]


def get_or_check_client(conn, tenant_id: str, client_id: Optional[str]) -> str:
    cur = conn.cursor()
    if client_id:
        cur.execute(
            "SELECT client_id FROM clients WHERE tenant_id = %s AND client_id = %s",
            (tenant_id, client_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="Client not provisioned")
        return client_id
    else:
        cur.execute(
            """
            INSERT INTO clients (client_id, tenant_id, name)
            VALUES (
                'C' || EXTRACT(EPOCH FROM NOW())::bigint,
                %s,
                'Auto-created client'
            )
            RETURNING client_id
            """,
            (tenant_id,),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id


@app.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    uid, email_verified = verify_with_identity_platform(req.email, req.password)

    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT user_id, tenant_id
            FROM users
            WHERE user_id = %s AND tenant_id = %s
            """,
            (uid, req.tenant_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="User not provisioned for this tenant")

        client_id = get_or_check_client(conn, req.tenant_id, req.client_id)

        now = int(time.time())
        expires_in = 3600
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": uid,
            "email": req.email,
            "tenant_id": req.tenant_id,
            "client_id": client_id,
            "iat": now,
            "exp": now + expires_in,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        return LoginResponse(
            access_token=token,
            expires_in=expires_in,
            tenant_id=req.tenant_id,
            client_id=client_id,
            user_id=uid,
        )
    finally:
        conn.close()


def decode_token(auth_header: Optional[str]) -> dict:
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/me")
def me(Authorization: Optional[str] = Header(None)):
    payload = decode_token(Authorization)
    return {
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "tenant_id": payload.get("tenant_id"),
        "client_id": payload.get("client_id"),
        "iat": payload.get("iat"),
        "exp": payload.get("exp"),
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "ostia-auth", "project": PROJECT_ID}

# main.py
import os
import io
import csv
import logging

from fastapi import FastAPI, HTTPException
from google.cloud import storage
import psycopg2
from psycopg2.extras import execute_batch

from models import SyncRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ostia-sync-writer")

app = FastAPI(title="Ostia Sync Writer", version="1.0.0")

# Env DB
DB_HOST = os.getenv("DB_HOST")          # es: 127.0.0.1 o socket Cloud SQL
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ostia_core")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Env bucket di default (fallback se file_bucket non è nel payload)
DEFAULT_SYNC_BUCKET = os.getenv("SYNC_BUCKET")

if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
    logger.warning("DB env vars mancanti: assicurati di impostare DB_HOST, DB_NAME, DB_USER, DB_PASSWORD")


def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def download_csv(bucket_name: str, file_name: str) -> list[dict]:
    """Scarica il CSV da GCS e lo restituisce come lista di dict (una riga = un record)."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    if not blob.exists(storage_client):
        raise HTTPException(status_code=404, detail=f"File {file_name} non trovato nel bucket {bucket_name}")

    content = blob.download_as_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    return rows


@app.post("/sync")
def sync(req: SyncRequest):
    logger.info(f"Ricevuta richiesta sync: tenant={req.tenant_id}, client={req.client_id}, "
                f"table={req.table_name}, file={req.file_name}, op={req.operation}")

    bucket_name = req.file_bucket or DEFAULT_SYNC_BUCKET
    if not bucket_name:
        raise HTTPException(status_code=400, detail="file_bucket mancante e SYNC_BUCKET non impostata")

    # 1) scarica dati
    rows = download_csv(bucket_name, req.file_name)
    if not rows:
        logger.info("Nessuna riga nel file CSV, niente da fare")
        return {"status": "ok", "table": req.table_name, "rows_processed": 0}

    # 2) connessione DB
    conn = get_db_conn()
    try:
        if req.table_name == "orders":
            processed = process_orders(conn, req, rows)
        elif req.table_name == "customers":
            processed = process_customers(conn, req, rows)
        else:
            raise HTTPException(status_code=400, detail=f"table_name non supportata: {req.table_name}")

        conn.commit()
        logger.info(f"Sync completato: table={req.table_name}, rows={processed}")

        return {
            "status": "ok",
            "tenant_id": req.tenant_id,
            "client_id": req.client_id,
            "table": req.table_name,
            "rows_processed": processed,
        }
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        logger.exception("Errore durante la sync")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ====== LOGICA PER TABELLE (ESEMPIO) ======

def process_orders(conn, req: SyncRequest, rows: list[dict]) -> int:
    """
    Esempio di upsert per la tabella orders.
    Adatta i campi alle tue colonne reali (order_id, amount, ...).
    Presuppone una tabella orders con chiave (tenant_id, order_id).
    """
    # TODO: sostituisci questi campi con quelli reali del tuo schema
    sql = """
    INSERT INTO orders (tenant_id, client_id, order_id, amount)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (tenant_id, order_id)
    DO UPDATE SET
        client_id = EXCLUDED.client_id,
        amount = EXCLUDED.amount;
    """

    values = []
    for row in rows:
        order_id = row.get("order_id")
        amount = row.get("amount")
        if order_id is None:
            # puoi decidere se skippare o lanciare errore
            continue
        values.append((req.tenant_id, req.client_id, order_id, amount))

    if not values:
        return 0

    with conn.cursor() as cur:
        execute_batch(cur, sql, values, page_size=100)

    return len(values)


def process_customers(conn, req: SyncRequest, rows: list[dict]) -> int:
    """
    Esempio per una tabella customers.
    Qui metti la logica specifica per quella tabella.
    """
    # TODO: implementare in base allo schema reale
    # Per ora facciamo solo un log e non scriviamo nulla
    logger.info(f"process_customers chiamato per {len(rows)} righe (TODO implementazione)")
    return 0

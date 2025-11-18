import os
import csv
import logging
import tempfile
from typing import Optional

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import storage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ostia-sync-writer")

app = FastAPI()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ostia_core")
DB_USER = os.getenv("DB_USER", "ostia_sync_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")
SYNC_BUCKET = os.getenv("SYNC_BUCKET")

storage_client = storage.Client()

class SyncRequest(BaseModel):
    tenant_id: str
    client_id: str
    table_name: str
    file_bucket: Optional[str] = None
    file_name: str
    operation: str = "UPSERT"

def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )

def download_csv_temp(bucket_name: str, blob_name: str) -> str:
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if not blob.exists():
        raise FileNotFoundError(f"Blob {blob_name} non trovato nel bucket {bucket_name}")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    blob.download_to_filename(tmp.name)
    return tmp.name

def process_orders(req: SyncRequest):
    csv_path = download_csv_temp(req.file_bucket or SYNC_BUCKET, req.file_name)

    conn = get_db_conn()
    try:
        with conn.cursor(), open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            for row in rows:
                cur_order_id = row["order_id"]
                amount = row["amount"]

                conn.cursor().execute("""
                    INSERT INTO orders (tenant_id, client_id, order_id, amount, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (tenant_id, order_id)
                    DO UPDATE SET
                        client_id = EXCLUDED.client_id,
                        amount = EXCLUDED.amount,
                        updated_at = NOW();
                """, (req.tenant_id, req.client_id, cur_order_id, amount))

        conn.commit()
        logger.info(f"Processate {len(rows)} righe dal CSV.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

@app.post("/sync")
def sync_endpoint(req: SyncRequest):
    if req.table_name != "orders":
        raise HTTPException(status_code=400, detail="Table non supportata.")

    try:
        process_orders(req)
    except Exception as e:
        logger.exception(f"Errore in /sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "table": req.table_name}

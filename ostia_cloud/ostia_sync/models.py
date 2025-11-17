# models.py
from pydantic import BaseModel
from typing import Optional

class SyncRequest(BaseModel):
    tenant_id: str
    client_id: str
    table_name: str
    file_name: str
    file_bucket: Optional[str] = None
    operation: str = "UPSERT"

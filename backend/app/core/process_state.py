
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class LegalReference(BaseModel):
    diploma: str
    artigo: str
    descricao: Optional[str] = None

class AuditEntry(BaseModel):
    timestamp: datetime
    actor: str
    action: str
    metadata: Dict = {}

class ProcessState(BaseModel):
    process_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    area_juridica: Optional[str] = None

    factos_confirmados: List[str] = []
    factos_contestados: List[str] = []

    provas: List[str] = []

    normas_aplicadas: List[LegalReference] = []

    contraditorio: List[str] = []

    riscos_juridicos: List[str] = []

    auditoria: List[AuditEntry] = []

    metadata: Dict = {}

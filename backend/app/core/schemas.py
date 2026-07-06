from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime


class AreaJuridica(str, Enum):
    LABORAL = "laboral"
    CIVIL = "civil"
    PENAL = "penal"
    ADMINISTRATIVO = "administrativo"
    CONSTITUCIONAL = "constitucional"
    FAMILIA = "familia"
    COMERCIAL = "comercial"
    RGPD = "rgpd"


class AnalysisRequest(BaseModel):
    texto: str = Field(..., min_length=20, max_length=8000, description="Descrição do caso")
    area_juridica: Optional[AreaJuridica] = None
    fontes: list[str] = Field(
        default=["CRP", "CC", "CPC"],
        description="Diplomas jurídicos a considerar"
    )

    @field_validator("texto")
    @classmethod
    def texto_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("O texto do caso não pode estar vazio")
        return v.strip()
    # Se indicado, a análise fica anexada ao caso guardado (rota /casos)
    caso_id: Optional[str] = None


class NormaIdentificada(BaseModel):
    diploma: str
    artigo: str
    relevancia: float = Field(ge=0.0, le=1.0)
    excerto: Optional[str] = None


class AuditInfo(BaseModel):
    timestamp: datetime
    normas_citadas: int
    fontes_utilizadas: list[str]
    modelo: str
    tokens_input: int
    tokens_output: int
    grounded: bool


class AnalysisResponse(BaseModel):
    caso_id: str
    factos: list[str]
    qualificacao_juridica: str
    normas: list[NormaIdentificada]
    analise: str
    vias_processuais: list[str]
    conclusao: str
    contraditorio: Optional[str] = None
    audit: AuditInfo

"""
Sistema de Notificações do SNAJI — Fase 2.

Monitoriza prazos em todos os processos activos e gera alertas.
Em produção: envia emails/SMS via AMA ou plataforma gov.pt.
Agora: mantém fila em memória, consultável via API.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)


class NivelAlerta(str, Enum):
    CRITICO  = "critico"   # prazo expirado
    URGENTE  = "urgente"   # < 3 dias
    AVISO    = "aviso"     # < 7 dias
    INFO     = "info"      # informativo


@dataclass
class Notificacao:
    id: str
    processo_id: str
    processo_numero: str
    nivel: NivelAlerta
    titulo: str
    mensagem: str
    criada_em: datetime
    lida: bool = False
    destinatario_id: Optional[str] = None


class GestorNotificacoes:
    """
    Gere a fila de notificações de prazos.
    Consultável via API. Em produção: integrar com email/SMS gov.pt.
    """

    def __init__(self):
        self._notificacoes: list[Notificacao] = []
        self._contador = 0

    def _novo_id(self) -> str:
        self._contador += 1
        return f"notif-{self._contador:04d}"

    def gerar_alertas_processo(
        self,
        processo_id: str,
        processo_numero: str,
        prazos: list,
        destinatario_id: Optional[str] = None,
    ) -> list[Notificacao]:
        """Analisa os prazos de um processo e gera notificações."""
        agora = datetime.now(timezone.utc)
        novas: list[Notificacao] = []

        for prazo in prazos:
            if prazo.cumprido:
                continue

            dias = (prazo.data_limite - agora).days

            if dias < 0:
                nivel = NivelAlerta.CRITICO
                titulo = f"PRAZO EXPIRADO — {processo_numero}"
                msg = f"O prazo '{prazo.descricao}' expirou há {abs(dias)} dias."
            elif dias == 0:
                nivel = NivelAlerta.CRITICO
                titulo = f"PRAZO HOJE — {processo_numero}"
                msg = f"O prazo '{prazo.descricao}' termina hoje."
            elif dias <= 3:
                nivel = NivelAlerta.URGENTE
                titulo = f"Prazo urgente — {processo_numero}"
                msg = f"O prazo '{prazo.descricao}' termina em {dias} dias."
            elif dias <= 7:
                nivel = NivelAlerta.AVISO
                titulo = f"Prazo próximo — {processo_numero}"
                msg = f"O prazo '{prazo.descricao}' termina em {dias} dias."
            else:
                continue  # Sem alerta para prazos distantes

            notif = Notificacao(
                id=self._novo_id(),
                processo_id=processo_id,
                processo_numero=processo_numero,
                nivel=nivel,
                titulo=titulo,
                mensagem=msg,
                criada_em=agora,
                destinatario_id=destinatario_id,
            )
            self._notificacoes.append(notif)
            novas.append(notif)

            logger.info("notificacao.gerada", nivel=nivel.value, processo=processo_numero)

        return novas

    def listar(
        self,
        destinatario_id: Optional[str] = None,
        apenas_nao_lidas: bool = False,
        limite: int = 50,
    ) -> list[Notificacao]:
        """Lista notificações, opcionalmente filtradas por destinatário."""
        resultado = self._notificacoes

        if destinatario_id:
            resultado = [n for n in resultado if n.destinatario_id == destinatario_id or n.destinatario_id is None]

        if apenas_nao_lidas:
            resultado = [n for n in resultado if not n.lida]

        # Ordena por nível (crítico primeiro) e depois por data
        nivel_ordem = {NivelAlerta.CRITICO: 0, NivelAlerta.URGENTE: 1, NivelAlerta.AVISO: 2, NivelAlerta.INFO: 3}
        resultado = sorted(resultado, key=lambda n: (nivel_ordem[n.nivel], -n.criada_em.timestamp()))

        return resultado[:limite]

    def marcar_lida(self, notif_id: str) -> bool:
        for n in self._notificacoes:
            if n.id == notif_id:
                n.lida = True
                return True
        return False

    def contar_nao_lidas(self, destinatario_id: Optional[str] = None) -> dict:
        notifs = self.listar(destinatario_id=destinatario_id, apenas_nao_lidas=True, limite=1000)
        return {
            "total": len(notifs),
            "criticas": sum(1 for n in notifs if n.nivel == NivelAlerta.CRITICO),
            "urgentes": sum(1 for n in notifs if n.nivel == NivelAlerta.URGENTE),
            "avisos": sum(1 for n in notifs if n.nivel == NivelAlerta.AVISO),
        }


# Instância partilhada
gestor_notificacoes = GestorNotificacoes()

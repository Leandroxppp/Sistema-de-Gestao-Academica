from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class Perfil(str, Enum):
    PROFESSOR = "professor"
    GESTOR = "gestor"


class StatusAluno(str, Enum):
    CADASTRADO = "Cadastrado"
    CURSANDO_MATERIA = "Cursando_Materia"
    REGULAR = "Regular"
    RISCO_MEDIO = "Risco_Medio"
    RISCO_ALTO = "Risco_Alto"
    APROVADO = "Aprovado"
    REPROVADO = "Reprovado"
    EVADIDO = "Evadido"


class NivelRisco(str, Enum):
    BAIXO = "Baixo"
    MEDIO = "Medio"
    ALTO = "Alto"


@dataclass(frozen=True)
class AnaliseRisco:
    aluno_id: int
    nivel: NivelRisco
    fator_risco: float
    media_notas: float
    frequencia: float
    atividades_entregues: int | None
    atividades_esperadas: int | None
    mensagem: str
    criado_em: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "aluno_id": self.aluno_id,
            "nivel": self.nivel.value,
            "fator_risco": round(self.fator_risco, 4),
            "media_notas": round(self.media_notas, 2),
            "frequencia": round(self.frequencia, 2),
            "atividades_entregues": self.atividades_entregues,
            "atividades_esperadas": self.atividades_esperadas,
            "mensagem": self.mensagem,
            "criado_em": self.criado_em.isoformat(timespec="seconds"),
        }


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

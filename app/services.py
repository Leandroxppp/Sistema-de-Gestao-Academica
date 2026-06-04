from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime
from typing import Any

from .database import fetch_all, fetch_one, password_hash
from .models import AnaliseRisco, NivelRisco, StatusAluno, today_iso


class AppError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class AuthService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.sessions: dict[str, dict[str, Any]] = {}

    def login(self, email: str, senha: str) -> dict[str, Any]:
        user = fetch_one(self.conn, "SELECT * FROM usuarios WHERE email = ?", (email,))
        if not user or user["senha_hash"] != password_hash(senha):
            raise AppError("Credenciais invalidas.", 401)
        token = secrets.token_urlsafe(24)
        safe_user = self._safe_user(user)
        self.sessions[token] = safe_user
        return {"token": token, "usuario": safe_user}

    def current_user(self, authorization: str | None) -> dict[str, Any] | None:
        if not authorization:
            return None
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return None
        return self.sessions.get(authorization[len(prefix) :])

    @staticmethod
    def _safe_user(user: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": user["id"],
            "nome": user["nome"],
            "email": user["email"],
            "perfil": user["perfil"],
            "especializacao": user.get("especializacao"),
            "cargo": user.get("cargo"),
        }


class MotorIA:
    """Motor preditivo por regras, conforme contingencia prevista no plano."""

    def analisar(self, aluno_id: int, notas: list[float], frequencia: float) -> AnaliseRisco:
        if not notas:
            raise AppError("Informe ao menos uma nota para analise.")
        if frequencia < 0 or frequencia > 100:
            raise AppError("Frequencia deve estar entre 0 e 100.")

        media = sum(notas) / len(notas)
        deficit_nota = max(0.0, (7.0 - media) / 7.0)
        deficit_freq = max(0.0, (75.0 - frequencia) / 75.0)
        probabilidade = min(0.95, 0.15 + (deficit_nota * 0.5) + (deficit_freq * 0.35))

        if media < 5.0 or frequencia < 65.0 or probabilidade >= 0.7:
            nivel = NivelRisco.ALTO
            mensagem = "Aluno em risco critico: desempenho e/ou frequencia exigem intervencao imediata."
        elif media < 7.0 or frequencia < 80.0 or probabilidade >= 0.4:
            nivel = NivelRisco.MEDIO
            mensagem = "Aluno em atencao: acompanhar proximas avaliacoes e frequencia."
        else:
            nivel = NivelRisco.BAIXO
            mensagem = "Aluno regular: indicadores academicos dentro do esperado."

        return AnaliseRisco(
            aluno_id=aluno_id,
            nivel=nivel,
            probabilidade_evasao=probabilidade,
            media_notas=media,
            frequencia=frequencia,
            mensagem=mensagem,
            criado_em=datetime.now(),
        )


class AcademicService:
    def __init__(self, conn: sqlite3.Connection, motor_ia: MotorIA) -> None:
        self.conn = conn
        self.motor_ia = motor_ia

    def listar_usuarios(self) -> list[dict[str, Any]]:
        rows = fetch_all(self.conn, "SELECT * FROM usuarios ORDER BY nome")
        return [AuthService._safe_user(row) for row in rows]

    def criar_usuario(self, payload: dict[str, Any]) -> dict[str, Any]:
        nome = require(payload, "nome")
        email = require(payload, "email")
        senha = payload.get("senha", "senha123")
        perfil = require(payload, "perfil")
        if perfil not in {"professor", "gestor"}:
            raise AppError("Perfil deve ser professor ou gestor.")
        cur = self.conn.execute(
            """
            INSERT INTO usuarios (nome, email, senha_hash, perfil, especializacao, cargo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome, email, password_hash(senha), perfil, payload.get("especializacao"), payload.get("cargo")),
        )
        self.conn.commit()
        return self.obter_usuario(cur.lastrowid)

    def obter_usuario(self, usuario_id: int) -> dict[str, Any]:
        user = fetch_one(self.conn, "SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
        if not user:
            raise AppError("Usuario nao encontrado.", 404)
        return AuthService._safe_user(user)

    def listar_materias(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT m.*, u.nome AS professor_nome
            FROM materias m
            LEFT JOIN usuarios u ON u.id = m.professor_id
            ORDER BY m.nome
            """,
        )

    def criar_materia(self, payload: dict[str, Any]) -> dict[str, Any]:
        cur = self.conn.execute(
            """
            INSERT INTO materias (nome, carga_horaria, semestre, professor_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                require(payload, "nome"),
                int(require(payload, "carga_horaria")),
                require(payload, "semestre"),
                payload.get("professor_id"),
            ),
        )
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM materias WHERE id = ?", (cur.lastrowid,))

    def listar_alunos(self) -> list[dict[str, Any]]:
        alunos = fetch_all(self.conn, "SELECT * FROM alunos ORDER BY nome")
        for aluno in alunos:
            aluno["materias"] = self._materias_do_aluno(aluno["id"])
            aluno["ultima_analise"] = self._ultima_analise(aluno["id"])
        return alunos

    def obter_aluno(self, aluno_id: int) -> dict[str, Any]:
        aluno = fetch_one(self.conn, "SELECT * FROM alunos WHERE id = ?", (aluno_id,))
        if not aluno:
            raise AppError("Aluno nao encontrado.", 404)
        aluno["materias"] = self._materias_do_aluno(aluno_id)
        aluno["desempenhos"] = fetch_all(
            self.conn,
            """
            SELECT d.*, m.nome AS materia_nome
            FROM desempenhos d
            LEFT JOIN materias m ON m.id = d.materia_id
            WHERE d.aluno_id = ?
            ORDER BY d.data_referencia DESC, d.id DESC
            """,
            (aluno_id,),
        )
        for desempenho in aluno["desempenhos"]:
            desempenho["notas"] = json.loads(desempenho.pop("notas_json"))
        aluno["ultima_analise"] = self._ultima_analise(aluno_id)
        return aluno

    def criar_aluno(self, payload: dict[str, Any]) -> dict[str, Any]:
        cur = self.conn.execute(
            """
            INSERT INTO alunos (nome, matricula, email, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                require(payload, "nome"),
                require(payload, "matricula"),
                payload.get("email"),
                payload.get("status", StatusAluno.CADASTRADO.value),
            ),
        )
        self.conn.commit()
        return self.obter_aluno(cur.lastrowid)

    def vincular_materia(self, aluno_id: int, materia_id: int) -> dict[str, Any]:
        self._ensure_aluno(aluno_id)
        self._ensure_materia(materia_id)
        self.conn.execute(
            "INSERT OR IGNORE INTO matriculas (aluno_id, materia_id) VALUES (?, ?)",
            (aluno_id, materia_id),
        )
        self.conn.execute(
            "UPDATE alunos SET status = ? WHERE id = ? AND status = ?",
            (StatusAluno.CURSANDO_MATERIA.value, aluno_id, StatusAluno.CADASTRADO.value),
        )
        self.conn.commit()
        return self.obter_aluno(aluno_id)

    def registrar_desempenho(self, aluno_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_aluno(aluno_id)
        materia_id = payload.get("materia_id")
        if materia_id is not None:
            self._ensure_materia(int(materia_id))
        notas = [float(nota) for nota in require(payload, "notas")]
        frequencia = float(require(payload, "frequencia"))
        data_referencia = payload.get("data_referencia", today_iso())
        self.conn.execute(
            """
            INSERT INTO desempenhos (aluno_id, materia_id, notas_json, frequencia, data_referencia)
            VALUES (?, ?, ?, ?, ?)
            """,
            (aluno_id, materia_id, json.dumps(notas), frequencia, data_referencia),
        )
        analise = self.motor_ia.analisar(aluno_id, notas, frequencia)
        self._persistir_analise(analise)
        self.conn.commit()
        return {"aluno": self.obter_aluno(aluno_id), "analise": analise.to_dict()}

    def recalcular_riscos(self) -> dict[str, Any]:
        desempenhos = fetch_all(
            self.conn,
            """
            SELECT d.*
            FROM desempenhos d
            INNER JOIN (
                SELECT aluno_id, MAX(id) AS max_id
                FROM desempenhos
                GROUP BY aluno_id
            ) ult ON ult.max_id = d.id
            ORDER BY d.aluno_id
            """,
        )
        analises = []
        for desempenho in desempenhos:
            analise = self.motor_ia.analisar(
                desempenho["aluno_id"],
                [float(nota) for nota in json.loads(desempenho["notas_json"])],
                float(desempenho["frequencia"]),
            )
            self._persistir_analise(analise)
            analises.append(analise.to_dict())
        self.conn.commit()
        return {"total": len(analises), "analises": analises}

    def dashboard(self) -> dict[str, Any]:
        alunos = fetch_all(self.conn, "SELECT * FROM alunos")
        total = len(alunos)
        por_risco = {"Baixo": 0, "Medio": 0, "Alto": 0}
        for aluno in alunos:
            por_risco[aluno["status_risco"]] = por_risco.get(aluno["status_risco"], 0) + 1
        alertas = fetch_all(
            self.conn,
            """
            SELECT a.*, al.nome AS aluno_nome, al.matricula
            FROM alertas a
            JOIN alunos al ON al.id = a.aluno_id
            WHERE a.ativo = 1
            ORDER BY a.id DESC
            LIMIT 10
            """,
        )
        analises = fetch_all(
            self.conn,
            """
            SELECT an.*, al.nome AS aluno_nome
            FROM analises an
            JOIN alunos al ON al.id = an.aluno_id
            ORDER BY an.id DESC
            LIMIT 10
            """,
        )
        media_evasao = sum(float(aluno["probabilidade_evasao"]) for aluno in alunos) / total if total else 0
        return {
            "indicadores": {
                "total_alunos": total,
                "alunos_em_risco": por_risco.get("Medio", 0) + por_risco.get("Alto", 0),
                "alertas_ativos": len(alertas),
                "probabilidade_evasao_media": round(media_evasao, 4),
            },
            "distribuicao_risco": por_risco,
            "alertas": alertas,
            "previsoes_recentes": analises,
        }

    def listar_alertas(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT a.*, al.nome AS aluno_nome, al.matricula
            FROM alertas a
            JOIN alunos al ON al.id = a.aluno_id
            ORDER BY a.ativo DESC, a.id DESC
            """,
        )

    def listar_relatorios(self) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT r.*, u.nome AS criado_por_nome
            FROM relatorios r
            LEFT JOIN usuarios u ON u.id = r.criado_por
            ORDER BY r.id DESC
            """,
        )

    def criar_relatorio(self, payload: dict[str, Any], usuario_id: int | None = None) -> dict[str, Any]:
        tipo = payload.get("tipo", "desempenho")
        titulo = payload.get("titulo", f"Relatorio de {tipo}")
        conteudo = payload.get("conteudo") or json.dumps(self.dashboard(), ensure_ascii=True, indent=2)
        cur = self.conn.execute(
            """
            INSERT INTO relatorios (titulo, tipo, conteudo, criado_por)
            VALUES (?, ?, ?, ?)
            """,
            (titulo, tipo, conteudo, usuario_id),
        )
        self.conn.commit()
        return fetch_one(self.conn, "SELECT * FROM relatorios WHERE id = ?", (cur.lastrowid,))

    def _persistir_analise(self, analise: AnaliseRisco) -> None:
        status = {
            NivelRisco.BAIXO: StatusAluno.REGULAR.value,
            NivelRisco.MEDIO: StatusAluno.RISCO_MEDIO.value,
            NivelRisco.ALTO: StatusAluno.RISCO_ALTO.value,
        }[analise.nivel]
        self.conn.execute(
            """
            INSERT INTO analises
            (aluno_id, nivel_risco, probabilidade_evasao, media_notas, frequencia, mensagem)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                analise.aluno_id,
                analise.nivel.value,
                analise.probabilidade_evasao,
                analise.media_notas,
                analise.frequencia,
                analise.mensagem,
            ),
        )
        self.conn.execute(
            """
            UPDATE alunos
            SET status = ?, status_risco = ?, probabilidade_evasao = ?
            WHERE id = ?
            """,
            (status, analise.nivel.value, analise.probabilidade_evasao, analise.aluno_id),
        )
        self.conn.execute("UPDATE alertas SET ativo = 0, resolvido_em = CURRENT_TIMESTAMP WHERE aluno_id = ?", (analise.aluno_id,))
        if analise.nivel in {NivelRisco.MEDIO, NivelRisco.ALTO}:
            self.conn.execute(
                """
                INSERT INTO alertas (aluno_id, mensagem, nivel_risco)
                VALUES (?, ?, ?)
                """,
                (analise.aluno_id, analise.mensagem, analise.nivel.value),
            )

    def _materias_do_aluno(self, aluno_id: int) -> list[dict[str, Any]]:
        return fetch_all(
            self.conn,
            """
            SELECT m.*
            FROM materias m
            JOIN matriculas ma ON ma.materia_id = m.id
            WHERE ma.aluno_id = ? AND ma.ativa = 1
            ORDER BY m.nome
            """,
            (aluno_id,),
        )

    def _ultima_analise(self, aluno_id: int) -> dict[str, Any] | None:
        return fetch_one(
            self.conn,
            "SELECT * FROM analises WHERE aluno_id = ? ORDER BY id DESC LIMIT 1",
            (aluno_id,),
        )

    def _ensure_aluno(self, aluno_id: int) -> None:
        if not fetch_one(self.conn, "SELECT id FROM alunos WHERE id = ?", (aluno_id,)):
            raise AppError("Aluno nao encontrado.", 404)

    def _ensure_materia(self, materia_id: int) -> None:
        if not fetch_one(self.conn, "SELECT id FROM materias WHERE id = ?", (materia_id,)):
            raise AppError("Materia nao encontrada.", 404)


def require(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if value is None or value == "":
        raise AppError(f"Campo obrigatorio ausente: {field}.")
    return value

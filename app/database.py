from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "academico.db"


def password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_all(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]


def fetch_one(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, tuple(params)).fetchone()
    return dict(row) if row else None


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            perfil TEXT NOT NULL CHECK (perfil IN ('professor', 'gestor')),
            especializacao TEXT,
            cargo TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS materias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            carga_horaria INTEGER NOT NULL,
            semestre TEXT NOT NULL,
            professor_id INTEGER,
            FOREIGN KEY (professor_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            matricula TEXT NOT NULL UNIQUE,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'Cadastrado',
            status_risco TEXT NOT NULL DEFAULT 'Baixo',
            probabilidade_evasao REAL NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS matriculas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            materia_id INTEGER NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1,
            UNIQUE (aluno_id, materia_id),
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS desempenhos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            materia_id INTEGER,
            notas_json TEXT NOT NULL,
            frequencia REAL NOT NULL,
            atividades_entregues INTEGER,
            atividades_esperadas INTEGER,
            data_referencia TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE,
            FOREIGN KEY (materia_id) REFERENCES materias(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            nivel_risco TEXT NOT NULL,
            probabilidade_evasao REAL NOT NULL,
            media_notas REAL NOT NULL,
            frequencia REAL NOT NULL,
            atividades_entregues INTEGER,
            atividades_esperadas INTEGER,
            mensagem TEXT NOT NULL,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            mensagem TEXT NOT NULL,
            nivel_risco TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolvido_em TEXT,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            criado_por INTEGER,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (criado_por) REFERENCES usuarios(id) ON DELETE SET NULL
        );
        """
    )
    ensure_column(conn, "desempenhos", "atividades_entregues", "INTEGER")
    ensure_column(conn, "desempenhos", "atividades_esperadas", "INTEGER")
    ensure_column(conn, "analises", "atividades_entregues", "INTEGER")
    ensure_column(conn, "analises", "atividades_esperadas", "INTEGER")
    conn.commit()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def seed_db(conn: sqlite3.Connection) -> None:
    existing = fetch_one(conn, "SELECT id FROM usuarios LIMIT 1")
    if existing:
        return

    conn.executemany(
        """
        INSERT INTO usuarios (nome, email, senha_hash, perfil, especializacao, cargo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("Ana Professora", "professor@sigma.edu", password_hash("professor123"), "professor", "Matematica", None),
            ("Bruno Gestor", "gestor@sigma.edu", password_hash("gestor123"), "gestor", None, "Coordenador Academico"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO materias (nome, carga_horaria, semestre, professor_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Calculo I", 80, "2026.1", 1),
            ("Programacao", 80, "2026.1", 1),
            ("Logica", 60, "2026.1", 1),
        ],
    )
    conn.executemany(
        """
        INSERT INTO alunos (nome, matricula, email, status, status_risco, probabilidade_evasao)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("Carla Lima", "2026001", "carla@sigma.edu", "Regular", "Baixo", 0.12),
            ("Diego Souza", "2026002", "diego@sigma.edu", "Risco_Medio", "Medio", 0.52),
            ("Elisa Rocha", "2026003", "elisa@sigma.edu", "Risco_Alto", "Alto", 0.84),
        ],
    )
    conn.executemany(
        "INSERT INTO matriculas (aluno_id, materia_id) VALUES (?, ?)",
        [(1, 1), (1, 2), (2, 1), (2, 3), (3, 2), (3, 3)],
    )
    conn.executemany(
        """
        INSERT INTO desempenhos (aluno_id, materia_id, notas_json, frequencia, data_referencia)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (1, 1, "[8.0, 7.5, 9.0]", 92, "2026-05-18"),
            (2, 1, "[5.5, 6.0, 5.0]", 74, "2026-05-18"),
            (3, 2, "[3.0, 4.0, 2.5]", 58, "2026-05-18"),
        ],
    )
    conn.commit()

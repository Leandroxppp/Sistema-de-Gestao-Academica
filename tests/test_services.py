from __future__ import annotations

import sqlite3
import unittest
from uuid import uuid4

from app.database import init_db, seed_db
from app.api import Application
from app.services import AcademicService, AuthService, MotorIA


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        init_db(self.conn)
        seed_db(self.conn)
        self.service = AcademicService(self.conn, MotorIA())

    def test_login_valido_retorna_token(self) -> None:
        auth = AuthService(self.conn)
        result = auth.login("professor@sigma.edu", "professor123")
        self.assertIn("token", result)
        self.assertEqual(result["usuario"]["perfil"], "professor")

    def test_registrar_desempenho_alto_risco_gera_alerta(self) -> None:
        result = self.service.registrar_desempenho(
            1,
            {"materia_id": 1, "notas": [2.0, 3.0, 4.0], "frequencia": 50},
        )
        self.assertEqual(result["analise"]["nivel"], "Alto")
        self.assertIn("fator_risco", result["analise"])
        self.assertNotIn("probabilidade_evasao", result["analise"])
        dashboard = self.service.dashboard()
        self.assertGreaterEqual(dashboard["indicadores"]["alertas_ativos"], 1)

    def test_atividades_entregues_influenciam_risco(self) -> None:
        result = self.service.registrar_desempenho(
            1,
            {
                "materia_id": 1,
                "notas": [8.0, 8.5, 9.0],
                "frequencia": 95,
                "atividades_entregues": 1,
                "atividades_esperadas": 4,
            },
        )
        self.assertEqual(result["analise"]["nivel"], "Alto")
        self.assertEqual(result["analise"]["atividades_entregues"], 1)
        self.assertEqual(result["analise"]["atividades_esperadas"], 4)

    def test_recalcular_riscos_processa_ultimos_desempenhos(self) -> None:
        result = self.service.recalcular_riscos()
        self.assertEqual(result["total"], 3)

    def test_rota_inicial_publica_existe(self) -> None:
        app = Application()
        status, payload = app.dispatch("GET", "/", {}, {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "online")

    def test_professor_nao_pode_cadastrar_aluno(self) -> None:
        app = Application()
        login = app.auth.login("professor@sigma.edu", "professor123")
        with self.assertRaises(Exception) as ctx:
            app.dispatch(
                "POST",
                "/alunos",
                {"nome": "Aluno Teste", "matricula": "T001"},
                {"authorization": f"Bearer {login['token']}"},
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_gestor_pode_cadastrar_aluno(self) -> None:
        app = Application()
        login = app.auth.login("gestor@sigma.edu", "gestor123")
        matricula = f"G{uuid4().hex[:8]}"
        status, payload = app.dispatch(
            "POST",
            "/alunos",
            {"nome": "Aluno Gestor", "matricula": matricula},
            {"authorization": f"Bearer {login['token']}"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["matricula"], matricula)


if __name__ == "__main__":
    unittest.main()

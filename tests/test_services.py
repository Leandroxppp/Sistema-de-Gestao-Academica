from __future__ import annotations

import sqlite3
import unittest

from app.database import init_db, seed_db
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
        dashboard = self.service.dashboard()
        self.assertGreaterEqual(dashboard["indicadores"]["alertas_ativos"], 1)

    def test_recalcular_riscos_processa_ultimos_desempenhos(self) -> None:
        result = self.service.recalcular_riscos()
        self.assertEqual(result["total"], 3)


if __name__ == "__main__":
    unittest.main()

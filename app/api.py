from __future__ import annotations

import json
import re
from threading import RLock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlparse

from .database import connect, init_db, seed_db
from .services import AcademicService, AppError, AuthService, MotorIA


RouteHandler = Callable[[dict[str, str], dict[str, Any], dict[str, str]], tuple[int, Any]]


class Application:
    def __init__(self) -> None:
        self.conn = connect()
        init_db(self.conn)
        seed_db(self.conn)
        self.auth = AuthService(self.conn)
        self.academic = AcademicService(self.conn, MotorIA())
        self.lock = RLock()
        self.routes: list[tuple[str, re.Pattern[str], RouteHandler, bool]] = []
        self._register_routes()

    def _register_routes(self) -> None:
        self.add("GET", r"^/$", self.home, public=True)
        self.add("GET", r"^/health$", self.health, public=True)
        self.add("POST", r"^/auth/login$", self.login, public=True)
        self.add("GET", r"^/usuarios$", self.usuarios)
        self.add("POST", r"^/usuarios$", self.criar_usuario)
        self.add("GET", r"^/materias$", self.materias)
        self.add("POST", r"^/materias$", self.criar_materia)
        self.add("GET", r"^/alunos$", self.alunos)
        self.add("POST", r"^/alunos$", self.criar_aluno)
        self.add("GET", r"^/alunos/(?P<aluno_id>\d+)$", self.aluno)
        self.add("POST", r"^/alunos/(?P<aluno_id>\d+)/materias/(?P<materia_id>\d+)$", self.vincular_materia)
        self.add("POST", r"^/alunos/(?P<aluno_id>\d+)/desempenhos$", self.registrar_desempenho)
        self.add("POST", r"^/analises/recalcular$", self.recalcular_riscos)
        self.add("GET", r"^/dashboard$", self.dashboard)
        self.add("GET", r"^/alertas$", self.alertas)
        self.add("GET", r"^/relatorios$", self.relatorios)
        self.add("POST", r"^/relatorios$", self.criar_relatorio)

    def add(self, method: str, pattern: str, handler: RouteHandler, public: bool = False) -> None:
        self.routes.append((method, re.compile(pattern), handler, public))

    def dispatch(self, method: str, path: str, body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        with self.lock:
            for route_method, pattern, handler, public in self.routes:
                if route_method != method:
                    continue
                match = pattern.match(path)
                if not match:
                    continue
                user = self.auth.current_user(headers.get("authorization"))
                if not public and not user:
                    raise AppError("Autenticacao obrigatoria.", 401)
                body["_current_user"] = user
                return handler(match.groupdict(), body, headers)
        raise AppError("Rota nao encontrada.", 404)

    def health(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, {"status": "ok", "service": "gestao-desempenho-estudantil"}

    def home(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, {
            "mensagem": "Backend do Sistema de Gestao do Desempenho Estudantil",
            "status": "online",
            "autenticacao": {
                "endpoint": "POST /auth/login",
                "usuarios_demo": [
                    {"email": "professor@sigma.edu", "senha": "professor123"},
                    {"email": "gestor@sigma.edu", "senha": "gestor123"},
                ],
            },
            "endpoints_publicos": ["GET /", "GET /health", "POST /auth/login"],
            "endpoints_autenticados": [
                "GET /dashboard",
                "GET /alunos",
                "GET /alertas",
                "GET /relatorios",
                "POST /alunos/{aluno_id}/desempenhos",
                "POST /analises/recalcular",
            ],
        }

    def login(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.auth.login(str(body.get("email", "")), str(body.get("senha", "")))

    def usuarios(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_usuarios()

    def criar_usuario(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_usuario(body)

    def materias(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_materias()

    def criar_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_materia(body)

    def alunos(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_alunos()

    def criar_aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 201, self.academic.criar_aluno(body)

    def aluno(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.obter_aluno(int(params["aluno_id"]))

    def vincular_materia(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        require_gestor(body)
        return 200, self.academic.vincular_materia(int(params["aluno_id"]), int(params["materia_id"]))

    def registrar_desempenho(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 201, self.academic.registrar_desempenho(int(params["aluno_id"]), body)

    def recalcular_riscos(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.recalcular_riscos()

    def dashboard(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.dashboard()

    def alertas(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_alertas()

    def relatorios(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        return 200, self.academic.listar_relatorios()

    def criar_relatorio(self, params: dict[str, str], body: dict[str, Any], headers: dict[str, str]) -> tuple[int, Any]:
        user = body.get("_current_user") or {}
        return 201, self.academic.criar_relatorio(body, user.get("id"))


class RequestHandler(BaseHTTPRequestHandler):
    app: Application

    def do_OPTIONS(self) -> None:
        self._send(204, None)

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
            headers = {key.lower(): value for key, value in self.headers.items()}
            status, response = self.app.dispatch(self.command, parsed.path, body, headers)
            self._send(status, response)
        except AppError as exc:
            self._send(exc.status, {"erro": exc.message})
        except json.JSONDecodeError:
            self._send(400, {"erro": "JSON invalido."})
        except Exception as exc:
            self._send(500, {"erro": "Erro interno.", "detalhe": str(exc)})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send(self, status: int, payload: Any) -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if payload is None:
            self.end_headers()
            return
        encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    app = Application()
    RequestHandler.app = app
    return ThreadingHTTPServer((host, port), RequestHandler)


def require_gestor(body: dict[str, Any]) -> None:
    user = body.get("_current_user") or {}
    if user.get("perfil") != "gestor":
        raise AppError("Acesso restrito ao gestor.", 403)

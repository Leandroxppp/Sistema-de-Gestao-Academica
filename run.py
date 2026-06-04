from __future__ import annotations

import argparse

from app.api import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Backend academico da Equipe Sigma")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    server = create_server(args.host, args.port)
    print(f"Servidor iniciado em http://{args.host}:{args.port}")
    print("Usuarios de demonstracao:")
    print("  professor@sigma.edu / professor123")
    print("  gestor@sigma.edu / gestor123")
    server.serve_forever()


if __name__ == "__main__":
    main()


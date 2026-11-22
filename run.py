from __future__ import annotations

import os

from waitress import serve

from app.main import create_app


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7500"))
    app = create_app()
    print(f"cc-quarantine-lab on http://{host}:{port}/login", flush=True)
    serve(app, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()

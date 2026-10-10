"""Проверка собранного EXE через HTTP с настоящим Elasticsearch."""

import argparse
import csv
import json
import os
import socket
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4


def request(url: str, method: str = "GET") -> tuple[int, object]:
    try:
        with urlopen(Request(url, method=method), timeout=5) as response:
            body = response.read()
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def verify(executable: Path, elasticsearch_url: str) -> None:
    index = "verify-exe-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="document-search-") as directory:
        root = Path(directory)
        csv_path = root / "posts.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["text", "created_date", "rubrics"])
            for number in range(1, 526):
                date = datetime(2020, 1, 1) + timedelta(days=number)
                writer.writerow(["Кошки играют", date.isoformat(), "['animals']"])
        environment = os.environ.copy()
        for key in ("PYTHONHOME", "PYTHONPATH", "DATABASE_PATH", "ELASTICSEARCH_INDEX"):
            environment.pop(key, None)
        environment["LOCALAPPDATA"] = str(root)
        # В PATH нет Python, виртуального окружения и каталога исходников.
        environment["PATH"] = os.pathsep.join([
            str(Path(os.environ["SystemRoot"]) / "System32"), os.environ["SystemRoot"],
        ])
        command = [str(executable), "--elasticsearch-url", elasticsearch_url, "--index", index]
        process = None
        try:
            version = subprocess.run([str(executable), "--version"], cwd=root, env=environment,
                                     capture_output=True, text=True, encoding="utf-8", timeout=60, check=True)
            assert version.stdout.strip() == "DocumentSearch 1.0.0"
            for _ in range(2):
                imported = subprocess.run(command + ["import", str(csv_path)], cwd=root, env=environment,
                                          capture_output=True, text=True, encoding="utf-8", timeout=120, check=True)
                assert "525" in imported.stdout
            database = root / "DocumentSearch" / "documents.db"
            assert database.exists()
            with closing(sqlite3.connect(database)) as db:
                assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 525
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            base_url = f"http://127.0.0.1:{port}"
            with (root / "server.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command + ["serve", "--port", str(port)],
                                           cwd=root, env=environment, stdout=log, stderr=log)
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError((root / "server.log").read_text(encoding="utf-8"))
                    try:
                        assert request(base_url + "/openapi.json")[0] == 200
                        break
                    except (URLError, OSError):
                        if time.monotonic() >= deadline:
                            raise TimeoutError("EXE API did not start")
                        time.sleep(0.5)
                status, documents = request(base_url + "/documents?q=" + quote("кошка"))
                assert status == 200
                assert [d["id"] for d in documents] == list(range(525, 505, -1))
                assert all(set(d) == {"id", "text", "rubrics", "created_date"} for d in documents)
                assert request(base_url + "/documents/525", "DELETE")[0] == 204
                assert request(base_url + "/documents/525", "DELETE")[0] == 404
                assert request(elasticsearch_url + f"/{index}/_doc/525")[0] == 404
                with closing(sqlite3.connect(database)) as db:
                    assert db.execute("SELECT COUNT(*) FROM documents WHERE id = 525").fetchone()[0] == 0
                assert request(base_url + "/documents?q=" + quote("несуществующий")) == (200, [])
                assert request(base_url + "/documents?q=%20%20")[0] == 422
                assert request(base_url + "/documents?q=" + quote("кошка"))[1][0]["id"] == 524
            print("EXE verified: isolated startup, repeat import, 525 documents, global top 20, deletion, validation")
        finally:
            if process is not None and process.poll() is None:
                # У onefile EXE есть дочерний процесс; останавливаем только дерево нашего API.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
                process.wait(timeout=20)
            request(elasticsearch_url + "/" + index, "DELETE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("--elasticsearch-url", default="http://localhost:9200")
    args = parser.parse_args()
    verify(args.executable.resolve(), args.elasticsearch_url)

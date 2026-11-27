"""Serve the upload UI and run document reviews."""

from datetime import datetime
from importlib.metadata import version
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from .gemini import GeminiReviewer, open_client
from .pipeline import run_review
from .readers import read_document

ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
app = FastAPI(title="Requirements Validator")


@app.post("/api/reviews")
def create_review(file: UploadFile = File(...)) -> dict:
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".md", ".pdf"}:
        raise HTTPException(415, "Выберите PDF или Markdown (.md).")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Размер файла превышает 10 МБ.")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(422, "Загружен пустой файл.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Размер файла превышает 10 МБ.")

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    if not api_key or not model:
        raise HTTPException(503, "На сервере не настроено подключение к Gemini.")

    with TemporaryDirectory() as directory:
        path = Path(directory) / f"spec{suffix}"
        path.write_bytes(content)
        try:
            blocks = read_document(path)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, "Не удалось прочитать файл. Для PDF нужен текстовый слой.") from exc
        if not blocks:
            raise HTTPException(422, "В документе не найден текст.")

    try:
        with open_client(api_key) as client:
            result = run_review(blocks, GeminiReviewer(client, model))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, f"Ошибка проверки через Gemini. {exc}") from exc

    return {
        "document": filename,
        "model": model,
        "run_date": datetime.now().astimezone().isoformat(timespec="seconds"),
        "agent_version": version("hihique-requirements-validator"),
        **result,
    }


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")

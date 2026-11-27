# REQ//SCAN

REQ//SCAN проверяет технические задания через Gemini. Он показывает отдельные требования, замечания с цитатами из документа и результаты проверки критериев приёмки. Отчёт можно открыть в браузере или скачать в PDF и Markdown.

## Запуск на Windows

Нужны Python 3.10 или новее и ключ Gemini. Выполните в PowerShell из корня репозитория:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ./backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Откройте `.env` и впишите свой ключ в `GEMINI_API_KEY`. Модель уже указана в `GEMINI_MODEL`. Ключ можно получить в [Google AI Studio](https://aistudio.google.com/api-keys).

```powershell
.\.venv\Scripts\python.exe -m uvicorn validator.api:app --host 127.0.0.1 --port 8003
```

## Прогон одной командой

Укажите путь к ТЗ организаторов и путь для отчёта:

```powershell
.\.venv\Scripts\review-requirements.exe "C:\путь\к\requirements.pdf" --output ".\report.md"
```

Команда запишет русскоязычный отчёт в `report.md` в текущей папке. Для JSON укажите `--output .\report.json`. Веб-сервер для этой команды не нужен.

## Проверка в браузере

1. Откройте [127.0.0.1:8003](http://127.0.0.1:8003/).
2. Загрузите выданное организаторами ТЗ и нажмите «Запустить проверку».
3. Откройте отчёт на сайте или скачайте его в PDF или Markdown.

Поддерживаются PDF с текстовым слоем и Markdown. В браузере можно загружать файлы до 10 МБ. На полном ТЗ агент выполняет до пяти запросов. По умолчанию используется `gemini-3.5-flash-lite`.

Для сдачи приложите исходное ТЗ и сформированный отчёт отдельно от ссылки на репозиторий.

## Тесты без ключа

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

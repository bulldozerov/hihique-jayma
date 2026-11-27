# hihique-jayma

hihique-jayma проверяет технические задания через Gemini. Он показывает отдельные требования, замечания с цитатами из документа и результаты проверки критериев приёмки. Отчёт можно открыть в браузере или скачать в PDF и Markdown.

## Установка на Windows

Нужны Python 3.10 или новее и ключ Gemini. Выполните в PowerShell из корня репозитория:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ./backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Откройте `.env` и впишите свой ключ в `GEMINI_API_KEY`. Модель уже указана в `GEMINI_MODEL`. Ключ можно получить в [Google AI Studio](https://aistudio.google.com/api-keys).

## Через сайт

Запустите сервер из корня проекта:

```powershell
.\.venv\Scripts\python.exe -m uvicorn validator.api:app --host 127.0.0.1 --port 8003
```

1. Откройте [127.0.0.1:8003](http://127.0.0.1:8003/).
2. Загрузите ТЗ в PDF или Markdown и нажмите «Запустить проверку».
3. Когда отчёт будет готов, нажмите «Смотреть на сайте», «Скачать PDF» или «Скачать Markdown». Чтобы получить оба файла из одного прогона, нажмите обе кнопки скачивания.

## Через терминал

Замените путь к ТЗ в нужной команде на свой. Отчёт появится в корне проекта. Веб-сервер для этих команд не нужен.

### Из PDF в PDF

```powershell
.\.venv\Scripts\review-requirements.exe "C:\путь\к\requirements.pdf" --output ".\report.pdf"
```

### Из PDF в Markdown

```powershell
.\.venv\Scripts\review-requirements.exe "C:\путь\к\requirements.pdf" --output ".\report.md"
```

### Из Markdown в PDF

```powershell
.\.venv\Scripts\review-requirements.exe "C:\путь\к\requirements.md" --output ".\report.pdf"
```

### Из Markdown в Markdown

```powershell
.\.venv\Scripts\review-requirements.exe "C:\путь\к\requirements.md" --output ".\report.md"
```

Для отчёта в JSON укажите `--output ".\report.json"` с любым из двух входных форматов. Каждая команда запускает новую проверку через Gemini.

Поддерживаются PDF с текстовым слоем и Markdown. В браузере можно загружать файлы до 10 МБ. На полном ТЗ агент выполняет до пяти запросов. По умолчанию используется `gemini-3.5-flash-lite`.

Для сдачи приложите исходное ТЗ и сформированный отчёт отдельно от ссылки на репозиторий.

## Тесты без ключа

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

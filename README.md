# hihique-jayma
## Проверка ТЗ через Gemini

Из корня репозитория установите пакет бэкенда в активное Python окружение.

```powershell
python -m pip install -e ./backend
Copy-Item .env.example .env
```

Откройте корневой `.env` и укажите ключ из [Google AI Studio](https://aistudio.google.com/api-keys) в `GEMINI_API_KEY`. Модель можно заменить через `GEMINI_MODEL`. Переменные окружения имеют приоритет перед файлом. Для другого расположения файла передайте `--env-file`.

```powershell
review-requirements docs/requirements.pdf --output review.json
```

Команда выполняет два прохода. Первый выделяет и проверяет отдельные требования, второй анализирует документ целиком. В JSON у исходных фрагментов PDF есть номера страниц и строки извлечённого текста на странице. Для Markdown можно передать `docs/requirements.md`, ссылки будут содержать номера строк исходного файла.

PDF должен содержать текстовый слой. Извлечение текста можно проверить без ключа Gemini.

```powershell
parse-requirements docs/requirements.pdf --output pdf-blocks.json
```

Для пробного прогона передайте число блоков через `--max-blocks`. Оба прохода
будут анализировать только выбранный фрагмент с начала документа.

```powershell
review-requirements docs/requirements.md --max-blocks 20 --output review-partial.json
```

Если документ был обрезан, поле `review_scope` в JSON содержит число
проверенных блоков, общее число блоков и номер последней включённой страницы для PDF или строки для Markdown.

## Веб-интерфейс

Из корня репозитория после установки зависимостей и настройки `.env`:

```powershell
python -m uvicorn validator.api:app --host 127.0.0.1 --port 8000
```

На http://127.0.0.1:8000/ доступен демонстрационный интерфейс. Для проверки через Gemini отправьте PDF с текстовым слоем или Markdown в `POST /api/reviews` как поле `file` формы `multipart/form-data`.

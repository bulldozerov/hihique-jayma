# hihique-jayma
## Проверка ТЗ через Gemini

Из корня репозитория установите пакет бэкенда в активное Python окружение.

```powershell
python -m pip install -e ./backend
Copy-Item .env.example .env
```

Откройте корневой `.env` и укажите ключ из [Google AI Studio](https://aistudio.google.com/api-keys) в `GEMINI_API_KEY`. Модель можно заменить через `GEMINI_MODEL`. Переменные окружения имеют приоритет перед файлом. Для другого расположения файла передайте `--env-file`.

```powershell
review-requirements docs/requirements.md --output review.json
```

Команда выполняет два прохода. Первый выделяет и проверяет отдельные требования, второй анализирует документ целиком. JSON содержит результаты обоих проходов и исходные фрагменты с номерами строк.

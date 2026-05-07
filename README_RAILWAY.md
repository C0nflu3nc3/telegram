# Railway Deploy

Этот проект можно деплоить на Railway как worker-сервис без HTTP-порта.

## Что уже подготовлено

- `railway.toml` задает явную старт-команду: `python -u run.py`
- если к сервису подключен Railway Volume, проект автоматически использует `RAILWAY_VOLUME_MOUNT_PATH`
- `.env` исключен из git, вместо него используйте `.env.example`

## Что нужно сделать в Railway

1. Импортировать репозиторий из GitHub.
2. В Variables задать:
   - `BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `ADMIN_ID`
   - при желании `CHAT_MODEL`, `INTENT_MODEL`, `ASSISTANT_STYLE`
3. Добавить Volume к сервису.
4. Указать mount path, например `/app/data`.

## Почему volume важен

Без volume Railway будет хранить файлы только во временной файловой системе контейнера.
Тогда SQLite-база, загруженные файлы и локальное vector-store будут теряться после redeploy/restart.

## Что будет храниться в volume

- `app.db`
- `uploads/`
- `chroma_db/vector_store.json`

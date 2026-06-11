# Railway Deploy

Этот проект можно деплоить на Railway как worker-сервис без HTTP-порта.

## Что уже подготовлено

- `railway.toml` задает явную старт-команду: `python -u run.py`
- `.python-version` фиксирует Python `3.12`, чтобы Railway/Nixpacks не пытались собрать проблемный `python@3.13.14`
- если к сервису подключен Railway Volume, проект автоматически использует `RAILWAY_VOLUME_MOUNT_PATH`
- `.env` исключен из git, вместо него используйте `.env.example`

## Что нужно сделать в Railway

1. Импортировать репозиторий из GitHub.
2. В Variables задать:
   - `BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `ADMIN_IDS` или `ADMIN_ID`
   - при желании `OPENAI_MODEL`, `INTENT_MODEL`, `ASSISTANT_STYLE`
3. Добавить Volume к сервису.
4. Указать mount path, например `/app/data`.
5. После пуша/редеплоя Railway должен взять Python из `.python-version`.

## Почему volume важен

Без volume Railway будет хранить файлы только во временной файловой системе контейнера.
Тогда SQLite-база, загруженные файлы и локальное knowledge-хранилище будут теряться после redeploy/restart.

## Что будет храниться в volume

- `app.db`
- `uploads/`
- локальные knowledge-файлы и служебные данные из `data/`

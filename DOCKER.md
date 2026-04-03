## Запуск в Docker Desktop (Windows)

### 1) Подготовьте `.env`
Создайте файл `.env` рядом с `docker-compose.yml` и заполните минимум:
- `BOT_TOKEN`
- `ADMIN_IDS`

Можно скопировать из `.env.example`.

### 2) Запуск

```powershell
docker compose up --build -d
```

### 3) Проверка логов

```powershell
docker compose logs -f
```

### 4) Остановка

```powershell
docker compose down
```

### Где лежит база SQLite
Файл БД будет в `./data/seobot.db` на хосте (смонтирован в контейнер как `/app/data`).


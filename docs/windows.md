# Windows-версия

`DocumentSearch.exe` — консольная сборка сервиса для Windows 10/11 x64.
Python и его библиотеки уже включены в файл. Elasticsearch запускается отдельно.
Сборка не требует прав администратора.

## Первый запуск

1. Скачайте `DocumentSearch.exe` из раздела Releases и сохраните в удобную папку.
2. Скачайте `compose.yaml` из того же релиза. В Docker Desktop должны быть включены
   Linux-контейнеры. Из папки с этим файлом запустите только Elasticsearch:

   ```powershell
   docker compose up -d elasticsearch
   ```

3. Скачайте [posts.csv](https://disk.yandex.ru/d/UYooXd9q2yqTMQ) в папку с EXE.
   Откройте там PowerShell и загрузите документы:

   ```powershell
   .\DocumentSearch.exe import .\posts.csv
   ```

4. Запустите API:

   ```powershell
   .\DocumentSearch.exe serve
   ```

5. Откройте <http://127.0.0.1:8000/docs>. Здесь можно выполнить поиск и удалить
   документ. Пока API работает, окно PowerShell должно оставаться открытым.
   Для остановки нажмите Ctrl+C.

При двойном щелчке EXE запускает API с настройками по умолчанию.
Для первого запуска удобнее PowerShell: в нём останутся сообщения об ошибках.

## Настройки

SQLite хранится в `%LOCALAPPDATA%\DocumentSearch\documents.db`.
Индекс EXE по умолчанию называется `documents-windows`, адрес Elasticsearch —
`http://localhost:9200`. Для Docker API используется индекс `documents`:
две версии хранят свои базы и не мешают друг другу. Если переопределяете имя индекса,
не используйте одно имя для разных баз SQLite.

Общие параметры указываются **перед** командой:

```powershell
.\DocumentSearch.exe --database D:\Search\documents.db --index my-documents import .\posts.csv
.\DocumentSearch.exe --database D:\Search\documents.db --index my-documents serve --port 8001
```

Для существующего сервера:

```powershell
.\DocumentSearch.exe --elasticsearch-url http://localhost:9200 serve
```

Также поддерживаются `DATABASE_PATH`, `ELASTICSEARCH_URL` и
`ELASTICSEARCH_INDEX`. Справка: `DocumentSearch.exe --help`.
Версия: `DocumentSearch.exe --version`.

Если порт 8000 занят уже работающим Docker API, остановите его командой
`docker compose stop api` или выберите другой порт для EXE.
Если Elasticsearch недоступен, проверьте `docker compose ps` и
`docker compose logs elasticsearch`.

## Сборка из исходников

Нужен Python 3.12 x64 на Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Результат: `dist\DocumentSearch.exe`. PyInstaller используется только для
упаковки и не нужен при обычном запуске сервиса. EXE включает код и зависимости,
но не включает CSV, пользовательскую базу и Elasticsearch.

Проверить EXE с настоящим Elasticsearch можно так:

```powershell
python scripts\verify_windows.py dist\DocumentSearch.exe
```

Проверка создаёт временную базу и отдельный индекс, импортирует 525 тестовых
документов, проверяет выдачу и удаление, затем очищает свои данные.

Рядом с EXE в релизе лежит `SHA256SUMS.txt`. Проверить контрольную сумму можно так:

```powershell
Get-FileHash .\DocumentSearch.exe -Algorithm SHA256
```

Файл не подписан цифровой подписью. Данные сохраняются после закрытия программы;
для удаления локальной SQLite удалите указанную выше папку после остановки API.

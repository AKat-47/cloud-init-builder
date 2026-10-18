# Cloud-Init Builder

Десктопное приложение с графическим интерфейсом для генерации файлов `cloud-config` ([cloud-init](https://cloud-init.io/)), которые автоматически настраивают сервер при первом запуске.

Параметры задаются в интерфейсе, а программа собирает из них готовый YAML. Его можно вставить в поле user-data у облачного провайдера или передать виртуальной машине.

## Возможности

- **Пакеты** — выбор ПО для установки через `apt` (по категориям, базовый набор) и добавление своих пакетов.
- **Пользователи** — создание пользователей с паролем, публичным SSH-ключом, правами `sudo` и членством в группе `docker`.
- **Система** — смена порта SSH (с правилом для `ufw`), запрет или разрешение входа root и аутентификации по паролю, часовой пояс.
- **GitHub / Docker** — анализ репозитория через GitHub API (публичного или приватного по Personal Access Token):
  - определяются версия Python, точка входа, порты, переменные окружения (`os.getenv` / `os.environ`) и нужные сервисы (PostgreSQL, Redis, MongoDB);
  - если в репозитории нет `Dockerfile` и `docker-compose.yml`, программа может их сгенерировать;
  - есть два варианта развёртывания: в Docker-контейнере (`docker compose up -d`) или напрямую на хосте (`pip install` и установка СУБД через `apt`).
- **Результат** — сводка конфигурации, готовый `cloud-config` и копирование в буфер обмена.

## Требования

- Python 3.11+
- Windows, Linux или macOS (нужен Tk; в Linux может понадобиться пакет `python3-tk`)

## Установка и запуск

```bash
git clone https://github.com/AKat-47/cloud-init-builder.git
cd cloud-init-builder

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

## Сборка .exe (Windows)

```bat
build_exe.bat
```

Скрипт создаёт виртуальное окружение, ставит зависимости и PyInstaller, а затем собирает один файл `dist\CloudInitBuilder.exe`.

## Структура проекта

```
├── main.py                  # точка входа, главное окно и сбор конфигурации
├── cloudinit_generator.py   # формирование итогового cloud-config YAML
├── docker_generator.py      # генерация Dockerfile и docker-compose.yml
├── github_analyzer.py       # анализ репозитория через GitHub API
├── ui/
│   ├── tab_packages.py      # вкладка «Пакеты»
│   ├── tab_users.py         # вкладка «Пользователи»
│   ├── tab_system.py        # вкладка «Система»
│   ├── tab_github.py        # вкладка «GitHub / Docker»
│   └── tab_result.py        # вкладка «Результат»
├── build_exe.bat            # сборка исполняемого файла
└── requirements.txt
```

## Безопасность

В программе нет встроенных секретов, файл `.env` для её работы не нужен. Токены и пароли вводятся только в интерфейсе.

Учтите, что **в сгенерированный `cloud-config` эти данные попадают в открытом виде**: пароли пользователей и БД, значения переменных окружения, а для приватного репозитория — GitHub PAT внутри URL для `git clone`. Поэтому:

- не публикуйте сгенерированные файлы и не коммитьте их в репозиторий;
- для приватных репозиториев используйте fine-grained токен с доступом только на чтение к одному репозиторию;
- отключите вход по паролю и используйте SSH-ключи, где это возможно.

## Зависимости

- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — интерфейс
- [requests](https://requests.readthedocs.io/) — запросы к GitHub API
- [PyYAML](https://pyyaml.org/) — сериализация YAML

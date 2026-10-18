DOCKER_INSTALL_COMMANDS = [
    "curl -fsSL https://get.docker.com | sh",
    "systemctl enable docker",
    "systemctl start docker",
]


def generate_dockerfile(py_ver: str = "3.11", main_file: str = "main.py") -> str:
    return f"""FROM python:{py_ver}-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "{main_file}"]
"""


def _yaml_value(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _env_value(db_vars: dict, name: str, placeholder: str) -> str:
    if db_vars and db_vars.get(name):
        return _yaml_value(db_vars[name])
    return placeholder


def _service_templates(db_vars: dict) -> dict[str, str]:
    return {
        "postgres": f"""
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: {_env_value(db_vars, "POSTGRES_PASSWORD", "${POSTGRES_PASSWORD}")}
      POSTGRES_USER: {_env_value(db_vars, "POSTGRES_USER", "${POSTGRES_USER:-app}")}
      POSTGRES_DB: {_env_value(db_vars, "POSTGRES_DB", "${POSTGRES_DB:-app}")}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped""",

        "redis": f"""
  redis:
    image: redis:7-alpine
    environment:
      REDIS_PASSWORD: {_env_value(db_vars, "REDIS_PASSWORD", "${REDIS_PASSWORD:-}")}
    command: sh -c 'if [ -n "$$REDIS_PASSWORD" ]; then redis-server --requirepass "$$REDIS_PASSWORD"; else redis-server; fi'
    restart: unless-stopped""",

        "mongo": f"""
  mongo:
    image: mongo:6
    environment:
      MONGO_INITDB_ROOT_USERNAME: {_env_value(db_vars, "MONGO_USER", "${MONGO_USER:-admin}")}
      MONGO_INITDB_ROOT_PASSWORD: {_env_value(db_vars, "MONGO_PASSWORD", "${MONGO_PASSWORD}")}
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped""",
    }

_VOLUME_NAMES = {
    "postgres": "postgres_data",
    "redis": None,
    "mongo": "mongo_data",
}


def generate_compose(
    project_name: str = "app",
    ports: list[int] = None,
    extra_services: list[str] = None,
    has_env: bool = False,
    db_vars: dict = None,
) -> str:
    ports = ports or []
    extra_services = extra_services or []
    db_vars = db_vars or {}
    service_templates = _service_templates(db_vars)

    depends = [s for s in extra_services if s in service_templates]

    lines = ["services:"]
    lines.append(f"  {project_name}:")
    lines.append("    build: .")
    lines.append("    restart: unless-stopped")

    if ports:
        lines.append("    ports:")
        for p in ports:
            lines.append(f'      - "{p}:{p}"')

    if has_env:
        lines.append("    env_file:")
        lines.append("      - .env")

    if depends:
        lines.append("    depends_on:")
        for svc in depends:
            lines.append(f"      - {svc}")

    for svc in extra_services:
        if svc in service_templates:
            lines.append(service_templates[svc])

    vol_names = [_VOLUME_NAMES[s] for s in extra_services if _VOLUME_NAMES.get(s)]
    if vol_names:
        lines.append("\nvolumes:")
        for vol in vol_names:
            lines.append(f"  {vol}:")

    return "\n".join(lines) + "\n"

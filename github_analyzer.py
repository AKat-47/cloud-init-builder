import re
import base64
import requests

GITHUB_API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}


def parse_github_url(url: str) -> tuple[str, str]:
    match = re.match(
        r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$",
        url.strip(),
    )
    if not match:
        raise ValueError(f"Не удалось распознать GitHub URL: {url}")
    return match.group(1), match.group(2)


def _api_get(url: str, headers: dict | None = None) -> dict | list:
    request_headers = dict(HEADERS)
    if headers:
        request_headers.update(headers)
    try:
        resp = requests.get(url, headers=request_headers, timeout=10)
    except requests.exceptions.Timeout as exc:
        raise TimeoutError("GitHub не ответил вовремя. Попробуйте ещё раз позже.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise ConnectionError("Не удалось подключиться к GitHub. Проверьте интернет-соединение.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Ошибка подключения к GitHub: {exc}") from exc
    if resp.status_code == 404:
        raise FileNotFoundError("Репозиторий не найден или закрыт для публичного доступа.")
    if resp.status_code in (401, 403):
        raise PermissionError("Токен недействителен или не имеет доступа к репозиторию.")
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"GitHub вернул ошибку HTTP {resp.status_code}.") from exc
    return resp.json()


def get_repo_tree(owner: str, repo: str, headers: dict | None = None) -> list[dict]:
    data = _api_get(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1", headers=headers)
    return [item for item in data.get("tree", []) if item["type"] == "blob"]


def get_file_content(owner: str, repo: str, path: str, headers: dict | None = None) -> str:
    data = _api_get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", headers=headers)
    if isinstance(data, list):
        raise IsADirectoryError(f"{path} является директорией")
    raw = data.get("content", "")
    return base64.b64decode(raw).decode("utf-8", errors="replace")


def detect_python_version(files_content: dict[str, str]) -> str:
    if ".python-version" in files_content:
        v = files_content[".python-version"].strip().split("\n")[0].strip()
        if re.match(r"^\d+\.\d+", v):
            return v

    if "pyproject.toml" in files_content:
        m = re.search(r'python_requires\s*=\s*["\']>=?(\d+\.\d+)', files_content["pyproject.toml"])
        if m:
            return m.group(1)

    if "setup.py" in files_content:
        m = re.search(r'python_requires\s*=\s*["\']>=?(\d+\.\d+)', files_content["setup.py"])
        if m:
            return m.group(1)

    return "3.11"


def detect_main_file(py_files_content: dict[str, str]) -> str | None:
    candidates = []
    for path, content in py_files_content.items():
        if "__main__" in content:
            candidates.append(path)

    if not candidates:
        return None

    root_level = [p for p in candidates if "/" not in p]
    if root_level:
        for preferred in ("main.py", "bot.py", "app.py", "run.py", "start.py"):
            if preferred in root_level:
                return preferred
        return root_level[0]

    return candidates[0]


def detect_ports(py_files_content: dict[str, str]) -> list[int]:
    ports = set()
    patterns = [
        r"port\s*=\s*(\d{2,5})",
        r"\.run\([^)]*port\s*=\s*(\d{2,5})",
        r"listen\s*\(\s*(\d{2,5})",
        r"PORT\s*=\s*(\d{2,5})",
        r'getenv\([^)]*["\'](\d{2,5})["\']',
    ]
    for content in py_files_content.values():
        for pattern in patterns:
            for m in re.finditer(pattern, content):
                port = int(m.group(1))
                if 1024 <= port <= 65535:
                    ports.add(port)
    return sorted(ports)


def detect_env_vars(py_files_content: dict[str, str]) -> dict[str, str]:
    vars_found: dict[str, str] = {}

    all_code = "\n".join(py_files_content.values())

    for cast, typ in (("int", "int"), ("float", "float")):
        patterns = [
            rf'{cast}\s*\(\s*(?:(?:os\.)?getenv|(?:os\.)?environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']',
            rf'{cast}\s*\(\s*(?:os\.)?environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']',
        ]
        for pattern in patterns:
            for m in re.finditer(pattern, all_code):
                vars_found[m.group(1)] = typ

    for m in re.finditer(
        r'(?:(?:os\.)?getenv|(?:os\.)?environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']'
        r'\s*,\s*([^\)]+)\)',
        all_code
    ):
        name = m.group(1)
        if name in vars_found:
            continue
        default = m.group(2).strip()
        if re.match(r'^\d+\.\d+$', default):
            vars_found[name] = "float"
        elif re.match(r'^\d+$', default):
            vars_found[name] = "int"
        else:
            vars_found[name] = "str"

    patterns = [
        r'(?:(?:os\.)?getenv|(?:os\.)?environ\.get)\(\s*["\']([A-Z_][A-Z0-9_]*)["\']',
        r'(?:os\.)?environ\[\s*["\']([A-Z_][A-Z0-9_]*)["\']',
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, all_code):
            name = m.group(1)
            if name not in vars_found:
                vars_found[name] = "str"

    return dict(sorted(vars_found.items()))


def detect_extra_services(req_content: str) -> list[str]:
    services = []
    lower = req_content.lower()
    if any(lib in lower for lib in ("psycopg2", "asyncpg")):
        services.append("postgres")
    if any(lib in lower for lib in ("redis", "aioredis")):
        services.append("redis")
    if any(lib in lower for lib in ("pymongo", "motor")):
        services.append("mongo")
    return services


def analyze_repo(url: str, access_token: str | None = None) -> dict:
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    owner, repo = parse_github_url(url)
    tree = get_repo_tree(owner, repo, headers=headers)
    all_paths = [item["path"] for item in tree]

    result = {
        "owner": owner,
        "repo": repo,
        "has_dockerfile": "Dockerfile" in all_paths,
        "has_compose": "docker-compose.yml" in all_paths or "docker-compose.yaml" in all_paths,
        "has_requirements": "requirements.txt" in all_paths,
        "python_version": "3.11",
        "main_file": None,
        "ports": [],
        "env_vars": [],
        "extra_services": [],
        "files_content": {},
    }

    special = [
        ".python-version",
        "pyproject.toml",
        "setup.py",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    ]
    for fname in special:
        if fname in all_paths:
            try:
                result["files_content"][fname] = get_file_content(owner, repo, fname, headers=headers)
            except Exception:
                pass

    py_paths = [p for p in all_paths if p.endswith(".py")][:40]
    py_content = {}
    for path in py_paths:
        try:
            py_content[path] = get_file_content(owner, repo, path, headers=headers)
        except Exception:
            pass
    result["files_content"].update(py_content)

    result["python_version"] = detect_python_version(result["files_content"])
    result["main_file"] = detect_main_file(py_content)
    result["ports"] = detect_ports(py_content)
    result["env_vars"] = detect_env_vars(py_content)

    req = result["files_content"].get("requirements.txt", "")
    result["extra_services"] = detect_extra_services(req)

    return result

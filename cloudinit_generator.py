import base64
import posixpath
import shlex
import yaml

from docker_generator import DOCKER_INSTALL_COMMANDS


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _make_write_file(path: str, content: str, permissions: str = "0644") -> dict:
    return {
        "path": path,
        "encoding": "b64",
        "content": _b64(content),
        "permissions": permissions,
    }


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


DB_SERVICE_COMMANDS = {
    "postgres": {
        "package": "postgresql",
        "systemd": "postgresql",
    },
    "redis": {
        "package": "redis-server",
        "systemd": "redis-server",
    },
    "mongo": {
        "package": "mongodb",
        "systemd": "mongodb",
    },
}


def _shell_arg(value: str) -> str:
    return shlex.quote(str(value))


def _sql_literal(value: str) -> str:
    return str(value).replace("'", "''")


def _js_literal(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def _effective_db_vars(gh: dict) -> dict:
    db_keys = {
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "POSTGRES_DB",
        "REDIS_PASSWORD",
        "MONGO_USER",
        "MONGO_PASSWORD",
    }
    env_vars = gh.get("env_vars", {})
    db_vars = gh.get("db_vars", {})
    result = {key: env_vars[key] for key in db_keys if env_vars.get(key)}
    result.update({key: value for key, value in db_vars.items() if value})
    return result


def _db_service_runcmd(extra_services: list[str], db_vars: dict) -> list[str]:
    commands = []
    for service in extra_services:
        spec = DB_SERVICE_COMMANDS.get(service)
        if not spec:
            continue

        commands.extend([
            f"DEBIAN_FRONTEND=noninteractive apt-get install -y {spec['package']}",
            f"systemctl enable {spec['systemd']}",
            f"systemctl start {spec['systemd']}",
        ])

        if service == "postgres":
            user = db_vars.get("POSTGRES_USER", "app")
            password = db_vars.get("POSTGRES_PASSWORD")
            database = db_vars.get("POSTGRES_DB", "app")
            if password:
                create_user_sql = (
                    f"CREATE USER {user} WITH PASSWORD '{_sql_literal(password)}';"
                )
                create_db_sql = f"CREATE DATABASE {database} OWNER {user};"
                commands.extend([
                    f"sudo -u postgres psql -c {_shell_arg(create_user_sql)}",
                    f"sudo -u postgres psql -c {_shell_arg(create_db_sql)}",
                ])

        elif service == "mongo":
            user = db_vars.get("MONGO_USER", "admin")
            password = db_vars.get("MONGO_PASSWORD")
            if password:
                js = (
                    "db.getSiblingDB('admin').createUser({"
                    f"user: '{_js_literal(user)}', "
                    f"pwd: '{_js_literal(password)}', "
                    "roles: ['root']})"
                )
                commands.append(f"mongosh --eval {_shell_arg(js)}")

        elif service == "redis":
            password = db_vars.get("REDIS_PASSWORD")
            if password:
                commands.extend([
                    f"echo {_shell_arg('requirepass ' + password)} >> /etc/redis/redis.conf",
                    "systemctl restart redis-server",
                ])

    return commands


def build_cloud_init(config: dict) -> str:
    sections: dict = {}
    gh = config.get("github")
    use_container = bool(gh and gh.get("use_container"))

    packages = _dedupe(list(config.get("packages", [])))
    if gh and "git" not in packages:
        packages.append("git")
    if gh and not use_container and "python3-pip" not in packages:
        packages.append("python3-pip")
    packages = _dedupe(packages)
    if packages:
        sections["packages"] = packages
        sections["package_update"] = True
        sections["package_upgrade"] = False

    timezone = config.get("timezone")
    if timezone:
        sections["timezone"] = timezone

    users_cfg = config.get("users", [])
    if users_cfg:
        users_list = []
        for u in users_cfg:
            entry: dict = {
                "name": u["name"],
                "shell": u.get("shell", "/bin/bash"),
                "lock_passwd": False,
            }
            if u.get("sudo"):
                entry["sudo"] = "ALL=(ALL) NOPASSWD:ALL"
            if u.get("groups"):
                entry["groups"] = u["groups"]
            if u.get("ssh_authorized_keys"):
                entry["ssh_authorized_keys"] = u["ssh_authorized_keys"]
            if u.get("password_hash"):
                entry["passwd"] = u["password_hash"]
            users_list.append(entry)
        sections["users"] = users_list

        plain_passwords = [u for u in users_cfg if u.get("password") and not u.get("password_hash")]
        if plain_passwords:
            sections["chpasswd"] = {
                "expire": False,
                "list": [f"{u['name']}:{u['password']}" for u in plain_passwords],
            }

    write_files = []

    ssh_port = config.get("ssh_port")
    if ssh_port and ssh_port != 22:
        root_login = "yes" if config.get("root_login", True) else "no"
        password_auth = "yes" if config.get("password_auth", True) else "no"
        sshd_config = (
            f"Port {ssh_port}\n"
            f"PermitRootLogin {root_login}\n"
            f"PasswordAuthentication {password_auth}\n"
        )
        write_files.append(_make_write_file("/etc/ssh/sshd_config.d/99-custom.conf", sshd_config, "0600"))

    staging_path = "/tmp/cloud-init-builder"
    if gh:
        dockerfile_generated = bool(gh.get("dockerfile_generated"))
        compose_generated = bool(gh.get("compose_generated"))

        if use_container and dockerfile_generated and gh.get("dockerfile"):
            write_files.append(_make_write_file(f"{staging_path}/Dockerfile", gh["dockerfile"]))

        if use_container and compose_generated and gh.get("compose"):
            write_files.append(_make_write_file(f"{staging_path}/docker-compose.yml", gh["compose"]))

        env_vars = gh.get("env_vars", {})
        if env_vars:
            env_content = "\n".join(f"{k}={v}" for k, v in env_vars.items()) + "\n"
            write_files.append(_make_write_file(f"{staging_path}/.env", env_content, "0600"))
    if write_files:
        sections["write_files"] = write_files

    runcmd = []

    if ssh_port and ssh_port != 22:
        runcmd += [
            "systemctl stop ssh.socket",
            "systemctl disable ssh.socket",
            f"ufw allow {ssh_port}/tcp",
            "ufw delete allow 22/tcp",
            "systemctl restart ssh",
            "systemctl enable ssh",
        ]

    for cmd_block in config.get("runcmd_packages", []):
        runcmd.extend(cmd_block)

    if gh:
        repo_url = gh.get("repo_url")
        deploy_path = gh.get("deploy_path", "/opt/app")
        deploy_parent = posixpath.dirname(deploy_path.rstrip("/")) or "/"

        if repo_url:
            if gh.get("is_private") and gh.get("access_token"):
                repo_url = repo_url.replace(
                    "https://",
                    f"https://{gh['access_token']}@",
                )
            q_repo_url = shlex.quote(repo_url)
            q_deploy_path = shlex.quote(deploy_path)
            q_deploy_parent = shlex.quote(deploy_parent)
            q_staging_path = shlex.quote(staging_path)

            runcmd += [
                f"mkdir -p {q_deploy_parent}",
                f"git clone --depth 1 {q_repo_url} {q_deploy_path}",
            ]

            if not use_container:
                runcmd.append(f"cd {q_deploy_path} && pip install -r requirements.txt")
                runcmd.extend(
                    _db_service_runcmd(
                        gh.get("extra_services", []),
                        _effective_db_vars(gh),
                    )
                )

            if gh.get("env_vars"):
                runcmd.append(f"cp {q_staging_path}/.env {q_deploy_path}/.env && chmod 600 {q_deploy_path}/.env")

            if use_container and gh.get("dockerfile_generated") and gh.get("dockerfile"):
                runcmd.append(f"cp {q_staging_path}/Dockerfile {q_deploy_path}/Dockerfile")

            if use_container and gh.get("compose_generated") and gh.get("compose"):
                runcmd.append(f"cp {q_staging_path}/docker-compose.yml {q_deploy_path}/docker-compose.yml")

    if use_container:
        deploy_path = gh.get("deploy_path", "/opt/app")
        q_deploy_path = shlex.quote(deploy_path)

        for cmd in DOCKER_INSTALL_COMMANDS:
            if cmd not in runcmd:
                runcmd.append(cmd)

        runcmd += [
            f"cd {q_deploy_path} && docker compose build",
            f"cd {q_deploy_path} && docker compose up -d",
        ]

    if runcmd:
        sections["runcmd"] = runcmd

    body = yaml.dump(
        sections,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
    return "#cloud-config\n" + body

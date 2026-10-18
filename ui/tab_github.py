import re
import threading
import customtkinter as ctk
from tkinter import messagebox

from github_analyzer import analyze_repo
from docker_generator import generate_dockerfile, generate_compose


DB_VAR_SPECS = {
    "postgres": [
        ("POSTGRES_PASSWORD", "", True),
        ("POSTGRES_USER", "app", False),
        ("POSTGRES_DB", "app", False),
    ],
    "redis": [
        ("REDIS_PASSWORD", "", False),
    ],
    "mongo": [
        ("MONGO_USER", "admin", False),
        ("MONGO_PASSWORD", "", True),
    ],
}


class EnvVarsDialog(ctk.CTkToplevel):
    def __init__(self, parent, env_vars_types: dict):
        super().__init__(parent)
        self.title("Переменные окружения")
        self.geometry("560x440")
        self.resizable(False, True)
        self.grab_set()
        self.focus_set()

        self.result = None
        self._entries = {}
        self._types = env_vars_types
        self._build(env_vars_types)

    def _build(self, env_vars_types):
        ctk.CTkLabel(
            self,
            text="Заполните все переменные окружения",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(padx=20, pady=(16, 4))

        ctk.CTkLabel(
            self,
            text="Эти переменные обнаружены в коде (os.getenv / os.environ).\n"
                 "Все поля обязательны для заполнения.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="center"
        ).pack(padx=20, pady=(0, 12))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        type_color = {"str": "#5dade2", "int": "#58d68d", "float": "#f39c12"}

        for var_name, var_type in env_vars_types.items():
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=6)

            left = ctk.CTkFrame(row, fg_color="transparent", width=210)
            left.pack(side="left", fill="y")
            left.pack_propagate(False)

            ctk.CTkLabel(
                left,
                text=var_name,
                font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
                anchor="w"
            ).pack(anchor="w")

            ctk.CTkLabel(
                left,
                text=f"тип: {var_type}",
                font=ctk.CTkFont(size=10),
                text_color=type_color.get(var_type, "gray"),
                anchor="w"
            ).pack(anchor="w")

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="left", fill="x", expand=True, padx=(10, 0))

            if var_type == "str":
                ctk.CTkLabel(
                    right, text='"',
                    font=ctk.CTkFont(family="Courier", size=15),
                    text_color="#888888"
                ).pack(side="left")

            entry = ctk.CTkEntry(right, placeholder_text="значение")
            entry.pack(side="left", fill="x", expand=True)
            self._entries[var_name] = entry

            if var_type == "str":
                ctk.CTkLabel(
                    right, text='"',
                    font=ctk.CTkFont(family="Courier", size=15),
                    text_color="#888888"
                ).pack(side="left")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 16))

        self._error_label = ctk.CTkLabel(btn_row, text="", text_color="red",
                                          font=ctk.CTkFont(size=11))
        self._error_label.pack(side="left")

        ctk.CTkButton(
            btn_row, text="Отмена", width=100,
            fg_color="transparent", border_width=1,
            command=self.destroy
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_row, text="Сохранить", width=120,
            command=self._save
        ).pack(side="right")

    def _save(self):
        empty = [name for name, entry in self._entries.items() if not entry.get().strip()]
        if empty:
            self._error_label.configure(text=f"Не заполнено: {', '.join(empty)}")
            return

        for name, entry in self._entries.items():
            val = entry.get().strip()
            typ = self._types[name]
            try:
                if typ == "int":
                    int(val)
                elif typ == "float":
                    float(val)
            except ValueError:
                self._error_label.configure(
                    text=f"{name}: ожидается {typ}, введено «{val}»")
                return

        self.result = {name: entry.get().strip() for name, entry in self._entries.items()}
        self.destroy()


class GithubTab(ctk.CTkFrame):
    def __init__(self, master, on_container_toggle=None, on_repo_ready=None):
        super().__init__(master, fg_color="transparent")
        self._on_container_toggle = on_container_toggle
        self._on_repo_ready = on_repo_ready
        self._repo_data = None
        self._token_visible = False
        self._env_values = {}
        self._env_entries = {}
        self._env_error_labels = {}
        self._db_values = {}
        self._db_entries = {}
        self._db_error_labels = {}
        self._db_required = {}
        self._env_default_border = "#565b5e"
        self._env_warning_border = "#f1c40f"
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Развёртывание приложения из GitHub",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            self,
            text="Укажите ссылку на репозиторий — программа проанализирует код и подготовит конфигурацию.",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        url_frame = ctk.CTkFrame(self)
        url_frame.pack(fill="x", padx=20, pady=(0, 8))

        inner = ctk.CTkFrame(url_frame, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)

        ctk.CTkLabel(inner, text="GitHub URL:").pack(side="left", padx=(0, 10))
        self._url_entry = ctk.CTkEntry(inner, placeholder_text="https://github.com/user/repo")
        self._url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._url_entry.bind("<KeyRelease>", lambda _event: self._refresh_private_repo_controls())
        self._analyze_btn = ctk.CTkButton(
            inner, text="Анализировать", width=130, command=self._start_analyze)
        self._analyze_btn.pack(side="left")
        self._remove_repo_btn = ctk.CTkButton(
            inner,
            text="Удалить",
            width=90,
            fg_color="transparent",
            border_width=1,
            state="disabled",
            command=self._remove_repo,
        )
        self._remove_repo_btn.pack(side="left", padx=(8, 0))

        self._private_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._private_frame.pack(fill="x", padx=35, pady=(0, 8))

        self._is_private_var = ctk.BooleanVar(value=False)
        self._private_checkbox = ctk.CTkCheckBox(
            self._private_frame,
            text="Приватный репозиторий",
            variable=self._is_private_var,
            command=self._toggle_private_repo,
        )
        self._private_checkbox.pack(anchor="w")

        self._token_row = ctk.CTkFrame(self._private_frame, fg_color="transparent")
        ctk.CTkLabel(self._token_row, text="GitHub PAT:").pack(side="left", padx=(0, 10))
        self._token_entry = ctk.CTkEntry(self._token_row, show="*")
        self._token_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._toggle_token_btn = ctk.CTkButton(
            self._token_row,
            text="Показать",
            width=90,
            command=self._toggle_token_visibility,
        )
        self._toggle_token_btn.pack(side="left")
        self._private_frame.pack_forget()

        self._status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self._status_label.pack(anchor="w", padx=20, pady=(0, 5))

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        meta = ctk.CTkFrame(self._scroll, fg_color="transparent")
        meta.pack(fill="x", pady=(5, 10))
        meta.columnconfigure(1, weight=1)
        meta.columnconfigure(3, weight=1)

        ctk.CTkLabel(meta, text="Имя проекта:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self._project_name = ctk.CTkEntry(meta, placeholder_text="myapp")
        self._project_name.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=4)

        ctk.CTkLabel(meta, text="Путь на сервере:", anchor="w").grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=4)
        self._deploy_path = ctk.CTkEntry(meta, placeholder_text="/opt/myapp")
        self._deploy_path.insert(0, "/opt/app")
        self._deploy_path.grid(row=0, column=3, sticky="ew", pady=4)

        self._container_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._scroll,
            text="Развернуть приложение в Docker-контейнере",
            variable=self._container_var,
            command=self._toggle_container,
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", pady=(5, 8))

        self._docker_block = ctk.CTkFrame(self._scroll)
        self._build_docker_block()

        self._env_section = ctk.CTkFrame(self._scroll)

        ctk.CTkLabel(
            self._env_section,
            text="Переменные окружения",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", pady=(8, 2))

        self._env_info = ctk.CTkLabel(
            self._env_section, text="", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self._env_info.pack(anchor="w", pady=(0, 6))

        self._env_fields_frame = ctk.CTkFrame(self._env_section, fg_color="transparent")
        self._env_fields_frame.pack(fill="x", pady=(0, 6))

        self._env_btn = ctk.CTkButton(
            self._env_section,
            text="Заполнить переменные...",
            command=self._open_env_dialog
        )

        self._env_status = ctk.CTkLabel(
            self._env_section, text="", font=ctk.CTkFont(size=11)
        )
        self._env_status.pack(anchor="w", pady=(0, 8))

        self._db_section = ctk.CTkFrame(self._scroll)

        ctk.CTkLabel(
            self._db_section,
            text="Параметры базы данных",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", pady=(8, 2))

        self._db_info = ctk.CTkLabel(
            self._db_section,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self._db_info.pack(anchor="w", pady=(0, 6))

        self._db_fields_frame = ctk.CTkFrame(self._db_section, fg_color="transparent")
        self._db_fields_frame.pack(fill="x", pady=(0, 6))

        self._db_status = ctk.CTkLabel(
            self._db_section, text="", font=ctk.CTkFont(size=11)
        )
        self._db_status.pack(anchor="w", pady=(0, 8))

    def _build_docker_block(self):
        ctk.CTkLabel(
            self._docker_block, text="Dockerfile",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 2))

        self._dockerfile_info = ctk.CTkLabel(
            self._docker_block, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._dockerfile_info.pack(anchor="w", padx=10)

        self._dockerfile_text = ctk.CTkTextbox(
            self._docker_block, height=170,
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self._dockerfile_text.pack(fill="x", padx=10, pady=(4, 6))

        dockerfile_btn_row = ctk.CTkFrame(self._docker_block, fg_color="transparent")
        dockerfile_btn_row.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(
            dockerfile_btn_row,
            text="Скопировать Dockerfile",
            width=170,
            command=lambda: self._copy_textbox(self._dockerfile_text, self._dockerfile_copy_label),
        ).pack(side="left")
        self._dockerfile_copy_label = ctk.CTkLabel(
            dockerfile_btn_row, text="", text_color="green", font=ctk.CTkFont(size=11)
        )
        self._dockerfile_copy_label.pack(side="left", padx=10)

        ctk.CTkLabel(
            self._docker_block, text="docker-compose.yml",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=10, pady=(0, 2))

        self._compose_info = ctk.CTkLabel(
            self._docker_block, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._compose_info.pack(anchor="w", padx=10)

        self._compose_text = ctk.CTkTextbox(
            self._docker_block, height=200,
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self._compose_text.pack(fill="x", padx=10, pady=(4, 6))

        compose_btn_row = ctk.CTkFrame(self._docker_block, fg_color="transparent")
        compose_btn_row.pack(fill="x", padx=10, pady=(0, 12))
        ctk.CTkButton(
            compose_btn_row,
            text="Скопировать docker-compose.yml",
            width=230,
            command=lambda: self._copy_textbox(self._compose_text, self._compose_copy_label),
        ).pack(side="left")
        self._compose_copy_label = ctk.CTkLabel(
            compose_btn_row, text="", text_color="green", font=ctk.CTkFont(size=11)
        )
        self._compose_copy_label.pack(side="left", padx=10)

    def _refresh_private_repo_controls(self):
        if self._url_entry.get().strip():
            self._private_frame.pack(fill="x", padx=35, pady=(0, 8), before=self._status_label)
        else:
            self._is_private_var.set(False)
            self._token_entry.delete(0, "end")
            self._token_row.pack_forget()
            self._private_frame.pack_forget()

    def _toggle_private_repo(self):
        if self._is_private_var.get():
            self._token_row.pack(fill="x", pady=(8, 0))
        else:
            self._token_entry.delete(0, "end")
            self._token_row.pack_forget()

    def _toggle_token_visibility(self):
        self._token_visible = not self._token_visible
        self._token_entry.configure(show="" if self._token_visible else "*")
        self._toggle_token_btn.configure(text="Скрыть" if self._token_visible else "Показать")

    def _toggle_container(self):
        use_container = self._container_var.get()
        if self._on_container_toggle:
            self._on_container_toggle(use_container)

        if use_container:
            self._docker_block.pack(fill="x", pady=(0, 10))
            if self._repo_data:
                self._fill_docker_fields(self._repo_data)
        else:
            self._docker_block.pack_forget()

    def _start_analyze(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showwarning("Ошибка", "Введите URL репозитория.")
            return
        error = self._validate_github_url(url)
        if error:
            self._status_label.configure(text=f"Ошибка: {error}", text_color="red")
            messagebox.showwarning("Некорректная ссылка", error)
            return
        token = self._token_entry.get().strip() if self._is_private_var.get() else None
        if self._is_private_var.get() and not token:
            messagebox.showwarning("Ошибка", "Введите GitHub Personal Access Token.")
            return
        self._analyze_btn.configure(state="disabled", text="Анализирую...")
        self._remove_repo_btn.configure(state="disabled")
        self._status_label.configure(text="Подключаюсь к GitHub...", text_color="gray")
        threading.Thread(target=self._analyze_worker, args=(url, token), daemon=True).start()

    @staticmethod
    def _validate_github_url(url: str) -> str | None:
        if not re.match(
            r"^https?://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$",
            url,
        ):
            return "Ссылка некорректна. Используйте формат https://github.com/user/repo"
        return None

    def _analyze_worker(self, url, access_token=None):
        try:
            data = analyze_repo(url, access_token=access_token)
            self.after(0, lambda data=data: self._on_analyze_done(data))
        except Exception as e:
            error = str(e)
            self.after(0, lambda error=error: self._on_analyze_error(error))

    def _on_analyze_done(self, data):
        self._repo_data = data
        self._env_values = {}
        self._db_values = {}
        if self._on_repo_ready:
            self._on_repo_ready(True)
        if (data.get("has_dockerfile") or data.get("has_compose")) and not self._container_var.get():
            self._container_var.set(True)
            if self._on_container_toggle:
                self._on_container_toggle(True)

        self._analyze_btn.configure(state="normal", text="Анализировать")
        self._remove_repo_btn.configure(state="normal")
        self._status_label.configure(
            text=f"{data['owner']}/{data['repo']} проанализирован.",
            text_color="green"
        )

        if not self._project_name.get():
            self._project_name.insert(0, data["repo"])
        self._deploy_path.delete(0, "end")
        self._deploy_path.insert(0, f"/opt/{data['repo']}")

        if self._container_var.get():
            self._docker_block.pack(fill="x", pady=(0, 10))
            self._fill_docker_fields(data)

        env_vars = data.get("env_vars", {})
        if env_vars:
            self._env_section.pack(fill="x", pady=(10, 0))
            names = ", ".join(env_vars.keys())
            self._env_info.configure(
                text=f"Найдено {len(env_vars)} переменных: {names}\n"
                     "Необходимо заполнить перед генерацией cloud-init."
            )
            self._env_status.configure(text="Переменные не заполнены.", text_color="orange")
            self._build_env_fields(env_vars)
        else:
            self._clear_env_fields()
            self._env_section.pack_forget()

        self._build_db_fields()

    def _on_analyze_error(self, error):
        self._analyze_btn.configure(state="normal", text="Анализировать")
        self._remove_repo_btn.configure(state="normal" if self._repo_data else "disabled")
        self._status_label.configure(text=f"Ошибка: {error}", text_color="red")

    def _remove_repo(self):
        self._repo_data = None
        self._env_values = {}
        self._db_values = {}

        self._url_entry.delete(0, "end")
        self._is_private_var.set(False)
        self._token_entry.delete(0, "end")
        self._token_visible = False
        self._token_entry.configure(show="*")
        self._toggle_token_btn.configure(text="Показать")
        self._token_row.pack_forget()
        self._private_frame.pack_forget()
        self._project_name.delete(0, "end")
        self._deploy_path.delete(0, "end")
        self._deploy_path.insert(0, "/opt/app")

        self._container_var.set(False)
        self._docker_block.pack_forget()
        self._dockerfile_info.configure(text="")
        self._compose_info.configure(text="")
        self._set_textbox(self._dockerfile_text, "")
        self._set_textbox(self._compose_text, "")

        self._clear_env_fields()
        self._env_section.pack_forget()
        self._env_info.configure(text="")
        self._env_status.configure(text="")

        self._clear_db_fields()
        self._db_section.pack_forget()
        self._db_info.configure(text="")
        self._db_status.configure(text="")

        if self._on_repo_ready:
            self._on_repo_ready(False)
        if self._on_container_toggle:
            self._on_container_toggle(False)

        self._remove_repo_btn.configure(state="disabled")
        self._analyze_btn.configure(state="normal", text="Анализировать")
        self._status_label.configure(text="Репозиторий удалён.", text_color="gray")

    def _fill_docker_fields(self, data):
        if data["has_dockerfile"]:
            self._dockerfile_info.configure(
                text="Dockerfile найден в репозитории.", text_color="green")
            content = data["files_content"].get("Dockerfile", "")
            self._set_textbox(self._dockerfile_text, content)
        else:
            self._dockerfile_info.configure(
                text="Не найден — сгенерирован автоматически. Можно отредактировать.",
                text_color="orange")
            self._set_textbox(self._dockerfile_text,
                generate_dockerfile(data["python_version"], data["main_file"] or "main.py"))

        if data["has_compose"]:
            self._compose_info.configure(
                text="docker-compose.yml найден.", text_color="green")
            content = (
                data["files_content"].get("docker-compose.yml")
                or data["files_content"].get("docker-compose.yaml")
                or ""
            )
            self._set_textbox(self._compose_text, content)
        else:
            self._compose_info.configure(
                text="Не найден — сгенерирован автоматически.", text_color="orange")
            self._set_textbox(self._compose_text,
                generate_compose(
                    project_name=self._project_name.get() or data["repo"],
                    ports=data["ports"],
                    extra_services=data["extra_services"],
                    has_env=bool(data.get("env_vars")),
                    db_vars=self._collect_db_values(),
                ))

    def _clear_env_fields(self):
        for widget in self._env_fields_frame.winfo_children():
            widget.destroy()
        self._env_entries = {}
        self._env_error_labels = {}
        self._env_values = {}

    def _clear_db_fields(self):
        for widget in self._db_fields_frame.winfo_children():
            widget.destroy()
        self._db_entries = {}
        self._db_error_labels = {}
        self._db_required = {}
        self._db_values = {}

    def _get_db_field_specs(self) -> list[tuple[str, str, bool]]:
        if not self._repo_data:
            return []

        extra_services = self._repo_data.get("extra_services", [])
        if not extra_services:
            return []

        app_env_names = set(self._repo_data.get("env_vars", {}).keys())
        specs = []
        seen = set()
        for service in extra_services:
            for name, default, required in DB_VAR_SPECS.get(service, []):
                if name in app_env_names or name in seen:
                    continue
                specs.append((name, default, required))
                seen.add(name)
        return specs

    def _build_db_fields(self):
        self._clear_db_fields()
        specs = self._get_db_field_specs()
        if not specs:
            self._db_section.pack_forget()
            return

        services = ", ".join(self._repo_data.get("extra_services", []))
        self._db_section.pack(fill="x", pady=(10, 0))
        self._db_info.configure(
            text=(
                f"Обнаружены сервисы: {services}. "
                "Эти значения используются только для инициализации БД."
            )
        )

        for name, default, required in specs:
            row = ctk.CTkFrame(self._db_fields_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            row.columnconfigure(1, weight=1)

            name_box = ctk.CTkFrame(row, fg_color="transparent", width=210)
            name_box.grid(row=0, column=0, sticky="w", padx=(0, 10))
            name_box.grid_propagate(False)

            ctk.CTkLabel(
                name_box,
                text=name,
                font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                name_box,
                text="обязательно" if required else "опционально / значение по умолчанию",
                font=ctk.CTkFont(size=10),
                text_color=self._env_warning_border if required else "gray",
                anchor="w",
            ).pack(anchor="w")

            entry = ctk.CTkEntry(
                row,
                placeholder_text="значение",
                border_color=self._env_default_border,
                border_width=2,
            )
            if default:
                entry.insert(0, default)
            entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            entry.bind("<KeyRelease>", lambda _event, var_name=name: self._on_db_field_change(var_name))
            self._db_entries[name] = entry
            self._db_required[name] = required

            error_label = ctk.CTkLabel(
                row,
                text="",
                width=210,
                anchor="w",
                text_color=self._env_warning_border,
                font=ctk.CTkFont(size=11),
            )
            error_label.grid(row=0, column=2, sticky="w")
            self._db_error_labels[name] = error_label

        self._refresh_db_status()
        self._refresh_generated_compose()

    def _build_env_fields(self, env_vars_types: dict):
        self._clear_env_fields()
        type_color = {"str": "#5dade2", "int": "#58d68d", "float": "#f39c12"}
        type_label = {"str": "строка", "int": "числовой", "float": "дробный"}

        for row_index, (var_name, var_type) in enumerate(env_vars_types.items()):
            row = ctk.CTkFrame(self._env_fields_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            row.columnconfigure(1, weight=1)

            name_box = ctk.CTkFrame(row, fg_color="transparent", width=210)
            name_box.grid(row=0, column=0, sticky="w", padx=(0, 10))
            name_box.grid_propagate(False)

            ctk.CTkLabel(
                name_box,
                text=var_name,
                font=ctk.CTkFont(family="Courier", size=13, weight="bold"),
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                name_box,
                text=f"тип: {type_label.get(var_type, var_type)}",
                font=ctk.CTkFont(size=10),
                text_color=type_color.get(var_type, "gray"),
                anchor="w",
            ).pack(anchor="w")

            entry = ctk.CTkEntry(
                row,
                placeholder_text="значение",
                border_color=self._env_default_border,
                border_width=2,
            )
            entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            entry.bind("<KeyRelease>", lambda _event, name=var_name: self._on_env_field_change(name))
            self._env_entries[var_name] = entry

            error_label = ctk.CTkLabel(
                row,
                text="",
                width=210,
                anchor="w",
                text_color=self._env_warning_border,
                font=ctk.CTkFont(size=11),
            )
            error_label.grid(row=0, column=2, sticky="w")
            self._env_error_labels[var_name] = error_label

        self._refresh_env_status()

    def _format_error_text(self, var_type: str) -> str:
        if var_type == "int":
            return "Требуется формат: числовой"
        if var_type == "float":
            return "Требуется формат: дробный"
        return ""

    def _validate_env_field(self, name: str, require_value: bool = False) -> str | None:
        if not self._repo_data or name not in self._env_entries:
            return None

        entry = self._env_entries[name]
        label = self._env_error_labels[name]
        var_type = self._repo_data.get("env_vars", {}).get(name, "str")
        value = entry.get().strip()

        error = None
        if not value:
            if require_value:
                error = "Обязательное поле"
        elif var_type == "int":
            try:
                int(value)
            except ValueError:
                error = self._format_error_text(var_type)
        elif var_type == "float":
            try:
                float(value)
            except ValueError:
                error = self._format_error_text(var_type)

        if error:
            entry.configure(border_color=self._env_warning_border)
            label.configure(text=error)
        else:
            entry.configure(border_color=self._env_default_border)
            label.configure(text="")
        return error

    def _on_env_field_change(self, name: str):
        self._validate_env_field(name)
        self._refresh_env_status()

    def _refresh_env_status(self):
        if not self._env_entries:
            self._env_status.configure(text="")
            return

        _, invalid = self._validate_env_fields(require_values=False)
        has_empty = any(not entry.get().strip() for entry in self._env_entries.values())

        if invalid:
            self._env_values = self._collect_env_values()
            self._env_status.configure(text="Некорректно заполнены переменные.", text_color="orange")
        elif has_empty:
            self._env_values = self._collect_env_values()
            self._env_status.configure(text="Переменные не заполнены.", text_color="orange")
        else:
            self._env_values = self._collect_env_values()
            total = len(self._env_entries)
            self._env_status.configure(text=f"Заполнено {total} из {total} переменных.", text_color="green")

    def _validate_env_fields(self, require_values: bool = False) -> tuple[list[str], list[str]]:
        missing = []
        invalid = []
        for name, entry in self._env_entries.items():
            value = entry.get().strip()
            error = self._validate_env_field(name, require_values)
            if error == "Обязательное поле":
                missing.append(name)
            elif error:
                invalid.append(name)
        return missing, invalid

    def _collect_env_values(self) -> dict:
        return {
            name: entry.get().strip()
            for name, entry in self._env_entries.items()
            if entry.get().strip()
        }

    def _validate_db_field(self, name: str, require_value: bool = False) -> str | None:
        if name not in self._db_entries:
            return None

        entry = self._db_entries[name]
        label = self._db_error_labels[name]
        value = entry.get().strip()
        required = self._db_required.get(name, False)

        error = None
        if required and require_value and not value:
            error = "Обязательное поле"

        if error:
            entry.configure(border_color=self._env_warning_border)
            label.configure(text=error)
        else:
            entry.configure(border_color=self._env_default_border)
            label.configure(text="")
        return error

    def _validate_db_fields(self, require_values: bool = False) -> list[str]:
        missing = []
        for name in self._db_entries:
            error = self._validate_db_field(name, require_values)
            if error:
                missing.append(name)
        return missing

    def _collect_db_values(self) -> dict:
        return {
            name: entry.get().strip()
            for name, entry in self._db_entries.items()
            if entry.get().strip()
        }

    def _on_db_field_change(self, name: str):
        self._validate_db_field(name)
        self._refresh_db_status()
        self._refresh_generated_compose()

    def _refresh_db_status(self):
        if not self._db_entries:
            self._db_status.configure(text="")
            return

        missing_required = [
            name for name, entry in self._db_entries.items()
            if self._db_required.get(name) and not entry.get().strip()
        ]
        self._db_values = self._collect_db_values()

        if missing_required:
            self._db_status.configure(text="Обязательные параметры БД не заполнены.", text_color="orange")
        else:
            total = len(self._db_values)
            self._db_status.configure(text=f"Параметры БД готовы: {total}.", text_color="green")

    def _refresh_generated_compose(self):
        if not self._repo_data or not self._container_var.get():
            return
        if self._repo_data.get("has_compose"):
            return

        self._set_textbox(
            self._compose_text,
            generate_compose(
                project_name=self._project_name.get() or self._repo_data["repo"],
                ports=self._repo_data["ports"],
                extra_services=self._repo_data["extra_services"],
                has_env=bool(self._repo_data.get("env_vars")),
                db_vars=self._collect_db_values(),
            )
        )

    def _open_env_dialog(self):
        if not self._repo_data:
            return
        env_vars_types = self._repo_data.get("env_vars", {})
        if not env_vars_types:
            return

        dialog = EnvVarsDialog(self, env_vars_types)
        self.wait_window(dialog)

        if dialog.result is not None:
            self._env_values = dialog.result
            n = len(self._env_values)
            self._env_status.configure(
                text=f"Заполнено {n} из {n} переменных.",
                text_color="green"
            )

    @staticmethod
    def _set_textbox(tb, text):
        tb.delete("1.0", "end")
        tb.insert("1.0", text)

    def _copy_textbox(self, tb, label):
        text = tb.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        label.configure(text="Скопировано")
        self.after(2500, lambda: label.configure(text=""))

    def _make_github_config(self):
        config = {
            "project_name":  self._project_name.get() or self._repo_data["repo"],
            "repo_url":      self._url_entry.get().strip(),
            "deploy_path":   self._deploy_path.get() or f"/opt/{self._repo_data['repo']}",
            "env_vars":      self._env_values,
            "db_vars":       self._db_values,
            "extra_services": self._repo_data.get("extra_services", []),
            "use_container": self._container_var.get(),
            "is_private":    self._is_private_var.get(),
            "access_token":   self._token_entry.get().strip() if self._is_private_var.get() else None,
        }

        if self._container_var.get():
            config["dockerfile_generated"] = not self._repo_data.get("has_dockerfile", False)
            config["compose_generated"] = not self._repo_data.get("has_compose", False)
            if config["dockerfile_generated"]:
                config["dockerfile"] = self._dockerfile_text.get("1.0", "end").strip()
            if config["compose_generated"]:
                config["compose"] = self._compose_text.get("1.0", "end").strip()

        return config

    def get_github_config(self):
        if not self._repo_data:
            return None

        env_vars_types = self._repo_data.get("env_vars", {})
        if env_vars_types:
            missing, invalid = self._validate_env_fields(require_values=True)
            if missing:
                self._env_status.configure(text="Переменные не заполнены.", text_color="orange")
                raise ValueError(f"Не заполнены переменные окружения: {', '.join(missing)}.")
            if invalid:
                self._env_status.configure(text="Некорректно заполнены переменные.", text_color="orange")
                raise ValueError(f"Некорректно заполнены переменные окружения: {', '.join(invalid)}.")
            self._env_values = self._collect_env_values()
            self._refresh_env_status()

        db_missing = self._validate_db_fields(require_values=True)
        if db_missing:
            self._db_status.configure(text="Обязательные параметры БД не заполнены.", text_color="orange")
            raise ValueError(f"Не заполнены обязательные параметры базы данных: {', '.join(db_missing)}.")
        self._db_values = self._collect_db_values()
        self._refresh_db_status()

        return self._make_github_config()

    def has_repo(self):
        return self._repo_data is not None

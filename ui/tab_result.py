import customtkinter as ctk
from tkinter import messagebox

from cloudinit_generator import build_cloud_init

_RUNCMD_DISPLAY_NAMES = {
    "__docker__":         "Docker Engine + Docker Compose",
    "__yandex-browser__": "Yandex Browser",
    "__google-chrome__":  "Google Chrome",
    "__opera__":          "Opera",
    "__ms-edge__":        "Microsoft Edge",
    "__vscode__":         "VS Code",
    "__notepadqq__":      "Notepadqq",
}


class ResultTab(ctk.CTkFrame):
    def __init__(self, master, get_config_fn):
        super().__init__(master, fg_color="transparent")
        self._get_config = get_config_fn
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Генерация cloud-init",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            self,
            text="Нажмите «Создать» — будет сгенерирован готовый cloud-config файл.\n"
                 "Вставьте его в поле Cloud-Init при создании сервера на Timeweb Cloud.",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self._summary_frame = ctk.CTkFrame(self)
        self._summary_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            self._summary_frame, text="Сводка конфигурации",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(10, 6))

        self._summary_label = ctk.CTkLabel(
            self._summary_frame,
            text="Нажмите «Создать» чтобы увидеть сводку.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="left",
            anchor="w",
            wraplength=820,
        )
        self._summary_label.pack(anchor="w", padx=15, pady=(0, 10))

        ctk.CTkButton(
            self,
            text="Создать cloud-init",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            command=self._generate
        ).pack(padx=20, pady=(0, 12), fill="x")

        ctk.CTkLabel(
            self, text="cloud-config.yaml:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=20)

        self._output = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Courier", size=11),
            state="disabled"
        )
        self._output.pack(fill="both", expand=True, padx=20, pady=(5, 5))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkButton(
            btn_row, text="Скопировать в буфер обмена",
            command=self._copy
        ).pack(side="left")

        self._copy_label = ctk.CTkLabel(
            btn_row, text="", text_color="green", font=ctk.CTkFont(size=12))
        self._copy_label.pack(side="left", padx=10)

    def _build_summary(self, config: dict) -> str:
        lines = []

        pkgs = config.get("packages", [])
        if pkgs:
            lines.append(f"Пакеты (apt): {', '.join(pkgs)}")

        runcmd_blocks = config.get("runcmd_packages", [])
        if runcmd_blocks:
            from ui.tab_packages import RUNCMD_PACKAGES
            marker_by_block = {tuple(v): k for k, v in RUNCMD_PACKAGES.items()}
            app_names = []
            for block in runcmd_blocks:
                marker = marker_by_block.get(tuple(block))
                name = _RUNCMD_DISPLAY_NAMES.get(marker, marker or "неизвестно")
                app_names.append(name)
            lines.append(f"Приложения (сторонние репо): {', '.join(app_names)}")

        users = config.get("users", [])
        if users:
            user_strs = []
            for u in users:
                tags = []
                if u.get("sudo"):
                    tags.append("sudo")
                if "docker" in u.get("groups", []):
                    tags.append("docker")
                suffix = f" [{', '.join(tags)}]" if tags else ""
                user_strs.append(f"{u['name']}{suffix}")
            lines.append(f"Пользователи: {', '.join(user_strs)}")

        ssh_port = config.get("ssh_port")
        if ssh_port and ssh_port != 22:
            lines.append(f"SSH порт: {ssh_port} (ufw настроен автоматически)")

        tz = config.get("timezone")
        if tz:
            lines.append(f"Часовой пояс: {tz}")

        gh = config.get("github")
        if gh:
            label = "Docker-приложение" if gh.get("use_container") else "GitHub-приложение"
            lines.append(
                f"{label}: {gh.get('project_name', 'app')}"
                f" -> {gh.get('deploy_path', '/opt/app')}"
            )
            if gh.get("repo_url"):
                lines.append(f"   Git clone: {gh['repo_url']}")
            if gh.get("env_vars"):
                env_keys = ", ".join(gh["env_vars"].keys())
                lines.append(f"   Переменные окружения: {env_keys}")

        if not lines:
            return "Конфигурация пуста — ничего не выбрано."

        numbered = [f"{i + 1}. {line}" for i, line in enumerate(lines)]
        return "\n".join(numbered)

    def _generate(self):
        try:
            config = self._get_config()
            yaml_text = build_cloud_init(config)

            summary = self._build_summary(config)
            self._summary_label.configure(text=summary, text_color="white")

            self._output.configure(state="normal")
            self._output.delete("1.0", "end")
            self._output.insert("1.0", yaml_text)
            self._output.configure(state="disabled")
            self._copy_label.configure(text="")
        except ValueError as e:
            messagebox.showwarning("Не все данные заполнены", str(e))
        except Exception as e:
            messagebox.showerror("Ошибка генерации", str(e))

    def _copy(self):
        text = self._output.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self._copy_label.configure(text="Скопировано!")
        self.after(3000, lambda: self._copy_label.configure(text=""))

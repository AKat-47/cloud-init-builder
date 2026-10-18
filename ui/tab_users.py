import customtkinter as ctk
from tkinter import messagebox


class UsersTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._users: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Управление пользователями",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(
            self, text="Добавьте пользователей, которые будут созданы при первом запуске сервера.",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(form, text="Новый пользователь", font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 5))

        grid = ctk.CTkFrame(form, fg_color="transparent")
        grid.pack(fill="x", padx=15, pady=(0, 10))
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(3, weight=1)

        ctk.CTkLabel(grid, text="Имя:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        self._name_entry = ctk.CTkEntry(grid, placeholder_text="username")
        self._name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 20), pady=5)

        ctk.CTkLabel(grid, text="Пароль:").grid(row=0, column=2, sticky="w", padx=(0, 8), pady=5)
        self._pass_entry = ctk.CTkEntry(grid, placeholder_text="пароль", show="*")
        self._pass_entry.grid(row=0, column=3, sticky="ew", pady=5)

        ctk.CTkLabel(grid, text="Публичный SSH-ключ:").grid(
            row=1, column=0, sticky="nw", padx=(0, 8), pady=5)
        self._ssh_key_text = ctk.CTkTextbox(grid, height=72)
        self._ssh_key_text.grid(row=1, column=1, columnspan=3, sticky="ew", pady=5)

        self._sudo_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(grid, text="Права sudo", variable=self._sudo_var).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=5)

        self._docker_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(grid, text="Группа docker", variable=self._docker_var).grid(
            row=2, column=2, columnspan=2, sticky="w", pady=5)

        ctk.CTkButton(form, text="Добавить пользователя", command=self._add_user).pack(
            anchor="e", padx=15, pady=(0, 12))

        ctk.CTkLabel(self, text="Добавленные пользователи:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=20, pady=(0, 5))

        self._list_frame = ctk.CTkScrollableFrame(self, height=200)
        self._list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._refresh_list()

    def _add_user(self):
        name = self._name_entry.get().strip()
        password = self._pass_entry.get()
        ssh_keys = [
            line.strip()
            for line in self._ssh_key_text.get("1.0", "end").splitlines()
            if line.strip()
        ]

        if not name:
            messagebox.showwarning("Ошибка", "Введите имя пользователя.")
            return
        if not password:
            messagebox.showwarning("Ошибка", "Введите пароль.")
            return
        if any(u["name"] == name for u in self._users):
            messagebox.showwarning("Ошибка", f"Пользователь '{name}' уже добавлен.")
            return

        groups = []
        if self._sudo_var.get():
            groups.append("sudo")
        if self._docker_var.get():
            groups.append("docker")

        user = {
            "name": name,
            "password": password,
            "sudo": self._sudo_var.get(),
            "groups": groups,
            "shell": "/bin/bash",
        }
        if ssh_keys:
            user["ssh_authorized_keys"] = ssh_keys

        self._users.append(user)

        self._name_entry.delete(0, "end")
        self._pass_entry.delete(0, "end")
        self._ssh_key_text.delete("1.0", "end")
        self._sudo_var.set(False)
        self._docker_var.set(False)
        self._refresh_list()

    def _remove_user(self, name: str):
        self._users = [u for u in self._users if u["name"] != name]
        self._refresh_list()

    def _refresh_list(self):
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not self._users:
            ctk.CTkLabel(self._list_frame, text="Пользователи не добавлены.",
                         text_color="gray").pack(pady=20)
            return

        for user in self._users:
            row = ctk.CTkFrame(self._list_frame)
            row.pack(fill="x", pady=3)

            tags = []
            if user["sudo"]:
                tags.append("sudo")
            if "docker" in user.get("groups", []):
                tags.append("docker")
            if user.get("ssh_authorized_keys"):
                tags.append("ssh-key")
            tag_str = f"  [{', '.join(tags)}]" if tags else ""

            ctk.CTkLabel(
                row,
                text=f"  {user['name']}{tag_str}",
                font=ctk.CTkFont(size=13)
            ).pack(side="left", padx=10, pady=8)

            ctk.CTkButton(
                row, text="Удалить", width=80, fg_color="#c0392b", hover_color="#922b21",
                command=lambda n=user["name"]: self._remove_user(n)
            ).pack(side="right", padx=10, pady=5)

    def get_users(self) -> list[dict]:
        return self._users

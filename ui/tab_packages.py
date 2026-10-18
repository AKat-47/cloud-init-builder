import customtkinter as ctk

from docker_generator import DOCKER_INSTALL_COMMANDS

PACKAGE_CATALOG = {
    "Рабочий стол (RDP)": [
        ("XFCE4 (графическое окружение)", "xfce4"),
        ("XRDP (удалённый рабочий стол)", "xrdp"),
        ("XFCE Terminal", "xfce4-terminal"),
        ("Файловый менеджер Thunar", "thunar"),
    ],
    "Браузеры": [
        ("Firefox", "firefox"),
        ("Yandex Browser", "__yandex-browser__"),
        ("Google Chrome", "__google-chrome__"),
        ("Opera", "__opera__"),
        ("Microsoft Edge", "__ms-edge__"),
    ],
    "Приложения": [
        ("Telegram Desktop", "telegram-desktop"),
        ("VS Code", "__vscode__"),
        ("Notepadqq", "__notepadqq__"),
    ],
    "Утилиты": [
        ("xz-utils", "xz-utils"),
        ("unzip", "unzip"),
        ("curl", "curl"),
        ("wget", "wget"),
        ("git", "git"),
        ("htop", "htop"),
        ("vim", "vim"),
        ("nano", "nano"),
        ("net-tools", "net-tools"),
        ("build-essential", "build-essential"),
        ("dkms", "dkms"),
        ("linux-headers-generic", "linux-headers-generic"),
        ("software-properties-common", "software-properties-common"),
        ("gnupg", "gnupg"),
        ("ca-certificates", "ca-certificates"),
        ("python3-passlib", "python3-passlib"),
    ],
    "Веб-серверы и окружение": [
        ("nginx", "nginx"),
        ("Python3 + pip", "python3 python3-pip"),
        ("Node.js (LTS)", "nodejs npm"),
        ("Docker Engine + Docker Compose", "__docker__"),
    ],
    "Безопасность": [
        ("ufw (фаервол)", "ufw"),
        ("fail2ban", "fail2ban"),
    ],
}

BASIC_PACKAGE_SET = {
    "xfce4",
    "xrdp",
    "telegram-desktop",
    "__notepadqq__",
    "__google-chrome__",
    "__ms-edge__",
    "firefox",
    "unzip",
    "curl",
    "wget",
    "net-tools",
    "nano",
}

RUNCMD_PACKAGES: dict[str, list[str]] = {
    "__docker__": DOCKER_INSTALL_COMMANDS,
    "__yandex-browser__": [
        "curl -fsSL https://repo.yandex.ru/yandex-browser/YANDEX-BROWSER-KEY.GPG"
        " | gpg --dearmor -o /usr/share/keyrings/yandex-browser.gpg",
        'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/yandex-browser.gpg]'
        ' https://repo.yandex.ru/yandex-browser/deb stable main"'
        " > /etc/apt/sources.list.d/yandex-browser.list",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y yandex-browser-stable",
    ],
    "__google-chrome__": [
        "curl -fsSL https://dl.google.com/linux/linux_signing_key.pub"
        " | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg",
        'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg]'
        ' https://dl.google.com/linux/chrome/deb/ stable main"'
        " > /etc/apt/sources.list.d/google-chrome.list",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y google-chrome-stable",
    ],
    "__opera__": [
        "curl -fsSL https://deb.opera.com/archive.key"
        " | gpg --dearmor -o /usr/share/keyrings/opera.gpg",
        'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/opera.gpg]'
        ' https://deb.opera.com/opera-stable/ stable non-free"'
        " > /etc/apt/sources.list.d/opera.list",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y opera-stable",
    ],
    "__ms-edge__": [
        "curl -fsSL https://packages.microsoft.com/keys/microsoft.asc"
        " | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg",
        'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg]'
        ' https://packages.microsoft.com/repos/edge stable main"'
        " > /etc/apt/sources.list.d/microsoft-edge.list",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y microsoft-edge-stable",
    ],
    "__vscode__": [
        "curl -fsSL https://packages.microsoft.com/keys/microsoft.asc"
        " | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg",
        'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg]'
        ' https://packages.microsoft.com/repos/code stable main"'
        " > /etc/apt/sources.list.d/vscode.list",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y code",
    ],
    "__notepadqq__": [
        "add-apt-repository -y ppa:notepadqq-team/notepadqq",
        "apt-get update -qq",
        "DEBIAN_FRONTEND=noninteractive apt-get install -y notepadqq",
    ],
}


class PackagesTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._vars: dict[str, ctk.BooleanVar] = {}
        self._basic_set_var = ctk.BooleanVar(value=False)
        self._select_all_var = ctk.BooleanVar(value=False)
        self._syncing_presets = False
        self._custom_entry = None
        self._custom_list: list[str] = []
        self._custom_listbox_frame = None
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Выберите программное обеспечение для установки",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(
            self, text="Выбранные пакеты будут установлены через apt при первом запуске сервера.",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        scroll = ctk.CTkScrollableFrame(self, label_text="")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        preset_row = ctk.CTkFrame(scroll, fg_color="transparent")
        preset_row.pack(fill="x", pady=(0, 8))

        ctk.CTkCheckBox(
            preset_row,
            text="Базовый набор",
            variable=self._basic_set_var,
            command=self._toggle_basic_set,
        ).pack(side="left", padx=(0, 24))

        ctk.CTkCheckBox(
            preset_row,
            text="Выбрать все",
            variable=self._select_all_var,
            command=self._toggle_select_all,
        ).pack(side="left")

        for category, items in PACKAGE_CATALOG.items():
            cat_label = ctk.CTkLabel(
                scroll, text=category,
                font=ctk.CTkFont(size=13, weight="bold")
            )
            cat_label.pack(anchor="w", pady=(12, 2))

            for display_name, pkg in items:
                var = ctk.BooleanVar(value=False)
                self._vars[pkg] = var
                cb = ctk.CTkCheckBox(
                    scroll,
                    text=display_name,
                    variable=var,
                    command=self._refresh_preset_state,
                )
                cb.pack(anchor="w", padx=15, pady=2)

        ctk.CTkLabel(
            scroll, text="Дополнительные пакеты",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", pady=(12, 2))

        ctk.CTkLabel(
            scroll, text="Введите apt-имя пакета и нажмите «Добавить»:",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=15)

        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=4)

        self._custom_entry = ctk.CTkEntry(row, placeholder_text="например: htop")
        self._custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(row, text="Добавить", width=90, command=self._add_custom).pack(side="left")

        self._custom_listbox_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._custom_listbox_frame.pack(fill="x", padx=15)

    def _add_custom(self):
        pkg = (self._custom_entry.get() or "").strip()
        if not pkg or pkg in self._custom_list:
            return
        self._custom_list.append(pkg)
        self._custom_entry.delete(0, "end")
        self._refresh_custom_list()

    def _refresh_custom_list(self):
        for w in self._custom_listbox_frame.winfo_children():
            w.destroy()
        for pkg in self._custom_list:
            row = ctk.CTkFrame(self._custom_listbox_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"  {pkg}", font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkButton(
                row, text="x", width=28, height=24, fg_color="transparent",
                text_color="gray", hover_color="#3a3a3a",
                command=lambda p=pkg: self._remove_custom(p)
            ).pack(side="right")

    def _remove_custom(self, pkg: str):
        self._custom_list.remove(pkg)
        self._refresh_custom_list()

    def _toggle_basic_set(self):
        if self._syncing_presets:
            return

        selected = self._basic_set_var.get()
        was_select_all = self._select_all_var.get()
        self._syncing_presets = True
        try:
            self._select_all_var.set(False)
            if selected and was_select_all:
                for var in self._vars.values():
                    var.set(False)
            for package in BASIC_PACKAGE_SET:
                self._set_package_selected(package, selected, refresh=False)
        finally:
            self._syncing_presets = False
        self._refresh_preset_state()

    def _toggle_select_all(self):
        if self._syncing_presets:
            return

        selected = self._select_all_var.get()
        self._syncing_presets = True
        try:
            self._basic_set_var.set(False)
            for var in self._vars.values():
                var.set(selected)
        finally:
            self._syncing_presets = False
        self._refresh_preset_state()

    def _refresh_preset_state(self):
        if self._syncing_presets:
            return

        selected = {pkg for pkg, var in self._vars.items() if var.get()}
        all_selected = bool(self._vars) and len(selected) == len(self._vars)
        basic_selected = BASIC_PACKAGE_SET.issubset(selected) and not all_selected

        self._syncing_presets = True
        try:
            self._select_all_var.set(all_selected)
            self._basic_set_var.set(basic_selected)
        finally:
            self._syncing_presets = False

    def _set_package_selected(self, package: str, selected: bool, refresh: bool = True):
        var = self._vars.get(package)
        if var is not None:
            var.set(selected)
        if refresh:
            self._refresh_preset_state()

    def set_git_selected(self, selected: bool):
        self._set_package_selected("git", selected)

    def set_docker_selected(self, selected: bool):
        self._set_package_selected("__docker__", selected)

    def get_packages(self) -> list[str]:
        result = []
        seen = set()
        for pkg, var in self._vars.items():
            if var.get() and not pkg.startswith("__"):
                for package_name in pkg.split():
                    if package_name not in seen:
                        result.append(package_name)
                        seen.add(package_name)
        for package_name in self._custom_list:
            if package_name not in seen:
                result.append(package_name)
                seen.add(package_name)
        return result

    def get_runcmd_packages(self) -> list[list[str]]:
        result = []
        for pkg, var in self._vars.items():
            if var.get() and pkg in RUNCMD_PACKAGES:
                result.append(RUNCMD_PACKAGES[pkg])
        return result

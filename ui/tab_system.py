import customtkinter as ctk

TIMEZONES = [
    "Europe/Moscow",
    "Europe/Kaliningrad",
    "Europe/Samara",
    "Asia/Yekaterinburg",
    "Asia/Omsk",
    "Asia/Krasnoyarsk",
    "Asia/Irkutsk",
    "Asia/Yakutsk",
    "Asia/Vladivostok",
    "Asia/Magadan",
    "Asia/Kamchatka",
    "Europe/Kiev",
    "Europe/Minsk",
    "Asia/Almaty",
    "Asia/Tashkent",
    "Asia/Tbilisi",
    "Asia/Baku",
    "Asia/Yerevan",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Rome",
    "Europe/Madrid",
    "Europe/Warsaw",
    "Europe/Amsterdam",
    "Europe/Stockholm",
    "Europe/Helsinki",
    "Europe/Istanbul",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Bangkok",
    "Asia/Singapore",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Pacific/Auckland",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "UTC",
]

MIN_SSH_PORT = 1024
MAX_SSH_PORT = 49151
COMMON_SERVICE_PORTS = {
    2049: "NFS",
    3000: "Node.js / dev server",
    3306: "MySQL",
    5000: "Flask / dev server",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8000: "Django / dev server",
    8080: "HTTP alternate",
    8443: "HTTPS alternate",
    27017: "MongoDB",
}


class SystemTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self, text="Системные настройки",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))
        ctk.CTkLabel(
            self,
            text="Настройки применяются при первом запуске сервера через cloud-init.",
            font=ctk.CTkFont(size=12), text_color="gray"
        ).pack(anchor="w", padx=20, pady=(0, 20))

        ssh_frame = ctk.CTkFrame(self)
        ssh_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(ssh_frame, text="SSH", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 8))

        row = ctk.CTkFrame(ssh_frame, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 12))

        self._change_port_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row, text="Изменить порт SSH",
            variable=self._change_port_var,
            command=self._toggle_port
        ).pack(side="left")

        self._port_entry = ctk.CTkEntry(row, placeholder_text="22", width=80)
        self._port_entry.pack(side="left", padx=(15, 0))
        self._port_entry.insert(0, "22")
        self._port_entry.configure(state="disabled")
        self._port_entry.bind(
            "<KeyRelease>",
            lambda _event: self._validate_ssh_port(show_error=True, raise_error=False),
        )

        ctk.CTkLabel(
            ssh_frame,
            text=(
                "При смене порта программа автоматически настроит sshd и ufw. "
                f"Рекомендуемый диапазон: {MIN_SSH_PORT}-{MAX_SSH_PORT}."
            ),
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", padx=15, pady=(0, 4))

        self._port_error_label = ctk.CTkLabel(
            ssh_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#f1c40f",
        )
        self._port_error_label.pack(anchor="w", padx=15, pady=(0, 12))

        access_frame = ctk.CTkFrame(self)
        access_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(access_frame, text="Доступ", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 8))

        self._root_login_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            access_frame, text="Разрешить вход root по паролю (PermitRootLogin yes)",
            variable=self._root_login_var
        ).pack(anchor="w", padx=15, pady=(0, 5))

        self._password_auth_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            access_frame, text="Аутентификация по паролю (PasswordAuthentication yes)",
            variable=self._password_auth_var
        ).pack(anchor="w", padx=15, pady=(0, 12))

        tz_frame = ctk.CTkFrame(self)
        tz_frame.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(tz_frame, text="Часовой пояс", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=15, pady=(12, 8))

        tz_row = ctk.CTkFrame(tz_frame, fg_color="transparent")
        tz_row.pack(fill="x", padx=15, pady=(0, 12))

        self._tz_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(tz_row, text="Установить часовой пояс:",
                        variable=self._tz_var, command=self._toggle_tz).pack(side="left")

        self._tz_menu = ctk.CTkOptionMenu(tz_row, values=TIMEZONES, width=220, state="disabled")
        self._tz_menu.set("Europe/Moscow")
        self._tz_menu.pack(side="left", padx=(15, 0))

    def _toggle_port(self):
        state = "normal" if self._change_port_var.get() else "disabled"
        self._port_entry.configure(state=state)
        if self._change_port_var.get():
            self._validate_ssh_port(show_error=True, raise_error=False)
        else:
            self._port_error_label.configure(text="")
            self._port_entry.configure(border_color="#565b5e")

    def _toggle_tz(self):
        state = "normal" if self._tz_var.get() else "disabled"
        self._tz_menu.configure(state=state)

    def _validate_ssh_port(self, show_error: bool = False, raise_error: bool = True) -> int | None:
        raw_port = self._port_entry.get().strip()

        try:
            port = int(raw_port)
        except ValueError:
            message = "SSH-порт должен быть целым числом."
            if show_error:
                self._show_port_error(message)
            if raise_error:
                raise ValueError(message)
            return None

        if not MIN_SSH_PORT <= port <= MAX_SSH_PORT:
            message = f"SSH-порт должен быть в диапазоне {MIN_SSH_PORT}-{MAX_SSH_PORT}."
            if show_error:
                self._show_port_error(message)
            if raise_error:
                raise ValueError(message)
            return None

        service_name = COMMON_SERVICE_PORTS.get(port)
        if service_name:
            message = f"Порт {port} обычно используется сервисом {service_name}. Выберите другой SSH-порт."
            if show_error:
                self._show_port_error(message)
            if raise_error:
                raise ValueError(message)
            return None

        if show_error:
            self._port_error_label.configure(text="")
            self._port_entry.configure(border_color="#565b5e")
        return port

    def _show_port_error(self, message: str):
        self._port_error_label.configure(text=message)
        self._port_entry.configure(border_color="#f1c40f")

    def get_settings(self) -> dict:
        ssh_port = None
        if self._change_port_var.get():
            ssh_port = self._validate_ssh_port(show_error=True)

        timezone = None
        if self._tz_var.get():
            tz = self._tz_menu.get().strip()
            if tz:
                timezone = tz

        return {
            "ssh_port": ssh_port,
            "root_login": self._root_login_var.get(),
            "password_auth": self._password_auth_var.get(),
            "timezone": timezone,
        }

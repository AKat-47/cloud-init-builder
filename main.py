import sys
import customtkinter as ctk

sys.path.insert(0, ".")

from ui.tab_packages import PackagesTab
from ui.tab_users import UsersTab
from ui.tab_system import SystemTab
from ui.tab_github import GithubTab
from ui.tab_result import ResultTab


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Cloud-Init Builder")
        self.geometry("900x700")
        self.minsize(800, 600)

        header = ctk.CTkFrame(self, height=54, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="  Cloud-Init Builder",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            header,
            text="Автоматизация развёртывания серверов",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).pack(side="left", pady=10)

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)

        tabview.add("Пакеты")
        tabview.add("Пользователи")
        tabview.add("Система")
        tabview.add("GitHub / Docker")
        tabview.add("Результат")

        self.tab_packages = PackagesTab(tabview.tab("Пакеты"))
        self.tab_packages.pack(fill="both", expand=True)

        self.tab_users = UsersTab(tabview.tab("Пользователи"))
        self.tab_users.pack(fill="both", expand=True)

        self.tab_system = SystemTab(tabview.tab("Система"))
        self.tab_system.pack(fill="both", expand=True)

        self.tab_github = GithubTab(
            tabview.tab("GitHub / Docker"),
            on_container_toggle=self.tab_packages.set_docker_selected,
            on_repo_ready=self.tab_packages.set_git_selected,
        )
        self.tab_github.pack(fill="both", expand=True)

        self.tab_result = ResultTab(
            tabview.tab("Результат"),
            get_config_fn=self._collect_config,
        )
        self.tab_result.pack(fill="both", expand=True)
        self.bind_all("<Control-KeyPress>", self._handle_control_shortcut, add="+")

    def _handle_control_shortcut(self, event):
        key = (event.keysym or "").lower()
        if key in {"c", "v", "x", "a"}:
            return

        keycode = getattr(event, "keycode", None)
        actions = {
            67: "<<Copy>>",
            86: "<<Paste>>",
            88: "<<Cut>>",
            65: "<<SelectAll>>",
        }
        action = actions.get(keycode)
        if not action:
            return

        try:
            event.widget.event_generate(action)
            return "break"
        except Exception:
            return

    def _collect_config(self) -> dict:
        system = self.tab_system.get_settings()

        config = {
            "packages":        self.tab_packages.get_packages(),
            "runcmd_packages": self.tab_packages.get_runcmd_packages(),
            "users":           self.tab_users.get_users(),
            "ssh_port":        system.get("ssh_port"),
            "root_login":      system.get("root_login"),
            "password_auth":   system.get("password_auth"),
            "timezone":        system.get("timezone"),
            "github":          self.tab_github.get_github_config(),
        }
        return config


if __name__ == "__main__":
    app = App()
    app.mainloop()

import sys
import asyncio
import os
import re
import pty
import signal
import struct
import fcntl
import termios
import threading
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from collections import deque

if getattr(sys, 'frozen', False):
    sys.path.insert(0, sys._MEIPASS)

try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
    try:
        SSL_CONTEXT.load_default_locations()
    except Exception:
        SSL_CONTEXT = ssl._create_unverified_context()

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import (
    Header,
    Footer,
    Static,
    RichLog,
    Input,
    Label,
    Select,
    Button,
)
from textual.reactive import reactive
from textual.message import Message

from translator import translate, validate_pro_key, activate_by_email, ProConnectionError, LANGUAGE_NAMES, AI_AVAILABLE, get_ai_status
from knowledge_base import ensure_knowledge_base_exists
from themes import (
    APP_CSS,
    load_theme_preference,
    save_theme_preference,
    load_license_key,
    save_license_key,
    THEME_NAMES,
)

APP_VERSION = "1.3.0"

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[@-~]|\r")

STARTER_COMMANDS = [
    ("pwd", "See what folder you're currently in"),
    ("ls", "List files and folders here"),
    ("ls -la", "List ALL files with details (including hidden)"),
    ("echo 'Hello World!'", "Print a message to the screen"),
    ("date", "Show the current date and time"),
    ("whoami", "Show your username"),
    ("uname -a", "Show info about your operating system"),
    ("cat /etc/os-release", "Show which Linux/OS version you have"),
    ("df -h", "Show how much disk space you have"),
    ("free -h", "Show how much memory (RAM) is available"),
    ("env | head -5", "Show first 5 environment variables"),
    ("history", "Show your recent command history"),
    ("mkdir test_folder", "Create a new folder called test_folder"),
    ("touch test_file.txt", "Create an empty file called test_file.txt"),
    ("echo 'hello' > test_file.txt", "Write 'hello' into test_file.txt"),
    ("cat test_file.txt", "Read the contents of test_file.txt"),
    ("cp test_file.txt backup.txt", "Copy test_file.txt to backup.txt"),
    ("ls -la test_*", "List all files starting with 'test_'"),
    ("rm test_file.txt backup.txt", "Delete the test files"),
    ("rmdir test_folder", "Remove the test folder"),
    ("which python", "Find where Python is installed"),
    ("python --version", "Check your Python version"),
    ("pip list | head -10", "Show first 10 installed Python packages"),
    ("git status", "Check if you're in a git repository"),
    ("uptime", "Show how long the system has been running"),
]

HELP_TEXT = """[bold green]Yakety Yak \u2014 Help[/]

[bold]What is this?[/]
This tool sits alongside a real terminal shell. You type commands
on the left, and plain-language explanations appear on the right
automatically. No copy-paste needed!

[bold]How to use it:[/]
  1. Type a command in the input box on the left and press Enter
  2. The command runs in a real shell
  3. An explanation appears on the right automatically

[bold]Git Translator:[/]
  Press [bold cyan]Ctrl+G[/] to switch to the Git Translator view
  Paste any GitHub URL to analyze it instantly
  Example: [bold cyan]https://github.com/torvalds/linux[/]
  Also works: [bold cyan]/git owner/repo[/] from the terminal view
  Shows: stars, forks, language, license, risk/reward score, and more

[bold]Translate without running:[/]
  Type [bold cyan]translate <command>[/] to explain a command without running it
  Example: [bold cyan]translate git rebase -i HEAD~3[/]

[bold]Quick-try commands:[/]
  Type [bold cyan]try[/] to see a list of beginner-friendly commands
  Type [bold cyan]try 1[/] through [bold cyan]try 25[/] to auto-run one

[bold]Keyboard shortcuts:[/]
  [dim]Ctrl+B[/]  Toggle between Beginner and Familiar mode
  [dim]Ctrl+G[/]  Toggle Terminal / Git Translator view
  [dim]Ctrl+T[/]  Toggle AI translations on/off
  [dim]Ctrl+S[/]  Switch theme (Terminal / Glass)
  [dim]Ctrl+L[/]  Clear the translation panel
  [dim]Ctrl+Q[/]  Quit the app

[bold]Pro Commands:[/]
  Type [bold cyan]login your@email.com[/] to sign in with Pro
  Type [bold cyan]account[/] to view your Pro subscription status
  Get Pro: [bold cyan]https://yaketyyak.replit.app/#download[/]

[bold]Tip:[/]
  All 25 starter commands are safe to run. They won't break
  anything and are great for learning!

[bold]Modes:[/]
  [magenta]Noob[/]           Never seen a terminal before. Full hand-holding
  [green]Beginner[/]       Just starting out. Simple, clear explanations
  [yellow]Intermediate[/]   Comfortable with basics. Focused, practical
  [red]Advanced[/]       Experienced dev. Terse, expert-level only

[bold]How translations work:[/]
  1. Your command/output is checked against a built-in knowledge
     base of 500+ commands and 50+ common error patterns
  2. If no match is found, AI provides a detailed explanation
  3. Toggle AI off with Ctrl+T for offline/local-only mode

[dim]\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500[/]"""

TRY_LIST_TEXT_HEADER = """[bold cyan]Quick-Try Commands[/]
[dim]Type \"try N\" to run a command (e.g. \"try 1\")[/]
"""


def strip_ansi(text):
    return ANSI_ESCAPE.sub("", text)


class ShellProcess:
    def __init__(self, on_output):
        self.on_output = on_output
        self.master_fd = None
        self.pid = None
        self.running = False

    def start(self):
        shell = os.environ.get("SHELL", "/bin/bash")
        self.master_fd, slave_fd = pty.openpty()

        self.pid = os.fork()
        if self.pid == 0:
            os.close(self.master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            env = os.environ.copy()
            env["TERM"] = "dumb"
            env["PROMPT_COMMAND"] = ""
            shell_name = os.path.basename(shell)
            if shell_name == "zsh":
                zdotdir = "/tmp/yakety-yak-zsh"
                os.makedirs(zdotdir, exist_ok=True)
                zshrc_path = os.path.join(zdotdir, ".zshrc")
                with open(zshrc_path, "w") as f:
                    f.write('PROMPT="$ "\n')
                    f.write("unsetopt zle\n")
                    f.write("setopt no_prompt_cr\n")
                env["ZDOTDIR"] = zdotdir
                env["PS1"] = "$ "
                env["PROMPT"] = "$ "
                shell_args = [shell, "--no-globalrcs"]
            else:
                env["PS1"] = "$ "
                shell_args = [shell, "--norc", "--noprofile"]
            os.execvpe(shell, shell_args, env)
        else:
            os.close(slave_fd)
            self.running = True
            self._reader_thread = threading.Thread(
                target=self._read_output, daemon=True
            )
            self._reader_thread.start()

    def _read_output(self):
        while self.running:
            try:
                data = os.read(self.master_fd, 4096)
                if not data:
                    break
                text = data.decode("utf-8", errors="replace")
                self.on_output(text)
            except OSError:
                break
        self.running = False

    def write(self, data):
        if self.master_fd is not None and self.running:
            os.write(self.master_fd, data.encode("utf-8"))

    def send_line(self, line):
        self.write(line + "\n")

    def resize(self, rows, cols):
        if self.master_fd is not None:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            try:
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except OSError:
                pass

    def stop(self):
        self.running = False
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.pid and self.pid > 0:
            try:
                os.kill(self.pid, signal.SIGTERM)
            except OSError:
                pass
            for _ in range(10):
                try:
                    pid, _ = os.waitpid(self.pid, os.WNOHANG)
                    if pid != 0:
                        break
                except ChildProcessError:
                    break
                import time
                time.sleep(0.1)
            else:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                    os.waitpid(self.pid, 0)
                except (OSError, ChildProcessError):
                    pass
            self.pid = None


class ShellOutput(RichLog):
    pass


class YaketyYak(App):

    CSS = APP_CSS

    TITLE = f"Yakety Yak v{APP_VERSION}"
    SUB_TITLE = "Type commands in the shell \u2014 get plain-language explanations"

    BINDINGS = [
        Binding("ctrl+b", "toggle_mode", "Toggle Mode", key_display="Ctrl+B"),
        Binding("ctrl+g", "toggle_view", "Git Translator", key_display="Ctrl+G"),
        Binding("ctrl+t", "toggle_ai", "AI Toggle", key_display="Ctrl+T"),
        Binding("ctrl+l", "clear_translations", "Clear Panel", key_display="Ctrl+L"),
        Binding("ctrl+s", "toggle_theme", "Switch Theme", key_display="Ctrl+S"),
        Binding("ctrl+q", "quit", "Quit App", key_display="Ctrl+Q"),
    ]

    mode = reactive("noob")
    use_ai = reactive(True)
    language = reactive("en")
    current_view = reactive("terminal")

    def __init__(self):
        super().__init__()
        self.shell = None
        self.output_buffer = deque(maxlen=100)
        self._debounce_task = None
        self._last_command = ""
        self._pending_lines = []
        self._translation_id = 0
        self._shown_welcome = False
        self._app_theme = load_theme_preference()
        self._license_key = load_license_key()
        self._is_pro = False

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="view-toggle-bar"):
            yield Button("\u25b6 Terminal", id="btn-terminal-view", classes="active-view")
            yield Button("Git Translator", id="btn-git-view")

        with Horizontal(id="main-container"):
            with Container(id="shell-panel"):
                with Vertical(id="shell-panel-inner"):
                    yield Label("SHELL", id="shell-title")
                    yield ShellOutput(id="shell-output", highlight=False, markup=False, wrap=True)
                    yield Input(
                        placeholder="Type a command, paste a GitHub URL, or 'help'",
                        id="shell-input",
                    )
            with Container(id="translation-panel"):
                with Vertical(id="translation-panel-inner"):
                    yield Label("TRANSLATION", id="translation-title")
                    yield RichLog(
                        id="translation-output", highlight=False, markup=True, wrap=True
                    )

        with Container(id="git-container"):
            with Container(id="git-panel"):
                with Vertical(id="git-panel-inner"):
                    yield Label("GIT URL TRANSLATOR", id="git-title")
                    with Horizontal(id="git-input-row"):
                        yield Input(
                            placeholder="Paste a GitHub URL (e.g. https://github.com/torvalds/linux)",
                            id="git-url-input",
                        )
                        yield Button("ANALYZE", id="btn-analyze")
                    yield RichLog(
                        id="git-results", highlight=False, markup=True, wrap=True
                    )

        with Horizontal(id="settings-bar"):
            yield Label("Mode:")
            yield Select(
                [
                    ("Noob", "noob"),
                    ("Beginner", "beginner"),
                    ("Intermediate", "intermediate"),
                    ("Advanced", "advanced"),
                ],
                value="noob",
                id="mode-select",
                allow_blank=False,
            )
            yield Label("Lang:")
            yield Select(
                [(name, code) for code, name in LANGUAGE_NAMES.items()],
                value="en",
                id="lang-select",
                allow_blank=False,
            )
            yield Label("AI: ON", id="ai-label")
            yield Label(f"Theme: {THEME_NAMES.get(self._app_theme, 'Terminal')}", id="theme-label")
            yield Label("Ready", id="status-label")

        yield Footer()

    def on_mount(self) -> None:
        self.kb = ensure_knowledge_base_exists()
        self._apply_theme_class()
        ai_status, ai_desc = get_ai_status()
        if not AI_AVAILABLE:
            self.use_ai = False
        self.shell = ShellProcess(on_output=self._on_shell_output)
        self.shell.start()
        shell_input = self.query_one("#shell-input", Input)
        shell_input.focus()
        ai_label = self.query_one("#ai-label", Label)
        if not AI_AVAILABLE:
            ai_label.update("AI: OFF")
        elif ai_status == "ollama_ready":
            ai_label.update("AI: Ollama")
        else:
            ai_label.update("AI: ON")
        self._ai_status = ai_status
        self._ai_desc = ai_desc
        if self._license_key:
            self._validate_pro_key_on_startup()
        self._show_shell_logo()
        self._show_welcome()
        self._show_git_placeholder()

    def _apply_theme_class(self) -> None:
        screen = self.screen
        screen.remove_class("theme-terminal", "theme-glass")
        screen.add_class(f"theme-{self._app_theme}")

    def _validate_pro_key_on_startup(self) -> None:
        try:
            valid, data = validate_pro_key(self._license_key)
            if valid and data.get("status") == "active":
                self._is_pro = True
                self.title = f"Yakety Yak v{APP_VERSION} [PRO]"
                try:
                    ai_label = self.query_one("#ai-label", Label)
                    ai_label.update("AI: PRO")
                except Exception:
                    pass
        except Exception:
            pass

    def _activate_pro(self, key: str) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        trans.write("[bold]Activating license key...[/]")

        try:
            valid, data = validate_pro_key(key)
        except ProConnectionError as e:
            trans.write(f"[yellow]Could not reach the activation server.[/]")
            trans.write(f"[dim]{e}[/]")
            trans.write("[dim]Your key has been saved. It will be validated next time you're online.[/]")
            save_license_key(key)
            self._license_key = key
            return
        except Exception as e:
            trans.write(f"[red]Activation error: {e}[/]")
            return

        if valid and data.get("status") == "active":
            save_license_key(key)
            self._license_key = key
            self._is_pro = True
            self.title = f"Yakety Yak v{APP_VERSION} [PRO]"
            ai_label = self.query_one("#ai-label", Label)
            ai_label.update("AI: PRO")
            trans.write("")
            trans.write("[bold green]License activated! Welcome to Yakety Yak Pro.[/]")
            plan = data.get("plan", "pro")
            usage = data.get("usage", {})
            trans.write(f"  Plan: [bold]{plan}[/]")
            trans.write(f"  Translations this month: {usage.get('translations_this_month', 0)} / {usage.get('limit', 500)}")
            trans.write("")
            trans.write("[dim]Cloud AI translations are now enabled.[/]")
        else:
            error = data.get("error", "Invalid or expired key")
            trans.write(f"[red]Activation failed: {error}[/]")

    def _login_pro(self, email: str) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        trans.write(f"[bold]Signing in with {email}...[/]")

        try:
            key, data = activate_by_email(email)
        except ProConnectionError as e:
            trans.write(f"[yellow]Could not reach the activation server.[/]")
            trans.write(f"[dim]{e}[/]")
            return
        except Exception as e:
            trans.write(f"[red]Login error: {e}[/]")
            return

        if key:
            save_license_key(key)
            self._license_key = key
            self._is_pro = True
            self.title = f"Yakety Yak v{APP_VERSION} [PRO]"
            ai_label = self.query_one("#ai-label", Label)
            ai_label.update("AI: PRO")
            trans.write("")
            trans.write("[bold green]Welcome to Yakety Yak Pro![/]")
            plan = data.get("plan", "pro")
            usage = data.get("usage", {})
            trans.write(f"  Plan: [bold]{plan}[/]")
            trans.write(f"  Translations this month: {usage.get('translations_this_month', 0)} / {usage.get('limit', 500)}")
            trans.write("")
            trans.write("[dim]Cloud AI translations are now enabled.[/]")
        else:
            error = data.get("error", "No active Pro subscription found for this email")
            trans.write(f"[red]{error}[/]")
            trans.write("[dim]Make sure you're using the same email you used at checkout.[/]")
            trans.write(f"[dim]Get Pro at https://yaketyyak.replit.app/#download[/]")

    def _show_account(self) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        if not self._license_key:
            trans.write("[yellow]No Pro account found.[/]")
            trans.write("[dim]Type 'login your@email.com' to sign in.[/]")
            trans.write("[dim]Get Pro at https://yaketyyak.replit.app/#download[/]")
            return

        trans.write("[bold]Checking account status...[/]")
        try:
            valid, data = validate_pro_key(self._license_key)
        except Exception:
            trans.write(f"[yellow]Could not reach server. Your key: {self._license_key}[/]")
            return

        if valid:
            plan = data.get("plan", "pro")
            status = data.get("status", "unknown")
            email = data.get("email", "")
            usage = data.get("usage", {})
            trans.write("")
            trans.write("[bold green]Yakety Yak Pro Account[/]")
            trans.write(f"  Email: [bold]{email}[/]")
            trans.write(f"  Plan: [bold]{plan}[/]")
            trans.write(f"  Status: [bold]{'[green]active[/green]' if status == 'active' else status}[/]")
            trans.write(f"  Translations: {usage.get('translations_this_month', 0)} / {usage.get('limit', 500)} this month")
            trans.write(f"  Key: [dim]{self._license_key}[/]")
            trans.write("")
            trans.write("[dim]Manage subscription: https://yaketyyak.replit.app/account[/]")
        else:
            error = data.get("error", "Invalid key")
            trans.write(f"[red]{error}[/]")

    def _show_shell_logo(self) -> None:
        shell_out = self.query_one("#shell-output", ShellOutput)
        is_glass = self._app_theme == "glass"
        accent = "bright_magenta" if is_glass else "green"
        dim_accent = "magenta" if is_glass else "dark_green"

        logo_lines = [
            "",
            f"  ╔{'═' * 47}╗",
            f"  ║                                               ║",
            f"  ║   ██╗   ██╗ █████╗ ██╗  ██╗███████╗████████╗  ║",
            f"  ║   ╚██╗ ██╔╝██╔══██╗██║ ██╔╝██╔════╝╚══██╔══╝  ║",
            f"  ║    ╚████╔╝ ███████║█████╔╝ █████╗     ██║     ║",
            f"  ║     ╚██╔╝  ██╔══██║██╔═██╗ ██╔══╝     ██║     ║",
            f"  ║      ██║   ██║  ██║██║  ██╗███████╗   ██║     ║",
            f"  ║      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝     ║",
            f"  ║                                               ║",
            f"  ║        ██╗   ██╗ █████╗ ██╗  ██╗              ║",
            f"  ║        ╚██╗ ██╔╝██╔══██╗██║ ██╔╝              ║",
            f"  ║         ╚████╔╝ ███████║█████╔╝               ║",
            f"  ║          ╚██╔╝  ██╔══██║██╔═██╗               ║",
            f"  ║           ██║   ██║  ██║██║  ██╗              ║",
            f"  ║           ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝              ║",
            f"  ║                                               ║",
            f"  ╚{'═' * 47}╝",
            "",
        ]

        for line in logo_lines:
            t = Text(line)
            t.stylize(accent)
            shell_out.write(t)

        tag = Text(f"  Terminal Translator v{APP_VERSION}")
        tag.stylize(f"bold {accent}")
        shell_out.write(tag)

        sub = Text("  Type a command below — explanations appear on the right")
        sub.stylize(f"{dim_accent}")
        shell_out.write(sub)

        sep = Text(f"  {'━' * 46}")
        sep.stylize(f"{dim_accent}")
        shell_out.write(sep)
        shell_out.write(Text(""))

    def _show_welcome(self) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        trans.write("[bold green]  ╔═══════════════════════════════════════════════╗[/]")
        trans.write("[bold green]  ║                                               ║[/]")
        trans.write("[bold green]  ║   ▄▄▄▄ ▄▄▄▄ ▄  ▄ ▄▄▄▄ ▄▄▄▄ ▄  ▄             ║[/]")
        trans.write("[bold green]  ║   █  █ █  █ █ ▀▄▀ █▀▀  █▀▀  █  █             ║[/]")
        trans.write("[bold green]  ║   █▄▄█ █▄▄█ █  █ █▄▄▄ █    █▄▄█             ║[/]")
        trans.write("[bold green]  ║   ▀  ▀ ▀  ▀ ▀  ▀ ▀▀▀▀ ▀    ▀  ▀             ║[/]")
        trans.write("[bold green]  ║                                               ║[/]")
        trans.write(f"[bold green]  ║[/]   [bold green]Y A K E T Y   Y A K[/]  [dim]v{APP_VERSION}[/dim]          [bold green]║[/]")
        trans.write("[bold green]  ║[/]   [dim italic]Terminal Translator — Understand Every Command[/] [bold green]║[/]")
        trans.write("[bold green]  ║                                               ║[/]")
        trans.write("[bold green]  ╚═══════════════════════════════════════════════╝[/]")
        trans.write("")
        trans.write("  [bold]🎯 Quick Start[/]")
        trans.write("  [bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        trans.write("")
        trans.write("  This tool explains everything that happens in your")
        trans.write("  terminal, in plain language. No experience needed!")
        trans.write("")
        trans.write("  [bold cyan]▸[/] Type [bold green]try 1[/] to run your first command")
        trans.write("  [bold cyan]▸[/] Type [bold green]/git owner/repo[/] to analyze a GitHub repo")
        trans.write("  [bold cyan]▸[/] Press [bold green]Ctrl+G[/] to open the Git Translator view")
        trans.write("  [bold cyan]▸[/] Type [bold green]help[/] for full instructions")
        trans.write("")
        trans.write("  [bold]📋 Starter Commands[/]")
        trans.write("  [bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        trans.write("")
        trans.write(f"   [bold cyan]①[/]  [bold]{STARTER_COMMANDS[0][0]}[/]  [dim]—[/] {STARTER_COMMANDS[0][1]}")
        trans.write(f"   [bold cyan]②[/]  [bold]{STARTER_COMMANDS[1][0]}[/]  [dim]—[/] {STARTER_COMMANDS[1][1]}")
        trans.write(f"   [bold cyan]③[/]  [bold]{STARTER_COMMANDS[2][0]}[/]  [dim]—[/] {STARTER_COMMANDS[2][1]}")
        trans.write(f"   [bold cyan]④[/]  [bold]{STARTER_COMMANDS[3][0]}[/]  [dim]—[/] {STARTER_COMMANDS[3][1]}")
        trans.write(f"   [bold cyan]⑤[/]  [bold]{STARTER_COMMANDS[4][0]}[/]  [dim]—[/] {STARTER_COMMANDS[4][1]}")
        trans.write("")
        trans.write("  [bold]⌨  Keyboard Shortcuts[/]")
        trans.write("  [bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        trans.write("")
        trans.write("   [bold green]Ctrl+B[/] [dim]→[/] Cycle Mode    [bold green]Ctrl+G[/] [dim]→[/] Git View")
        trans.write("   [bold green]Ctrl+T[/] [dim]→[/] AI Toggle     [bold green]Ctrl+L[/] [dim]→[/] Clear Panel")
        trans.write("   [bold green]Ctrl+S[/] [dim]→[/] Switch Theme  [bold green]Ctrl+Q[/] [dim]→[/] Quit App")
        trans.write("")
        trans.write("  [bold green]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        if not AI_AVAILABLE:
            trans.write("")
            trans.write("[bold yellow]  ⚠ AI is off — no AI backend detected.[/]")
            trans.write("[dim]    Install Ollama + qwen2.5-coder for free local AI,[/]")
            trans.write("[dim]    or set OPENAI_API_KEY for cloud AI.[/]")
            trans.write("[dim]    The built-in knowledge base (500+ commands) works without AI![/]")
        elif hasattr(self, '_ai_status') and self._ai_status == "ollama_ready":
            trans.write("")
            trans.write("[bold green]  ✓ AI powered by Ollama (local, private, free)[/]")
        elif hasattr(self, '_ai_status') and self._ai_status == "ollama_no_model":
            trans.write("")
            trans.write("[bold yellow]  ⚠ Ollama is running but model not installed.[/]")
            trans.write("[dim]    Run: ollama pull qwen2.5-coder:1.5b[/]")
        trans.write("")
        self._shown_welcome = True

    def _show_git_placeholder(self) -> None:
        git_results = self.query_one("#git-results", RichLog)
        git_results.write("")
        git_results.write("  [bold]Git URL Translator[/]")
        git_results.write("  [bold green]\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501[/]")
        git_results.write("")
        git_results.write("  Paste a GitHub URL above and click ANALYZE to get a")
        git_results.write("  full breakdown of any repository including:")
        git_results.write("")
        git_results.write("  [bold cyan]\u25b8[/] Stars, forks, and watchers")
        git_results.write("  [bold cyan]\u25b8[/] Language and license info")
        git_results.write("  [bold cyan]\u25b8[/] Quality score with risk/reward analysis")
        git_results.write("  [bold cyan]\u25b8[/] Activity and maintenance status")
        git_results.write("  [bold cyan]\u25b8[/] Topics and metadata")
        git_results.write("")
        git_results.write("  [bold]Examples:[/]")
        git_results.write("    [bold green]\u25b8[/] [cyan]https://github.com/torvalds/linux[/]")
        git_results.write("    [bold green]\u25b8[/] [cyan]https://github.com/textualize/textual[/]")
        git_results.write("    [bold green]\u25b8[/] [cyan]facebook/react[/]")
        git_results.write("")
        git_results.write("[dim]You can also type /git owner/repo in the terminal view.[/]")

    def _show_try_list(self) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        trans.write(TRY_LIST_TEXT_HEADER)
        trans.write("")
        for i, (cmd, desc) in enumerate(STARTER_COMMANDS, 1):
            trans.write(f"  [cyan]{i:2d}.[/] [bold]{cmd}[/]")
            trans.write(f"      [dim]{desc}[/]")
        trans.write("")
        trans.write("[dim]" + "\u2500" * 50 + "[/]")

    def _show_help(self) -> None:
        trans = self.query_one("#translation-output", RichLog)
        trans.write("")
        for line in HELP_TEXT.split("\n"):
            trans.write(line)

    def _handle_app_command(self, command: str) -> bool:
        cmd = command.strip().lower()

        if cmd == "help":
            self._show_help()
            return True

        if cmd == "try":
            self._show_try_list()
            return True

        try_match = re.match(r"^try\s+(\d+)$", cmd)
        if try_match:
            num = int(try_match.group(1))
            if 1 <= num <= len(STARTER_COMMANDS):
                actual_cmd = STARTER_COMMANDS[num - 1][0]
                desc = STARTER_COMMANDS[num - 1][1]
                trans = self.query_one("#translation-output", RichLog)
                trans.write("")
                trans.write(f"[bold cyan]Running:[/] {actual_cmd}")
                trans.write(f"[dim]{desc}[/]")
                trans.write("")
                self._last_command = actual_cmd
                if self.shell and self.shell.running:
                    self.shell.send_line(actual_cmd)
                return True
            else:
                trans = self.query_one("#translation-output", RichLog)
                trans.write(f"[yellow]No command #{num}. Type 'try' to see the list (1-{len(STARTER_COMMANDS)}).[/]")
                return True

        login_match = re.match(r"^login\s+(.+)$", cmd, re.IGNORECASE)
        if login_match:
            email = login_match.group(1).strip()
            self._login_pro(email)
            return True

        if cmd == "login":
            trans = self.query_one("#translation-output", RichLog)
            trans.write("")
            trans.write("[bold]Usage:[/] [cyan]login your@email.com[/]")
            trans.write("[dim]Use the email you used when purchasing Pro.[/]")
            return True

        activate_match = re.match(r"^activate\s+(.+)$", cmd, re.IGNORECASE)
        if activate_match:
            key = activate_match.group(1).strip()
            if "@" in key:
                self._login_pro(key)
            else:
                self._activate_pro(key)
            return True

        if cmd == "account":
            self._show_account()
            return True

        translate_match = re.match(r"^(?:/translate|translate)\s+(.+)$", cmd, re.IGNORECASE)
        if translate_match:
            text_to_translate = translate_match.group(1)
            trans = self.query_one("#translation-output", RichLog)
            trans.write("")
            trans.write(f"[bold cyan]Translating:[/] {text_to_translate}")
            self._do_translate(text_to_translate, self._translation_id + 1)
            return True

        git_match = re.match(r"^/git\s+(.+)$", cmd, re.IGNORECASE)
        if git_match:
            url_or_repo = git_match.group(1).strip()
            self._analyze_github_repo(url_or_repo)
            return True

        if re.match(r"^https?://github\.com/[^/]+/[^/\s#?]+", cmd, re.IGNORECASE):
            self._analyze_github_repo(cmd.strip())
            return True

        return False

    def _parse_github_url(self, url_or_repo: str):
        patterns = [
            r"(?:https?://)?github\.com/([^/]+)/([^/\s#?]+)",
            r"^([^/\s]+)/([^/\s]+)$",
        ]
        for pattern in patterns:
            m = re.match(pattern, url_or_repo.strip().rstrip("/"))
            if m:
                owner = m.group(1)
                repo = m.group(2).replace(".git", "")
                return owner, repo
        return None, None

    def _calculate_quality_score(self, data):
        score = 0
        risk_flags = []
        reward_flags = []

        stars = data.get("stargazers_count", 0)
        if stars >= 5000:
            score += 25
            reward_flags.append("Highly starred project")
        elif stars >= 1000:
            score += 20
            reward_flags.append("Strong community interest")
        elif stars >= 100:
            score += 12
            reward_flags.append("Growing community")
        elif stars >= 10:
            score += 5
        else:
            risk_flags.append("Very low star count \u2014 may be experimental")

        desc = data.get("description")
        if desc:
            score += 5
            reward_flags.append("Has description")
        else:
            risk_flags.append("No description \u2014 purpose unclear")

        license_info = data.get("license")
        license_name = license_info.get("spdx_id", "Unknown") if license_info else "None"
        if license_name not in ("None", "Unknown", "NOASSERTION"):
            score += 10
            reward_flags.append(f"Licensed ({license_name})")
        else:
            risk_flags.append("No license \u2014 legally risky to use")

        days_since_update = None
        if data.get("pushed_at"):
            try:
                last_push = datetime.fromisoformat(data["pushed_at"].replace("Z", "+00:00"))
                days_since_update = (datetime.now(timezone.utc) - last_push).days
                if days_since_update < 30:
                    score += 15
                    reward_flags.append("Actively maintained (updated within 30 days)")
                elif days_since_update < 90:
                    score += 10
                    reward_flags.append("Recently maintained")
                elif days_since_update < 365:
                    score += 5
                    risk_flags.append(f"Not updated in {days_since_update} days")
                else:
                    risk_flags.append(f"Stale \u2014 last updated {days_since_update} days ago")
            except Exception:
                pass

        forks = data.get("forks_count", 0)
        if forks >= 500:
            score += 10
            reward_flags.append("Heavily forked \u2014 widely used")
        elif forks >= 50:
            score += 7
            reward_flags.append("Good fork count")
        elif forks >= 5:
            score += 3

        if not data.get("fork", False):
            score += 3

        if data.get("archived", False):
            score -= 15
            risk_flags.append("Repository is ARCHIVED \u2014 no longer maintained")

        if data.get("fork", False):
            score -= 5
            risk_flags.append("This is a fork, not the original")

        open_issues = data.get("open_issues_count", 0)
        if open_issues > 500:
            score -= 5
            risk_flags.append(f"{open_issues:,} open issues \u2014 may have unresolved problems")
        elif open_issues > 100:
            risk_flags.append(f"{open_issues:,} open issues")

        if data.get("has_wiki"):
            score += 2
        if data.get("has_pages"):
            score += 2
            reward_flags.append("Has GitHub Pages site")

        score = max(0, min(score, 100))

        if score >= 75:
            verdict = "Excellent"
            verdict_color = "green"
        elif score >= 55:
            verdict = "Good"
            verdict_color = "cyan"
        elif score >= 35:
            verdict = "Fair"
            verdict_color = "yellow"
        else:
            verdict = "Caution"
            verdict_color = "red"

        return score, verdict, verdict_color, risk_flags, reward_flags, days_since_update

    @work(thread=True)
    def _analyze_github_repo(self, url_or_repo: str, target: str = "auto") -> None:
        if target == "auto":
            if self.current_view == "git":
                target = "git"
            else:
                target = "translation"

        if target == "git":
            out = self.query_one("#git-results", RichLog)
        else:
            out = self.query_one("#translation-output", RichLog)

        status = self.query_one("#status-label", Label)
        self.call_from_thread(status.update, "Analyzing repo...")
        self.call_from_thread(out.write, "")
        self.call_from_thread(out.write, "[bold magenta]\u2500\u2500\u2500 Git URL Translator \u2500\u2500\u2500[/bold magenta]")
        self.call_from_thread(out.write, f"[dim]Analyzing: {url_or_repo}[/dim]")

        owner, repo = self._parse_github_url(url_or_repo)
        if not owner or not repo:
            self.call_from_thread(out.write, "")
            self.call_from_thread(out.write, "[red]Could not parse GitHub URL.[/red]")
            self.call_from_thread(out.write, "[dim]Usage: https://github.com/owner/repo or owner/repo[/dim]")
            self.call_from_thread(out.write, "[dim]" + "\u2500" * 50 + "[/dim]")
            self.call_from_thread(status.update, "Ready")
            return

        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            req = urllib.request.Request(api_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "YaketyYak/1.0",
            })
            with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            self.call_from_thread(out.write, "")
            if e.code == 404:
                self.call_from_thread(out.write, f"[red]Repository not found: {owner}/{repo}[/red]")
                self.call_from_thread(out.write, "[dim]Check the URL and make sure the repo exists and is public.[/dim]")
            elif e.code == 403:
                self.call_from_thread(out.write, f"[red]GitHub API rate limit exceeded.[/red]")
                self.call_from_thread(out.write, "[dim]Try again in a few minutes.[/dim]")
            else:
                self.call_from_thread(out.write, f"[red]GitHub API error: {e.code}[/red]")
            self.call_from_thread(out.write, "[dim]" + "\u2500" * 50 + "[/dim]")
            self.call_from_thread(status.update, "Ready")
            return
        except Exception as e:
            self.call_from_thread(out.write, "")
            self.call_from_thread(out.write, f"[red]Network error: {str(e)}[/red]")
            self.call_from_thread(out.write, "[dim]Check your internet connection.[/dim]")
            self.call_from_thread(out.write, "[dim]" + "\u2500" * 50 + "[/dim]")
            self.call_from_thread(status.update, "Ready")
            return

        contrib_count = 0
        try:
            contrib_url = f"https://api.github.com/repos/{owner}/{repo}/contributors?per_page=1&anon=true"
            req2 = urllib.request.Request(contrib_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "YaketyYak/1.0",
            })
            with urllib.request.urlopen(req2, timeout=5, context=SSL_CONTEXT) as resp2:
                link_header = resp2.headers.get("Link", "")
                if 'rel="last"' in link_header:
                    m = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if m:
                        contrib_count = int(m.group(1))
                else:
                    contributors = json.loads(resp2.read())
                    contrib_count = len(contributors)
        except Exception:
            pass

        releases_count = 0
        try:
            rel_url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=1"
            req3 = urllib.request.Request(rel_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "YaketyYak/1.0",
            })
            with urllib.request.urlopen(req3, timeout=5, context=SSL_CONTEXT) as resp3:
                link_header = resp3.headers.get("Link", "")
                if 'rel="last"' in link_header:
                    m = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if m:
                        releases_count = int(m.group(1))
                else:
                    releases = json.loads(resp3.read())
                    releases_count = len(releases)
        except Exception:
            pass

        score, verdict, verdict_color, risk_flags, reward_flags, days_since_update = self._calculate_quality_score(data)

        if releases_count > 0:
            score = min(score + 5, 100)
            reward_flags.append(f"{releases_count} release(s) published")
        else:
            risk_flags.append("No releases \u2014 may not have stable versions")

        if contrib_count >= 50:
            score = min(score + 10, 100)
            reward_flags.append(f"{contrib_count}+ contributors")
        elif contrib_count >= 10:
            score = min(score + 7, 100)
            reward_flags.append(f"{contrib_count} contributors")
        elif contrib_count >= 2:
            score = min(score + 3, 100)
        elif contrib_count == 1:
            risk_flags.append("Single contributor \u2014 bus factor of 1")

        languages_info = {}
        try:
            lang_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
            req_lang = urllib.request.Request(lang_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "YaketyYak/1.0",
            })
            with urllib.request.urlopen(req_lang, timeout=5, context=SSL_CONTEXT) as resp_lang:
                languages_info = json.loads(resp_lang.read())
        except Exception:
            pass

        recent_commits = []
        try:
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=5"
            req_commits = urllib.request.Request(commits_url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "YaketyYak/1.0",
            })
            with urllib.request.urlopen(req_commits, timeout=5, context=SSL_CONTEXT) as resp_commits:
                recent_commits = json.loads(resp_commits.read())
        except Exception:
            pass

        name = data.get("full_name", f"{owner}/{repo}")
        desc = data.get("description") or "No description provided"
        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        watchers = data.get("subscribers_count", data.get("watchers_count", 0))
        lang = data.get("language") or "Not specified"
        license_info = data.get("license")
        license_name = license_info.get("spdx_id", "Unknown") if license_info else "None"
        license_full = license_info.get("name", license_name) if license_info else "None"
        created = data.get("created_at", "")[:10]
        updated = data.get("pushed_at", "")[:10]
        created_full = data.get("created_at", "")
        size_kb = data.get("size", 0)
        default_branch = data.get("default_branch", "main")
        is_fork = data.get("fork", False)
        archived = data.get("archived", False)
        open_issues = data.get("open_issues_count", 0)
        topics = data.get("topics", [])
        homepage = data.get("homepage") or ""
        has_wiki = data.get("has_wiki", False)
        has_pages = data.get("has_pages", False)
        has_projects = data.get("has_projects", False)
        has_discussions = data.get("has_discussions", False)
        network_count = data.get("network_count", forks)

        if score >= 75:
            verdict_color = "green"
            verdict = "EXCELLENT"
            verdict_emoji = "\u2705"
            verdict_summary = "Well-maintained, widely used, and safe to integrate into your projects."
        elif score >= 55:
            verdict_color = "cyan"
            verdict = "GOOD"
            verdict_emoji = "\U0001f44d"
            verdict_summary = "Solid project with good fundamentals. Worth using with normal caution."
        elif score >= 35:
            verdict_color = "yellow"
            verdict = "FAIR"
            verdict_emoji = "\u26a0\ufe0f"
            verdict_summary = "Some concerns present. Review the risk flags before depending on this."
        else:
            verdict_color = "red"
            verdict = "CAUTION"
            verdict_emoji = "\U0001f6a8"
            verdict_summary = "Significant risks identified. Carefully evaluate before using."

        if size_kb >= 1024 * 1024:
            size_str = f"{size_kb / 1024 / 1024:.1f} GB"
        elif size_kb >= 1024:
            size_str = f"{size_kb / 1024:.1f} MB"
        else:
            size_str = f"{size_kb:,} KB"

        repo_age_str = ""
        if created_full:
            try:
                created_dt = datetime.fromisoformat(created_full.replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).days
                if age_days >= 365:
                    repo_age_str = f" ({age_days // 365}y {(age_days % 365) // 30}m old)"
                elif age_days >= 30:
                    repo_age_str = f" ({age_days // 30} months old)"
                else:
                    repo_age_str = f" ({age_days} days old)"
            except Exception:
                pass

        bar_width = 20
        filled = int(score / 100 * bar_width)
        empty = bar_width - filled
        score_bar = f"[{verdict_color}]{'█' * filled}[/{verdict_color}][dim]{'░' * empty}[/dim]"

        def w(text):
            self.call_from_thread(out.write, text)

        w("")
        w(f"[bold]{'═' * 54}[/bold]")
        w(f"  [bold]{name}[/bold]")
        w(f"  [dim]{desc}[/dim]")
        if homepage:
            w(f"  [dim cyan]{homepage}[/dim cyan]")
        w(f"[bold]{'═' * 54}[/bold]")

        w("")
        w(f"  {verdict_emoji} [{verdict_color}][bold]  QUALITY SCORE: {score}/100 — {verdict}[/bold][/{verdict_color}]")
        w(f"     {score_bar} {score}%")
        w(f"  [dim]  {verdict_summary}[/dim]")

        w("")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"  [bold cyan]POPULARITY[/bold cyan]")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"    [yellow]★[/yellow] Stars        [bold]{stars:>10,}[/bold]")
        w(f"    \U0001f374 Forks        [bold]{forks:>10,}[/bold]")
        w(f"    \U0001f441  Watchers     [bold]{watchers:>10,}[/bold]")
        w(f"    \U0001f465 Contributors [bold]{contrib_count:>10,}[/bold]")
        w(f"    \U0001f310 Network      [bold]{network_count:>10,}[/bold]")

        w("")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"  [bold cyan]PROJECT INFO[/bold cyan]")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"    \U0001f4bb Language     [bold]{lang}[/bold]")
        w(f"    \U0001f4dc License      [bold]{license_full}[/bold]")
        w(f"    \U0001f333 Branch       [bold]{default_branch}[/bold]")
        w(f"    \U0001f4e6 Size         [bold]{size_str}[/bold]")
        w(f"    \U0001f4e6 Releases     [bold]{releases_count}[/bold]")
        w(f"    \U0001f41b Open Issues  [bold]{open_issues:,}[/bold]")

        flags = []
        if is_fork:
            flags.append("[yellow]⑂ Fork[/yellow]")
        if archived:
            flags.append("[red]⊘ Archived[/red]")
        if has_wiki:
            flags.append("[dim]📖 Wiki[/dim]")
        if has_pages:
            flags.append("[dim]🌐 Pages[/dim]")
        if has_discussions:
            flags.append("[dim]💬 Discussions[/dim]")
        if has_projects:
            flags.append("[dim]📋 Projects[/dim]")
        if flags:
            w(f"    Features     {' · '.join(flags)}")

        w("")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"  [bold cyan]TIMELINE[/bold cyan]")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"    \U0001f4c5 Created      [bold]{created}[/bold]{repo_age_str}")
        w(f"    \U0001f504 Last Push    [bold]{updated}[/bold]", )
        if days_since_update is not None:
            if days_since_update == 0:
                w(f"                 [green]Updated today![/green]")
            elif days_since_update == 1:
                w(f"                 [green]Updated yesterday[/green]")
            elif days_since_update < 7:
                w(f"                 [green]Updated {days_since_update} days ago[/green]")
            elif days_since_update < 30:
                w(f"                 [cyan]Updated {days_since_update} days ago[/cyan]")
            elif days_since_update < 90:
                w(f"                 [yellow]Updated {days_since_update} days ago[/yellow]")
            elif days_since_update < 365:
                w(f"                 [yellow]Updated {days_since_update} days ago ({days_since_update // 30} months)[/yellow]")
            else:
                w(f"                 [red]Last updated {days_since_update} days ago ({days_since_update // 365}+ years)[/red]")

        if languages_info:
            w("")
            w(f"  [bold]{'─' * 50}[/bold]")
            w(f"  [bold cyan]LANGUAGES[/bold cyan]")
            w(f"  [bold]{'─' * 50}[/bold]")
            total_bytes = sum(languages_info.values())
            lang_colors = {
                "Python": "yellow", "JavaScript": "yellow", "TypeScript": "blue",
                "Go": "cyan", "Rust": "red", "Ruby": "red", "Java": "red",
                "C": "white", "C++": "magenta", "C#": "green", "Swift": "red",
                "Kotlin": "magenta", "Shell": "green", "HTML": "red",
                "CSS": "blue", "Dockerfile": "cyan", "Makefile": "green",
            }
            for lang_name, lang_bytes in sorted(languages_info.items(), key=lambda x: x[1], reverse=True)[:8]:
                pct = (lang_bytes / total_bytes * 100) if total_bytes > 0 else 0
                lang_bar_width = 15
                lang_filled = int(pct / 100 * lang_bar_width)
                lc = lang_colors.get(lang_name, "white")
                bar = f"[{lc}]{'█' * lang_filled}[/{lc}][dim]{'░' * (lang_bar_width - lang_filled)}[/dim]"
                w(f"    {bar} {pct:5.1f}%  {lang_name}")

        if topics:
            w("")
            w(f"  [bold]{'─' * 50}[/bold]")
            w(f"  [bold cyan]TOPICS[/bold cyan]")
            w(f"  [bold]{'─' * 50}[/bold]")
            topic_strs = [f"[dim cyan]#{t}[/dim cyan]" for t in topics[:12]]
            row = "    "
            for t in topic_strs:
                row += t + "  "
            w(row)

        if recent_commits:
            w("")
            w(f"  [bold]{'─' * 50}[/bold]")
            w(f"  [bold cyan]RECENT ACTIVITY[/bold cyan]")
            w(f"  [bold]{'─' * 50}[/bold]")
            for commit in recent_commits[:5]:
                commit_data = commit.get("commit", {})
                msg = commit_data.get("message", "").split("\n")[0][:60]
                author = commit_data.get("author", {}).get("name", "unknown")
                date_str = commit_data.get("author", {}).get("date", "")[:10]
                sha_short = commit.get("sha", "")[:7]
                w(f"    [dim]{sha_short}[/dim] {msg}")
                w(f"             [dim]by {author} on {date_str}[/dim]")

        w("")
        w(f"  [bold]{'─' * 50}[/bold]")
        if reward_flags:
            w(f"  [green][bold]✓ STRENGTHS ({len(reward_flags)})[/bold][/green]")
            w(f"  [bold]{'─' * 50}[/bold]")
            for flag in reward_flags:
                w(f"    [green]✓[/green] {flag}")
            w("")

        if risk_flags:
            w(f"  [bold]{'─' * 50}[/bold]")
            w(f"  [yellow][bold]⚠ RISKS ({len(risk_flags)})[/bold][/yellow]")
            w(f"  [bold]{'─' * 50}[/bold]")
            for flag in risk_flags:
                w(f"    [yellow]⚠[/yellow] {flag}")
            w("")

        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"  [bold cyan]QUICK LINKS[/bold cyan]")
        w(f"  [bold]{'─' * 50}[/bold]")
        w(f"    [dim]Repo:[/dim]     https://github.com/{owner}/{repo}")
        w(f"    [dim]Issues:[/dim]   https://github.com/{owner}/{repo}/issues")
        w(f"    [dim]PRs:[/dim]      https://github.com/{owner}/{repo}/pulls")
        if releases_count > 0:
            w(f"    [dim]Releases:[/dim] https://github.com/{owner}/{repo}/releases")
        if has_wiki:
            w(f"    [dim]Wiki:[/dim]     https://github.com/{owner}/{repo}/wiki")

        w("")
        w(f"    [dim]Clone: git clone https://github.com/{owner}/{repo}.git[/dim]")

        w("")
        w(f"[bold]{'═' * 54}[/bold]")
        self.call_from_thread(status.update, "Ready")

    def _on_shell_output(self, text: str) -> None:
        self.call_from_thread(self._handle_output, text)

    def _handle_output(self, text: str) -> None:
        shell_out = self.query_one("#shell-output", ShellOutput)
        clean = strip_ansi(text)
        for line in clean.split("\n"):
            stripped = line.rstrip()
            if stripped:
                shell_out.write(stripped)
                self._pending_lines.append(stripped)

        if self._debounce_task is not None:
            self._debounce_task.cancel()
        self._debounce_task = asyncio.get_event_loop().call_later(
            0.8, self._trigger_translation
        )

    def _normalize_for_translation(self, lines):
        prompt_re = re.compile(r"^\$\s*")
        normalized = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped == "$":
                continue
            cleaned = prompt_re.sub("", stripped)
            if cleaned:
                normalized.append(cleaned)
        return normalized

    def _trigger_translation(self) -> None:
        if not self._pending_lines:
            return

        lines = list(self._pending_lines)
        self._pending_lines.clear()

        normalized = self._normalize_for_translation(lines)
        if not normalized:
            return

        combined = "\n".join(normalized)

        if combined == self._last_command:
            return

        self._translation_id += 1
        self._do_translate(combined, self._translation_id)

    @work(thread=True, exclusive=True)
    def _do_translate(self, text: str, tid: int = 0) -> None:
        status = self.query_one("#status-label", Label)
        self.call_from_thread(status.update, "Translating...")

        result = translate(
            text,
            mode=self.mode,
            language=self.language,
            use_ai=self.use_ai,
            license_key=self._license_key if self._is_pro else "",
        )

        if tid != self._translation_id:
            self.call_from_thread(status.update, "Ready")
            return

        explanation = result.get("explanation", "")
        source = result.get("source", "")
        category = result.get("category", "")

        if source == "local_db":
            source_tag = "[green][Local KB][/green]"
        elif source == "ai" and category == "cloud_ai_pro":
            source_tag = "[bold #f0b429][PRO Cloud AI][/bold #f0b429]"
        elif source == "ai" and category == "ollama":
            source_tag = "[cyan][Ollama AI][/cyan]"
        elif source == "ai":
            source_tag = "[blue][Cloud AI][/blue]"
        elif source == "error":
            source_tag = "[red][Error][/red]"
        else:
            source_tag = "[dim][No match][/dim]"

        preview = text[:80].replace("\n", " ")
        if len(text) > 80:
            preview += "..."

        trans_out = self.query_one("#translation-output", RichLog)
        self.call_from_thread(
            self._write_translation, trans_out, source_tag, category, preview, explanation
        )
        self.call_from_thread(status.update, "Ready")

    def _write_translation(self, trans_out, source_tag, category, preview, explanation):
        trans_out.write("")
        trans_out.write(f"  {source_tag}  [dim italic]{category}[/dim]")
        trans_out.write(f"  [bold cyan]\u25b8[/] [bold]{preview}[/bold]")
        trans_out.write("")
        for line in explanation.split("\n"):
            trans_out.write(f"  {line}")
        trans_out.write("")
        trans_out.write("[dim green]  \u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "shell-input":
            command = event.value
            event.input.clear()

            if not command.strip():
                return

            if self._handle_app_command(command):
                return

            if self.shell and self.shell.running:
                self._last_command = command
                self.shell.send_line(command)

        elif event.input.id == "git-url-input":
            url = event.value.strip()
            if url:
                self._analyze_github_repo(url, target="git")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-terminal-view":
            self._switch_view("terminal")
        elif event.button.id == "btn-git-view":
            self._switch_view("git")
        elif event.button.id == "btn-analyze":
            git_input = self.query_one("#git-url-input", Input)
            url = git_input.value.strip()
            if url:
                self._analyze_github_repo(url, target="git")

    def _switch_view(self, view: str) -> None:
        self.current_view = view
        main_container = self.query_one("#main-container")
        git_container = self.query_one("#git-container")
        btn_terminal = self.query_one("#btn-terminal-view", Button)
        btn_git = self.query_one("#btn-git-view", Button)

        if view == "git":
            main_container.add_class("hidden")
            git_container.add_class("active")
            btn_terminal.remove_class("active-view")
            btn_terminal.label = "Terminal"
            btn_git.add_class("active-view")
            btn_git.label = "\u25b6 Git Translator"
            git_input = self.query_one("#git-url-input", Input)
            git_input.focus()
        else:
            main_container.remove_class("hidden")
            git_container.remove_class("active")
            btn_terminal.add_class("active-view")
            btn_terminal.label = "\u25b6 Terminal"
            btn_git.remove_class("active-view")
            btn_git.label = "Git Translator"
            shell_input = self.query_one("#shell-input", Input)
            shell_input.focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "mode-select":
            self.mode = event.value
            self._update_footer_for_mode(self.mode)
        elif event.select.id == "lang-select":
            self.language = event.value

    MODE_ORDER = ["noob", "beginner", "intermediate", "advanced"]

    def _update_footer_for_mode(self, mode_name: str) -> None:
        if mode_name in ("intermediate", "advanced"):
            new_bindings = [
                Binding("ctrl+b", "toggle_mode", "Mode", key_display="^B"),
                Binding("ctrl+g", "toggle_view", "Git", key_display="^G"),
                Binding("ctrl+t", "toggle_ai", "AI", key_display="^T"),
                Binding("ctrl+l", "clear_translations", "Clear", key_display="^L"),
                Binding("ctrl+s", "toggle_theme", "Theme", key_display="^S"),
                Binding("ctrl+q", "quit", "Quit", key_display="^Q"),
            ]
        else:
            new_bindings = [
                Binding("ctrl+b", "toggle_mode", "Toggle Mode", key_display="Ctrl+B"),
                Binding("ctrl+g", "toggle_view", "Git Translator", key_display="Ctrl+G"),
                Binding("ctrl+t", "toggle_ai", "AI Toggle", key_display="Ctrl+T"),
                Binding("ctrl+l", "clear_translations", "Clear Panel", key_display="Ctrl+L"),
                Binding("ctrl+s", "toggle_theme", "Switch Theme", key_display="Ctrl+S"),
                Binding("ctrl+q", "quit", "Quit App", key_display="Ctrl+Q"),
            ]
        try:
            if hasattr(self._bindings, 'keys') and hasattr(self._bindings.keys, 'clear'):
                self._bindings.keys.clear()
            elif hasattr(self._bindings, 'key_to_bindings'):
                self._bindings.key_to_bindings.clear()
            else:
                self._bindings = type(self._bindings)()
        except Exception:
            pass
        for b in new_bindings:
            self._bindings.bind(b.key, b.action, b.description, key_display=b.key_display)
        try:
            footer = self.query_one(Footer)
            footer.refresh()
        except Exception:
            pass

    def action_toggle_mode(self) -> None:
        mode_select = self.query_one("#mode-select", Select)
        idx = self.MODE_ORDER.index(self.mode) if self.mode in self.MODE_ORDER else 0
        next_idx = (idx + 1) % len(self.MODE_ORDER)
        self.mode = self.MODE_ORDER[next_idx]
        mode_select.value = self.mode
        self._update_footer_for_mode(self.mode)
        status = self.query_one("#status-label", Label)
        status.update(f"Mode: {self.mode.title()}")

    def action_toggle_view(self) -> None:
        if self.current_view == "terminal":
            self._switch_view("git")
        else:
            self._switch_view("terminal")

    def action_toggle_ai(self) -> None:
        self.use_ai = not self.use_ai
        ai_label = self.query_one("#ai-label", Label)
        ai_label.update(f"AI: {'ON' if self.use_ai else 'OFF'}")
        status = self.query_one("#status-label", Label)
        status.update(f"AI {'enabled' if self.use_ai else 'disabled'}")

    def action_toggle_theme(self) -> None:
        if self._app_theme == "terminal":
            self._app_theme = "glass"
        else:
            self._app_theme = "terminal"
        save_theme_preference(self._app_theme)
        self._apply_theme_class()
        theme_label = self.query_one("#theme-label", Label)
        theme_label.update(f"Theme: {THEME_NAMES[self._app_theme]}")
        status = self.query_one("#status-label", Label)
        status.update(f"Switched to {THEME_NAMES[self._app_theme]} theme")

    def action_clear_translations(self) -> None:
        self._pending_lines.clear()
        if self._debounce_task is not None:
            self._debounce_task.cancel()
            self._debounce_task = None
        self._translation_id += 1
        if self.current_view == "git":
            git_results = self.query_one("#git-results", RichLog)
            git_results.clear()
            git_results.write("[dim]Git results cleared. Paste a URL to analyze.[/]")
        else:
            trans = self.query_one("#translation-output", RichLog)
            trans.clear()
            trans.write("[dim]Translation panel cleared. Type a command to continue.[/]")

    def on_unmount(self) -> None:
        if self.shell:
            self.shell.stop()

    def action_quit(self) -> None:
        if self.shell:
            self.shell.stop()
        self.exit()


if __name__ == "__main__":
    app = YaketyYak()
    app.run()

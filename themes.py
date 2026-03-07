import json
import os

PREFS_DIR = os.path.join(os.path.expanduser("~"), ".yakety-yak")
PREFS_FILE = os.path.join(PREFS_DIR, "preferences.json")

THEME_NAMES = {
    "terminal": "Terminal",
    "glass": "Glass",
}


def load_theme_preference():
    try:
        with open(PREFS_FILE, "r") as f:
            prefs = json.load(f)
            theme = prefs.get("theme", "terminal")
            if theme in THEME_NAMES:
                return theme
    except (FileNotFoundError, json.JSONDecodeError, KeyError, OSError, PermissionError):
        pass
    return "terminal"


def save_theme_preference(theme):
    try:
        os.makedirs(PREFS_DIR, exist_ok=True)
        prefs = {}
        try:
            with open(PREFS_FILE, "r") as f:
                prefs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        prefs["theme"] = theme
        with open(PREFS_FILE, "w") as f:
            json.dump(prefs, f, indent=2)
    except (OSError, PermissionError):
        pass


APP_CSS = """
Screen {
    layout: vertical;
}

#view-toggle-bar {
    dock: top;
    height: 3;
    layout: horizontal;
    align: center middle;
    padding: 0 1;
}

#view-toggle-bar Button {
    min-width: 18;
    height: 3;
    margin: 0 0;
}

#btn-terminal-view {
    border: none;
}

#btn-git-view {
    border: none;
}

#main-container {
    layout: horizontal;
    height: 1fr;
}

#shell-panel {
    width: 1fr;
    height: 100%;
}

#shell-panel-inner {
    height: 1fr;
}

#shell-title {
    dock: top;
    height: 1;
    text-align: center;
    text-style: bold;
    padding: 0 1;
}

#shell-output {
    height: 1fr;
    scrollbar-size: 1 1;
}

#shell-input {
    dock: bottom;
    height: 3;
}

#translation-panel {
    width: 1fr;
    height: 100%;
}

#translation-panel-inner {
    height: 1fr;
}

#translation-title {
    dock: top;
    height: 1;
    text-align: center;
    text-style: bold;
    padding: 0 1;
}

#translation-output {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#git-container {
    height: 1fr;
    display: none;
}

#git-container.active {
    display: block;
}

#main-container.hidden {
    display: none;
}

#git-panel {
    width: 100%;
    height: 100%;
}

#git-panel-inner {
    height: 1fr;
}

#git-title {
    dock: top;
    height: 1;
    text-align: center;
    text-style: bold;
    padding: 0 1;
}

#git-input-row {
    dock: top;
    height: 3;
    layout: horizontal;
    padding: 0 1;
}

#git-url-input {
    width: 1fr;
}

#btn-analyze {
    min-width: 14;
    height: 3;
    margin: 0 0 0 1;
}

#git-results {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#settings-bar {
    dock: bottom;
    height: 3;
    layout: horizontal;
    padding: 0 1;
}

#settings-bar Label {
    padding: 1 1 0 0;
    width: auto;
}

#mode-select {
    width: 28;
}

#lang-select {
    width: 20;
}

#ai-label {
    padding: 1 1 0 2;
}

#status-label {
    padding: 1 1 0 2;
    width: 1fr;
    text-align: right;
}

#theme-label {
    padding: 1 1 0 2;
}


/* ── Terminal Theme (default) ── */

Screen.theme-terminal {
    background: #060a13;
}

Screen.theme-terminal #view-toggle-bar {
    background: #0a0e17;
    border-bottom: solid #10b98130;
}

Screen.theme-terminal #btn-terminal-view {
    background: #111827;
    color: #94a3b8;
}

Screen.theme-terminal #btn-git-view {
    background: #111827;
    color: #94a3b8;
}

Screen.theme-terminal #btn-terminal-view.active-view {
    background: #10b981;
    color: #0a0e17;
    text-style: bold;
}

Screen.theme-terminal #btn-git-view.active-view {
    background: #10b981;
    color: #0a0e17;
    text-style: bold;
}

Screen.theme-terminal #shell-panel {
    border: solid #10b981;
}

Screen.theme-terminal #shell-title {
    background: #10b981;
    color: #0a0e17;
}

Screen.theme-terminal #shell-output {
    background: #0a0e17;
    color: #e2e8f0;
}

Screen.theme-terminal #shell-input {
    background: #111827;
    color: #e2e8f0;
    border: tall #10b981;
}

Screen.theme-terminal #translation-panel {
    border: solid #10b981;
}

Screen.theme-terminal #translation-title {
    background: #10b981;
    color: #0a0e17;
}

Screen.theme-terminal #translation-output {
    background: #0a0e17;
    color: #e2e8f0;
}

Screen.theme-terminal #git-panel {
    border: solid #10b981;
}

Screen.theme-terminal #git-title {
    background: #10b981;
    color: #0a0e17;
}

Screen.theme-terminal #git-url-input {
    background: #111827;
    color: #e2e8f0;
    border: tall #10b981;
}

Screen.theme-terminal #btn-analyze {
    background: #10b981;
    color: #0a0e17;
    text-style: bold;
}

Screen.theme-terminal #git-results {
    background: #0a0e17;
    color: #e2e8f0;
}

Screen.theme-terminal #settings-bar {
    background: #111827;
}

Screen.theme-terminal #settings-bar Label {
    color: #94a3b8;
}

Screen.theme-terminal #ai-label {
    color: #10b981;
}

Screen.theme-terminal #theme-label {
    color: #10b981;
}

Screen.theme-terminal #status-label {
    color: #64748b;
}

Screen.theme-terminal Header {
    background: #0a0e17;
    color: #10b981;
}

Screen.theme-terminal Footer {
    background: #111827;
    color: #64748b;
}


/* ── Glass Theme ── */

Screen.theme-glass {
    background: #0a0520;
}

Screen.theme-glass #view-toggle-bar {
    background: #0f0a2e;
    border-bottom: solid #6366f130;
}

Screen.theme-glass #btn-terminal-view {
    background: #1a1545;
    color: #a5b4fc;
}

Screen.theme-glass #btn-git-view {
    background: #1a1545;
    color: #a5b4fc;
}

Screen.theme-glass #btn-terminal-view.active-view {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #btn-git-view.active-view {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #shell-panel {
    border: round #6366f1;
}

Screen.theme-glass #shell-title {
    background: #4f46e5;
    color: #e0e7ff;
}

Screen.theme-glass #shell-output {
    background: #0f0a2e;
    color: #c7d2fe;
}

Screen.theme-glass #shell-input {
    background: #1a1545;
    color: #e0e7ff;
    border: round #818cf8;
}

Screen.theme-glass #translation-panel {
    border: round #818cf8;
}

Screen.theme-glass #translation-title {
    background: #6366f1;
    color: #e0e7ff;
}

Screen.theme-glass #translation-output {
    background: #0f0a2e;
    color: #c7d2fe;
}

Screen.theme-glass #git-panel {
    border: round #818cf8;
}

Screen.theme-glass #git-title {
    background: #6366f1;
    color: #e0e7ff;
}

Screen.theme-glass #git-url-input {
    background: #1a1545;
    color: #e0e7ff;
    border: round #818cf8;
}

Screen.theme-glass #btn-analyze {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #git-results {
    background: #0f0a2e;
    color: #c7d2fe;
}

Screen.theme-glass #settings-bar {
    background: #1a1545;
}

Screen.theme-glass #settings-bar Label {
    color: #a5b4fc;
}

Screen.theme-glass #ai-label {
    color: #a78bfa;
}

Screen.theme-glass #theme-label {
    color: #a78bfa;
}

Screen.theme-glass #status-label {
    color: #6366f1;
}

Screen.theme-glass Header {
    background: #0f0a2e;
    color: #a78bfa;
}

Screen.theme-glass Footer {
    background: #1a1545;
    color: #6366f1;
}
"""

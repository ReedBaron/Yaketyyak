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


def load_license_key():
    try:
        with open(PREFS_FILE, "r") as f:
            prefs = json.load(f)
            return prefs.get("license_key", "")
    except (FileNotFoundError, json.JSONDecodeError, OSError, PermissionError):
        return ""


def save_license_key(key):
    try:
        os.makedirs(PREFS_DIR, exist_ok=True)
        prefs = {}
        try:
            with open(PREFS_FILE, "r") as f:
                prefs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        prefs["license_key"] = key
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
    min-width: 20;
    height: 3;
    margin: 0 1 0 0;
    text-style: bold;
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
    padding: 0 1;
}

#shell-panel {
    width: 1fr;
    height: 100%;
    margin: 0 1 0 0;
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
    content-align: center middle;
}

#shell-output {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 0 1;
}

#shell-input {
    dock: bottom;
    height: 3;
    margin: 0 1;
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
    content-align: center middle;
}

#translation-output {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 1 2;
}

#git-container {
    height: 1fr;
    display: none;
    padding: 0 1;
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
    padding: 1 1 0 1;
}

#git-url-input {
    width: 1fr;
}

#btn-analyze {
    min-width: 16;
    height: 3;
    margin: 0 0 0 1;
    text-style: bold;
}

#git-results {
    height: 1fr;
    scrollbar-size: 1 1;
    padding: 1 2;
}

#settings-bar {
    dock: bottom;
    height: 3;
    layout: horizontal;
    padding: 0 2;
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
    text-style: bold;
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
    background: #050810;
}

Screen.theme-terminal #view-toggle-bar {
    background: #080c16;
    border-bottom: solid #10b981;
}

Screen.theme-terminal #btn-terminal-view {
    background: #0d1420;
    color: #4b5e75;
}

Screen.theme-terminal #btn-git-view {
    background: #0d1420;
    color: #4b5e75;
}

Screen.theme-terminal #btn-terminal-view.active-view {
    background: #10b981;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #btn-git-view.active-view {
    background: #10b981;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #shell-panel {
    border: double #10b981;
    background: #070b14;
}

Screen.theme-terminal #shell-title {
    background: #10b981;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #shell-output {
    background: #070b14;
    color: #e2e8f0;
}

Screen.theme-terminal #shell-input {
    background: #0d1420;
    color: #10b981;
    border: tall #10b981;
}

Screen.theme-terminal #translation-panel {
    border: double #059669;
    background: #070b14;
}

Screen.theme-terminal #translation-title {
    background: #059669;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #translation-output {
    background: #070b14;
    color: #d1d5db;
}

Screen.theme-terminal #git-panel {
    border: double #10b981;
    background: #070b14;
}

Screen.theme-terminal #git-title {
    background: #10b981;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #git-url-input {
    background: #0d1420;
    color: #10b981;
    border: tall #10b981;
}

Screen.theme-terminal #btn-analyze {
    background: #10b981;
    color: #050810;
    text-style: bold;
}

Screen.theme-terminal #git-results {
    background: #070b14;
    color: #d1d5db;
}

Screen.theme-terminal #settings-bar {
    background: #080c16;
    border-top: solid #10b981;
}

Screen.theme-terminal #settings-bar Label {
    color: #6b8299;
}

Screen.theme-terminal #settings-bar Select > SelectCurrent {
    background: #0d1420;
    color: #10b981;
}

Screen.theme-terminal #ai-label {
    color: #10b981;
    text-style: bold;
}

Screen.theme-terminal #theme-label {
    color: #059669;
}

Screen.theme-terminal #status-label {
    color: #4b5e75;
}

Screen.theme-terminal Header {
    background: #050810;
    color: #10b981;
    text-style: bold;
}

Screen.theme-terminal Footer {
    background: #080c16;
    color: #4b5e75;
}


/* ── Glass Theme ── */

Screen.theme-glass {
    background: #08041a;
}

Screen.theme-glass #view-toggle-bar {
    background: #0c0824;
    border-bottom: solid #6366f1;
}

Screen.theme-glass #btn-terminal-view {
    background: #141040;
    color: #6366f1;
}

Screen.theme-glass #btn-git-view {
    background: #141040;
    color: #6366f1;
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
    border: round #818cf8;
    background: #0c0826;
}

Screen.theme-glass #shell-title {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #shell-output {
    background: #0c0826;
    color: #c7d2fe;
}

Screen.theme-glass #shell-input {
    background: #141040;
    color: #a5b4fc;
    border: round #818cf8;
}

Screen.theme-glass #translation-panel {
    border: round #a78bfa;
    background: #0c0826;
}

Screen.theme-glass #translation-title {
    background: #7c3aed;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #translation-output {
    background: #0c0826;
    color: #ddd6fe;
}

Screen.theme-glass #git-panel {
    border: round #818cf8;
    background: #0c0826;
}

Screen.theme-glass #git-title {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #git-url-input {
    background: #141040;
    color: #a5b4fc;
    border: round #818cf8;
}

Screen.theme-glass #btn-analyze {
    background: #6366f1;
    color: #e0e7ff;
    text-style: bold;
}

Screen.theme-glass #git-results {
    background: #0c0826;
    color: #ddd6fe;
}

Screen.theme-glass #settings-bar {
    background: #0c0824;
    border-top: solid #6366f1;
}

Screen.theme-glass #settings-bar Label {
    color: #818cf8;
}

Screen.theme-glass #settings-bar Select > SelectCurrent {
    background: #141040;
    color: #a5b4fc;
}

Screen.theme-glass #ai-label {
    color: #a78bfa;
    text-style: bold;
}

Screen.theme-glass #theme-label {
    color: #a78bfa;
}

Screen.theme-glass #status-label {
    color: #6366f1;
}

Screen.theme-glass Header {
    background: #08041a;
    color: #a78bfa;
    text-style: bold;
}

Screen.theme-glass Footer {
    background: #0c0824;
    color: #6366f1;
}
"""

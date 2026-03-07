#!/usr/bin/env python3
import subprocess
import sys
import platform
import os
import shutil
import stat
import plistlib
import argparse


APP_NAME = "Yakety Yak"
EXECUTABLE_NAME = "yakety-yak"
BUNDLE_ID = "com.yaketyyak.app"
VERSION = "1.0.1"
OLLAMA_MODEL = "qwen2.5-coder:1.5b"
ICON_SOURCE = "static/yak-app-icon.png"

HIDDEN_IMPORTS = [
    "textual", "textual.app", "textual.widgets", "textual.containers",
    "textual.binding", "textual.reactive", "textual.message",
    "textual._xterm_parser", "textual.css", "textual.css.query",
    "textual.css.stylesheet", "textual.dom", "textual.screen",
    "textual.widget", "textual.driver", "textual.drivers",
    "textual.drivers.linux_driver", "textual._linux_driver",
    "textual._animator", "textual._timer", "textual._worker_manager",
    "textual.worker", "textual.events", "textual.geometry",
    "textual.strip", "textual.renderables", "textual.renderables.gradient",
    "textual.widgets._header", "textual.widgets._footer",
    "textual.widgets._static", "textual.widgets._input",
    "textual.widgets._label", "textual.widgets._select",
    "textual.widgets._rich_log",
    "rich", "rich.text", "rich.console", "rich.markup",
    "rich.segment", "rich.style", "rich.color", "rich.terminal_theme",
    "openai", "pexpect", "translator", "knowledge_base", "themes",
]


def build_executable():
    system = platform.system().lower()
    if system == "windows":
        print("Error: Yakety Yak requires a Unix-like terminal (pty, fork).")
        print("It works on macOS, Linux, and Windows WSL.")
        print("To build for Windows, use WSL (Windows Subsystem for Linux).")
        sys.exit(1)

    print(f"Building Yakety Yak for {platform.system()} ({platform.machine()})...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--name", EXECUTABLE_NAME,
        "--console", "--clean", "--noconfirm", "app.py",
    ]

    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    try:
        import textual as _t
        css_dir = os.path.join(os.path.dirname(_t.__file__), "css")
        if os.path.isdir(css_dir):
            cmd.extend(["--add-data", f"{css_dir}{os.pathsep}textual/css"])
    except ImportError:
        pass

    print("Compiling executable...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    exe_path = os.path.join("dist", EXECUTABLE_NAME)
    if result.returncode != 0 or not os.path.exists(exe_path):
        print("Build failed!")
        print(result.stderr[-2000:] if result.stderr else "No error output")
        sys.exit(1)

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"Executable built: {exe_path} ({size_mb:.1f} MB)")
    return exe_path


def create_icns(source_png, output_path):
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not available, skipping icon generation")
        return False

    if not os.path.exists(source_png):
        print(f"  Icon source not found: {source_png}")
        return False

    print(f"  Generating .icns from {source_png}...")
    img = Image.open(source_png).convert("RGBA")

    iconset_dir = output_path + ".iconset"
    if os.path.exists(iconset_dir):
        shutil.rmtree(iconset_dir)
    os.makedirs(iconset_dir)

    sizes = [16, 32, 64, 128, 256, 512]
    for size in sizes:
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, f"icon_{size}x{size}.png"))
        retina = img.resize((size * 2, size * 2), Image.LANCZOS)
        retina.save(os.path.join(iconset_dir, f"icon_{size}x{size}@2x.png"))

    try:
        result = subprocess.run(
            ["iconutil", "-c", "icns", iconset_dir, "-o", output_path],
            capture_output=True, text=True
        )
        if result.returncode == 0 and os.path.exists(output_path):
            shutil.rmtree(iconset_dir)
            print(f"  Icon created: {output_path}")
            return True
    except FileNotFoundError:
        pass

    print("  iconutil not available, creating PNG-based icon fallback")
    icon_img = img.resize((512, 512), Image.LANCZOS)
    icon_img.save(output_path.replace(".icns", ".png"))
    shutil.rmtree(iconset_dir)
    return False


def create_macos_app(exe_path):
    print("\nCreating macOS app bundle...")

    app_dir = os.path.join("dist", f"{APP_NAME}.app")
    contents_dir = os.path.join(app_dir, "Contents")
    macos_dir = os.path.join(contents_dir, "MacOS")
    resources_dir = os.path.join(contents_dir, "Resources")

    if os.path.exists(app_dir):
        shutil.rmtree(app_dir)

    os.makedirs(macos_dir)
    os.makedirs(resources_dir)

    shutil.copy2(exe_path, os.path.join(macos_dir, EXECUTABLE_NAME))

    icns_path = os.path.join(resources_dir, "AppIcon.icns")
    has_icon = create_icns(ICON_SOURCE, icns_path)

    launcher_path = os.path.join(macos_dir, "launcher")
    with open(launcher_path, "w") as f:
        f.write(f"""#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
EXEC="$DIR/{EXECUTABLE_NAME}"

if [ -t 0 ] && [ -t 1 ]; then
    exec "$EXEC"
else
    osascript -e '
        tell application "Terminal"
            activate
            do script "clear && \\"'"$EXEC"'\\" ; exit"
        end tell
    '
fi
""")
    os.chmod(launcher_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)

    info_plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "CFBundleExecutable": "launcher",
        "CFBundlePackageType": "APPL",
        "CFBundleSignature": "????",
        "CFBundleInfoDictionaryVersion": "6.0",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.developer-tools",
        "NSHumanReadableCopyright": f"Yakety Yak {VERSION}",
    }

    if has_icon:
        info_plist["CFBundleIconFile"] = "AppIcon"

    with open(os.path.join(contents_dir, "Info.plist"), "wb") as f:
        plistlib.dump(info_plist, f)

    print(f"macOS app bundle created: {app_dir}")
    return app_dir


def create_linux_launcher(exe_path):
    print("\nCreating Linux launcher...")

    launcher_dir = os.path.join("dist", "linux-package")
    bin_dir = os.path.join(launcher_dir, "bin")
    apps_dir = os.path.join(launcher_dir, "share", "applications")

    if os.path.exists(launcher_dir):
        shutil.rmtree(launcher_dir)

    os.makedirs(bin_dir)
    os.makedirs(apps_dir)
    shutil.copy2(exe_path, os.path.join(bin_dir, EXECUTABLE_NAME))

    with open(os.path.join(apps_dir, f"{EXECUTABLE_NAME}.desktop"), "w") as f:
        f.write(f"""[Desktop Entry]
Name={APP_NAME}
Comment=Learn the terminal with real-time command explanations
Exec={EXECUTABLE_NAME}
Terminal=true
Type=Application
Categories=Development;Education;
Keywords=terminal;cli;learn;translate;command;
StartupNotify=false
""")

    install_path = os.path.join(launcher_dir, "install.sh")
    with open(install_path, "w") as f:
        f.write(f"""#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local"
BIN_DIR="$INSTALL_DIR/bin"
APPS_DIR="$INSTALL_DIR/share/applications"

echo "Installing {APP_NAME}..."
echo ""

mkdir -p "$BIN_DIR"
mkdir -p "$APPS_DIR"

cp "$SCRIPT_DIR/bin/{EXECUTABLE_NAME}" "$BIN_DIR/{EXECUTABLE_NAME}"
chmod +x "$BIN_DIR/{EXECUTABLE_NAME}"

cat > "$APPS_DIR/{EXECUTABLE_NAME}.desktop" << DESKTOP
[Desktop Entry]
Name={APP_NAME}
Comment=Learn the terminal with real-time command explanations
Exec=$BIN_DIR/{EXECUTABLE_NAME}
Terminal=true
Type=Application
Categories=Development;Education;
Keywords=terminal;cli;learn;translate;command;
StartupNotify=false
DESKTOP

echo "Installed successfully!"
echo ""
echo "You can now:"
echo "  1. Find '{APP_NAME}' in your application menu"
echo "  2. Or run it from terminal: {EXECUTABLE_NAME}"
echo ""

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "Note: Add $BIN_DIR to your PATH if the command isn't found:"
    echo "  echo 'export PATH=\\"$BIN_DIR:\\$PATH\\"' >> ~/.bashrc"
    echo ""
fi

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi
""")
    _make_executable(install_path)

    uninstall_path = os.path.join(launcher_dir, "uninstall.sh")
    with open(uninstall_path, "w") as f:
        f.write(f"""#!/bin/bash
echo "Uninstalling {APP_NAME}..."

rm -f "$HOME/.local/bin/{EXECUTABLE_NAME}"
rm -f "$HOME/.local/share/applications/{EXECUTABLE_NAME}.desktop"
rm -rf "$HOME/.yakety-yak"

if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
fi

echo "Uninstalled successfully!"
""")
    _make_executable(uninstall_path)

    print(f"Linux package created: {launcher_dir}/")
    return launcher_dir


def create_ollama_setup_scripts(output_dir):
    print("\nCreating Ollama setup scripts...")

    setup_mac = os.path.join(output_dir, "setup-ai-mac.sh")
    with open(setup_mac, "w") as f:
        f.write(f"""#!/bin/bash
set -e

echo "====================================="
echo "  Yakety Yak - AI Setup"
echo "====================================="
echo ""

if command -v ollama &> /dev/null; then
    echo "Ollama is already installed!"
else
    echo "Installing Ollama..."
    echo "This will download about 300 MB."
    echo ""

    if command -v brew &> /dev/null; then
        brew install ollama
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    echo ""
    echo "Ollama installed!"
fi

echo ""
echo "Starting Ollama..."
ollama serve &>/dev/null &
sleep 3

echo "Downloading AI model ({OLLAMA_MODEL})..."
echo "This will download about 1 GB (one-time only)."
echo ""
ollama pull {OLLAMA_MODEL}

echo ""
echo "====================================="
echo "  AI Setup Complete!"
echo "====================================="
echo ""
echo "You can now open Yakety Yak."
echo "AI translations are ready to go!"
echo ""
echo "Ollama will start automatically when you"
echo "open Yakety Yak."
echo ""
""")
    _make_executable(setup_mac)

    setup_linux = os.path.join(output_dir, "setup-ai-linux.sh")
    with open(setup_linux, "w") as f:
        f.write(f"""#!/bin/bash
set -e

echo "====================================="
echo "  Yakety Yak - AI Setup"
echo "====================================="
echo ""

if command -v ollama &> /dev/null; then
    echo "Ollama is already installed!"
else
    echo "Installing Ollama..."
    echo "This will download about 300 MB."
    echo ""
    curl -fsSL https://ollama.com/install.sh | sh
    echo ""
    echo "Ollama installed!"
fi

echo ""
echo "Starting Ollama..."
ollama serve &>/dev/null &
sleep 3

echo "Downloading AI model ({OLLAMA_MODEL})..."
echo "This will download about 1 GB (one-time only)."
echo ""
ollama pull {OLLAMA_MODEL}

echo ""
echo "====================================="
echo "  AI Setup Complete!"
echo "====================================="
echo ""
echo "You can now open Yakety Yak."
echo "AI translations are ready to go!"
echo ""
echo "To start Ollama on boot, run:"
echo "  sudo systemctl enable ollama"
echo ""
""")
    _make_executable(setup_linux)

    print(f"AI setup scripts created in {output_dir}/")
    return setup_mac, setup_linux


def _make_executable(path):
    os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def build():
    parser = argparse.ArgumentParser(description="Build Yakety Yak")
    parser.add_argument("--lite", action="store_true", help="Build Lite edition only (no AI setup)")
    parser.add_argument("--full", action="store_true", help="Build Full edition with AI setup scripts")
    args = parser.parse_args()

    if not args.lite and not args.full:
        args.lite = True
        args.full = True

    system = platform.system().lower()
    exe_path = build_executable()

    if system == "darwin":
        create_macos_app(exe_path)
    elif system == "linux":
        create_linux_launcher(exe_path)

    if args.full:
        full_dir = os.path.join("dist", "full-edition")
        os.makedirs(full_dir, exist_ok=True)
        shutil.copy2(exe_path, os.path.join(full_dir, EXECUTABLE_NAME))
        create_ollama_setup_scripts(full_dir)

        if system == "darwin":
            app_dir = os.path.join("dist", f"{APP_NAME}.app")
            if os.path.exists(app_dir):
                full_app = os.path.join(full_dir, f"{APP_NAME}.app")
                if os.path.exists(full_app):
                    shutil.rmtree(full_app)
                shutil.copytree(app_dir, full_app)

        if system == "linux":
            pkg_dir = os.path.join("dist", "linux-package")
            if os.path.exists(pkg_dir):
                full_pkg = os.path.join(full_dir, "linux-package")
                if os.path.exists(full_pkg):
                    shutil.rmtree(full_pkg)
                shutil.copytree(pkg_dir, full_pkg)

    print("\n" + "=" * 56)
    print(f"  BUILD COMPLETE — {APP_NAME} v{VERSION}")
    print("=" * 56)

    if args.lite:
        print(f"\n  LITE EDITION:")
        print(f"    dist/{EXECUTABLE_NAME} ({os.path.getsize(exe_path) / 1024 / 1024:.1f} MB)")
        if system == "darwin":
            print(f"    dist/{APP_NAME}.app (drag to Applications)")
        elif system == "linux":
            print(f"    dist/linux-package/ (run install.sh)")

    if args.full:
        print(f"\n  FULL EDITION + AI:")
        print(f"    dist/full-edition/")
        print(f"    Includes app + Ollama setup scripts")
        if system == "darwin":
            print(f"    Run setup-ai-mac.sh to install Ollama + AI model")
        elif system == "linux":
            print(f"    Run setup-ai-linux.sh to install Ollama + AI model")

    print("")


if __name__ == "__main__":
    build()

#!/usr/bin/env python3

import os
import subprocess
import sys
import signal
from shutil import which
import re
import argparse


def detect_methods():
    methods = []

    if detect_tmux():
        methods.append('tmux')

    if detect_iterm():
        methods.append('iterm')

    if which('gnome-terminal'):
        methods.append('gnome-terminal')

    methods.append('inline')
    return methods


def detect_iterm():
    if os.environ.get("TERM_PROGRAM") == "iTerm.app":
        return True

    try:
        result = subprocess.run(
            ['osascript', '-e',
             'tell application "System Events" to (name of processes) contains "iTerm"'],
            capture_output=True, text=True
        )
        return 'true' in result.stdout.lower()
    except Exception:
        return False


def detect_tmux():
    return which('tmux') is not None


def enable_tmux_mouse():
    tmux_conf = os.path.expanduser("~/.tmux.conf")

    if os.path.exists(tmux_conf):
        with open(tmux_conf, 'r') as f:
            lines = f.readlines()
        if any("set -g mouse" in line and not line.strip().startswith("#") for line in lines):
            print("🖱️  Mouse support already enabled in ~/.tmux.conf.")
            return
    else:
        lines = []

    print("🖱️  Enabling mouse support in ~/.tmux.conf...")
    lines.append("\n# Enable mouse support\nset -g mouse on\n")
    with open(tmux_conf, 'w') as f:
        f.writelines(lines)

    subprocess.run(["tmux", "source-file", tmux_conf])
    print("✅ Mouse support enabled and tmux config reloaded.")


def check_or_start_tmux_session(project):
    if 'TMUX' in os.environ:
        return True  # already inside tmux

    result = subprocess.run(['tmux', 'ls'], capture_output=True, text=True)

    if project in result.stdout:
        print(f"⚠️ Session '{project}' already exists.")
        while True:
            choice = input("👉 [a]ttach / [k]ill & restart / [q]uit: ").strip().lower()
            if choice == 'a':
                subprocess.run(['tmux', 'attach-session', '-t', project])
                sys.exit(0)
            elif choice == 'k':
                subprocess.run(['tmux', 'kill-session', '-t', project])
                break
            elif choice == 'q':
                print("👋 Goodbye.")
                sys.exit(0)
            else:
                print("⚠️ Invalid choice. Try again.")

    print(f"🪄 Starting a new tmux session named: {project}")
    subprocess.run([
        'tmux', 'new-session', '-s', project,
        f'python3 {sys.argv[0]} --method tmux'
    ])
    sys.exit(0)


def get_project_name():
    return os.path.basename(os.getcwd())


def list_containers(project):
    result = subprocess.run(
        ['docker', 'ps', '--filter', f'name={project}', '--format', '{{.Names}}'],
        capture_output=True, text=True
    )
    containers = result.stdout.strip().splitlines()
    return containers


def open_tmux_split(container):
    print(f"🚀 Opening in tmux split-pane: {container}")
    subprocess.Popen([
        'tmux', 'split-window', '-v',
        f"docker exec -it {container} bash"
    ])
    subprocess.Popen(['tmux', 'select-layout', 'tiled'])


def open_iterm(container):
    print(f"🚀 Opening in iTerm2 tab: {container}")
    script = f'''
    tell application "iTerm"
        create window with default profile
        tell current session of current window
            write text "docker exec -it {container} bash"
        end tell
    end tell
    '''
    subprocess.Popen(['osascript', '-e', script])


def open_gnome(container):
    print(f"🚀 Opening in gnome-terminal: {container}")
    subprocess.Popen([
        'gnome-terminal', '--', 'bash', '-c',
        f"docker exec -it {container} bash; exec bash"
    ])


def open_inline(container):
    print(f"🚀 Connecting inline: {container} (menu will block)")
    subprocess.run(['docker', 'exec', '-it', container, 'bash'])


def handle_sigint(signum, frame):
    print("\n⚠️ Use the menu to quit instead of Ctrl+C!")


def choose_method(available_methods):
    print("\n📋 Choose how to open the container session:")
    for idx, m in enumerate(available_methods, 1):
        print(f"  {idx}. {m}")
    print("  q. Quit")

    while True:
        choice = input("👉 Your choice [number or 'q']: ").strip().lower()
        if choice == 'q':
            print("👋 Goodbye.")
            sys.exit(0)
        elif choice.isdigit() and 1 <= int(choice) <= len(available_methods):
            return available_methods[int(choice) - 1]
        print("⚠️ Invalid choice. Try again.")


def connect(container, method, project):
    if method == 'tmux':
        enable_tmux_mouse()
        show_tmux_cheat_sheet()
        open_tmux_split(container)
    elif method == 'iterm':
        open_iterm(container)
    elif method == 'gnome-terminal':
        open_gnome(container)
    else:
        open_inline(container)


def show_tmux_cheat_sheet():
    cheat = []
    color_prefix = "\033[96m"
    color_key = "\033[92m"
    color_reset = "\033[0m"

    def line(text=""):
        cheat.append(text)

    line(f"\n🎹 {color_prefix}Tmux Cheat Sheet{color_reset}")
    line("─────────────────────────────────────────────")
    line(f"🪄 {color_key}Prefix key (default):{color_reset} Ctrl+b\n")
    line(f"🔷 {color_key}Common Commands:{color_reset}")
    line(f"  {color_key}Pane Navigation:{color_reset}")
    line(f"    → Move between panes:       {color_key}Prefix + ← ↑ ↓ →{color_reset}")
    line(f"    → Cycle through panes:      {color_key}Prefix + o{color_reset}")
    line(f"    → Zoom current pane:        {color_key}Prefix + z{color_reset}\n")
    line(f"  {color_key}Pane Management:{color_reset}")
    line(f"    → Split horizontally:       {color_key}Prefix + \"{color_reset}")
    line(f"    → Split vertically:         {color_key}Prefix + %{color_reset}")
    line(f"    → Close current pane:       {color_key}exit or Ctrl+d{color_reset}")
    line(f"    → Swap panes:               {color_key}Prefix + Ctrl+o{color_reset}\n")
    line(f"  {color_key}Window Management:{color_reset}")
    line(f"    → New window:               {color_key}Prefix + c{color_reset}")
    line(f"    → Next window:              {color_key}Prefix + n{color_reset}")
    line(f"    → Previous window:          {color_key}Prefix + p{color_reset}")
    line(f"    → List windows:             {color_key}Prefix + w{color_reset}\n")
    line(f"  {color_key}Misc:{color_reset}")
    line(f"    → Show pane numbers:        {color_key}Prefix + q{color_reset}")
    line(f"    → Resize pane:              {color_key}Prefix + hold ← ↑ ↓ →{color_reset}")
    line(f"    → Detach from tmux:         {color_key}Prefix + d{color_reset}")
    line("─────────────────────────────────────────────\n")

    print("\n".join(cheat))

    plain_cheat = "\n".join([strip_ansi(c) for c in cheat])
    with open("tmux-cheatsheet.txt", "w") as f:
        f.write(plain_cheat)
    print("📄 Cheat sheet saved to: tmux-cheatsheet.txt")


def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Connect to Docker containers interactively"
    )
    parser.add_argument('--method', choices=['tmux', 'iterm', 'gnome-terminal', 'inline'],
                        help='Terminal method to use (skip menu)')
    return parser.parse_args()


def main():
    signal.signal(signal.SIGINT, handle_sigint)

    args = parse_args()
    project = get_project_name()
    print(f"🔍 Looking for containers in project: {project}")

    if args.method:
        method = args.method
    else:
        available_methods = detect_methods()
        print(f"✅ Detected available terminal methods: {', '.join(available_methods)}")
        method = choose_method(available_methods)

    if method == 'tmux':
        if 'TMUX' not in os.environ:
            check_or_start_tmux_session(project)
        else:
            enable_tmux_mouse()
            show_tmux_cheat_sheet()

    while True:
        containers = list_containers(project)
        if not containers:
            print("❌ No running containers found for this project.")
            sys.exit(0)

        print("\n📋 Available containers:")
        for idx, c in enumerate(containers, 1):
            print(f"  {idx}. {c}")
        print("  a. Connect to ALL containers")
        print("  q. Quit")

        choice = input("👉 Enter number, 'a' for all, or 'q' to quit: ").strip().lower()
        if choice == 'q':
            print("👋 Goodbye.")
            break
        elif choice == 'a':
            for c in containers:
                connect(c, method, project)
            continue
        elif choice.isdigit() and 1 <= int(choice) <= len(containers):
            connect(containers[int(choice) - 1], method, project)
        else:
            print("⚠️ Invalid choice. Try again.")


if __name__ == "__main__":
    main()

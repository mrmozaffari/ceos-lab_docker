#!/usr/bin/env python3

import os
import subprocess
import sys
import signal
from shutil import which
import re
import argparse
import threading
import time

# ========== SPINNER ==========

def spinner(msg, stop_event):
    symbols = ['⏳', '⌛', '🕒', '🕓', '🕔', '🕕']
    i = 0
    while not stop_event.is_set():
        print(f"\r{msg} {symbols[i % len(symbols)]}", end='', flush=True)
        i += 1
        time.sleep(0.2)
    print('\r', end='', flush=True)

def run_with_spinner(cmd, msg):
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=(msg, stop_event))
    t.start()
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    stop_event.set()
    t.join()

# ========== UTILS ==========

def parse_args():
    parser = argparse.ArgumentParser(description="Manage and connect to your cEOS lab.")
    parser.add_argument('--method', choices=['tmux', 'iterm', 'gnome-terminal', 'inline'],
                        help='Preferred connection method (skip menu)')
    return parser.parse_args()

def detect_methods():
    methods = []
    if which('tmux'): methods.append('tmux')
    if os.environ.get("TERM_PROGRAM") == "iTerm.app": methods.append('iterm')
    if which('gnome-terminal'): methods.append('gnome-terminal')
    methods.append('inline')
    return methods

def get_project_name():
    return os.path.basename(os.getcwd())

def list_containers(project):
    result = subprocess.run(
        ['docker', 'ps', '-a', '--filter', f'name={project}', '--format', '{{.Names}}'],
        capture_output=True, text=True
    )
    return result.stdout.strip().splitlines()

def container_is_running(container):
    result = subprocess.run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', container],
        capture_output=True, text=True
    )
    return result.stdout.strip() == 'true'

# ========== DOCKER ACTIONS WITH SPINNER ==========

def start_container(container):
    run_with_spinner(['docker', 'start', container], f"🚀 Starting {container}…")
    print(f"✅ {container} started.")

def stop_container(container):
    run_with_spinner(['docker', 'stop', container], f"🛑 Stopping {container}…")
    print(f"✅ {container} stopped.")

def restart_container(container):
    run_with_spinner(['docker', 'restart', container], f"🔄 Restarting {container}…")
    print(f"✅ {container} restarted.")

# ========== MENU ==========

def main_menu():
    while True:
        print("\n📋 What would you like to do?")
        print("  1. 🚀 Start lab (docker-compose up -d)")
        print("  2. 🔗 Connect to containers")
        print("  3. 🛑 Stop lab (docker-compose down)")
        print("  4. 🔄 Lab control panel (restart/shutdown containers)")
        print("  5. 📊 Lab status")
        print("  q. ❌ Quit")
        choice = input("👉 Your choice: ").strip().lower()

        if choice == '1':
            start_lab()
        elif choice == '2':
            connect_to_lab()
        elif choice == '3':
            stop_lab()
        elif choice == '4':
            lab_control_panel()
        elif choice == '5':
            lab_status()
        elif choice == 'q':
            print("👋 Goodbye!")
            sys.exit(0)
        else:
            print("⚠️ Invalid choice.")

def start_lab():
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        return
    project = get_project_name()
    running = [c for c in list_containers(project) if container_is_running(c)]
    if running:
        print("\n" + "═" * 60)
        print(f"✅ Lab already running with {len(running)} container(s):")
        for c in running:
            print(f"   🔷 {c}")
        print("═" * 60)
        return
    print("🚀 Starting lab…")
    run_with_spinner(['docker-compose', 'up', '-d'], "🚀 Starting lab…")
    print("✅ Lab started.")

def stop_lab():
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        return
    project = get_project_name()
    running = [c for c in list_containers(project) if container_is_running(c)]
    if not running:
        print("ℹ️ Lab is not currently running.")
        return
    print("🛑 Stopping lab…")
    run_with_spinner(['docker-compose', 'down'], "🛑 Stopping lab…")
    print("✅ Lab stopped.")

def lab_control_panel():
    project = get_project_name()
    containers = list_containers(project)
    if not containers:
        print("ℹ️ No containers to control.")
        return
    while True:
        print("\n📋 Containers:")
        for idx, c in enumerate(containers, 1):
            status = "🟢 (running)" if container_is_running(c) else "🔴 (stopped)"
            print(f"  {idx}. {c} {status}")
        print("  a. 🔄 Restart ALL")
        print("  q. 🔙 Back")
        choice = input("👉 Enter number, 'a' or 'q': ").strip().lower()
        if choice == 'q':
            return
        elif choice == 'a':
            for c in containers:
                restart_container(c)
        elif choice.isdigit() and 1 <= int(choice) <= len(containers):
            container_action(containers[int(choice)-1], detect_methods()[0], project)
        else:
            print("⚠️ Invalid choice.")

def lab_status():
    project = get_project_name()
    containers = list_containers(project)
    if not containers:
        print("ℹ️ No containers found.")
        return
    print("\n📊 Lab Status:")
    for c in containers:
        if container_is_running(c):
            print(f"  🟢 {c}")
        else:
            print(f"  🔴 {c}")

def container_action(container, method, project):
    while True:
        is_running = container_is_running(container)
        print(f"\n📋 What do you want to do with {container}?")
        if is_running:
            print("  1. 🔗 Connect")
            print("  2. 🔄 Restart")
            print("  3. 🛑 Stop")
        else:
            print("  1. 🔗 Connect (unavailable — stopped)")
            print("  2. 🔄 Restart")
            print("  3. 🚀 Start")
        print("  q. Back")
        choice = input("👉 Your choice: ").strip().lower()
        if choice == '1':
            if not is_running:
                print("⚠️ Cannot connect — container is stopped.")
            else:
                connect(container, method, project)
        elif choice == '2':
            restart_container(container)
        elif choice == '3':
            if is_running:
                stop_container(container)
            else:
                start_container(container)
        elif choice == 'q':
            return
        else:
            print("⚠️ Invalid choice.")

def connect_to_lab():
    project = get_project_name()
    methods = detect_methods()

    # ✅ FIX: already inside tmux? just proceed
    if 'TMUX' in os.environ:
        method = 'tmux'
    else:
        method = choose_method(methods)
        if not method:
            return

        if method == 'tmux':
            start_tmux_session(project)
            return  # relaunches itself in tmux

    if method == 'tmux':
        enable_tmux_mouse()
        show_tmux_cheat_sheet()

    container_menu(method, project)

def container_menu(method, project):
    while True:
        containers = list_containers(project)
        if not containers:
            print("❌ No containers found.")
            return
        print("\n📋 Available containers:")
        for idx, c in enumerate(containers, 1):
            status = "🟢 (running)" if container_is_running(c) else "🔴 (stopped)"
            print(f"  {idx}. {c} {status}")
        print("  a. Connect to ALL")
        print("  q. Back")
        choice = input("👉 Enter number, 'a' or 'q': ").strip().lower()
        if choice == 'q':
            if method == 'tmux' and 'TMUX' in os.environ:
                subprocess.run(['tmux', 'kill-session', '-t', project])
            return
        elif choice == 'a':
            for c in containers:
                connect(c, method, project)
        elif choice.isdigit() and 1 <= int(choice) <= len(containers):
            container_action(containers[int(choice)-1], method, project)
        else:
            print("⚠️ Invalid choice.")

def start_tmux_session(project):
    result = subprocess.run(['tmux', 'ls'], capture_output=True, text=True)
    if project in result.stdout:
        subprocess.run(['tmux', 'attach-session', '-t', project])
    else:
        subprocess.Popen([
            'tmux', 'new-session', '-s', project,
            f'python3 {sys.argv[0]} --method tmux'
        ]).wait()

def choose_method(methods):
    print("\n📋 Choose terminal method:")
    for idx, m in enumerate(methods, 1):
        print(f"  {idx}. {m}")
    print("  q. Back")
    while True:
        choice = input("👉 Your choice [number or 'q']: ").strip().lower()
        if choice == 'q':
            return None
        elif choice.isdigit() and 1 <= int(choice) <= len(methods):
            return methods[int(choice)-1]
        print("⚠️ Invalid choice.")

def enable_tmux_mouse():
    conf = os.path.expanduser("~/.tmux.conf")
    with open(conf, "a") as f:
        f.write("\nset -g mouse on\n")
    subprocess.run(['tmux', 'source-file', conf])

def show_tmux_cheat_sheet():
    sheet = "\n🎹 Tmux Cheat Sheet\n" + "-"*30 + """
🪄 Prefix: Ctrl+b
🔷 Navigate Panes: Prefix + arrows
🔷 Split Horizontally: Prefix + "
🔷 Split Vertically: Prefix + %
🔷 Zoom Pane: Prefix + z
🔷 Cycle Layouts: Prefix + Space
🔷 Detach: Prefix + d
"""
    print(sheet)
    with open("tmux-cheatsheet.txt", "w") as f:
        f.write(strip_ansi(sheet))
    print("📄 Cheat sheet saved to tmux-cheatsheet.txt")

def strip_ansi(text):
    return re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', text)

def connect(container, method, project):
    if method == 'tmux':
        subprocess.Popen(['tmux', 'split-window', '-v', f"docker exec -it {container} Cli"])
        subprocess.Popen(['tmux', 'select-layout', 'tiled'])
    elif method == 'iterm':
        subprocess.Popen(['osascript', '-e', f'tell app "iTerm" to create window with default profile and write text \"docker exec -it {container} Cli\"'])
    elif method == 'gnome-terminal':
        subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f"docker exec -it {container} Cli; exec bash"])
    else:
        subprocess.run(['docker', 'exec', '-it', container, 'Cli'])

def handle_sigint(sig, frame):
    print("\n⚠️ Use menu to quit. Press 'q'.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    args = parse_args()
    if args.method:
        connect_to_lab()
    else:
        main_menu()

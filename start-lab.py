#!/usr/bin/env python3

import argparse
import os, subprocess, sys, signal, threading, time, re, shutil
from shutil import which

# === COLORS ===
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def cprint(text, color=Colors.RESET):
    print(f"{color}{text}{Colors.RESET}")

def cprint_centered(text, color=Colors.RESET, fill=' '):
    columns = shutil.get_terminal_size((80, 20)).columns
    line = text.center(columns, fill)
    cprint(line, color)

# === SPINNER ===
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

signal.signal(signal.SIGINT, lambda s,f: print("\n⚠️ Use menu to quit. Press 'q'."))

# === UTILS ===
def get_project_name():
    return os.path.basename(os.getcwd())

def list_containers(project):
    result = subprocess.run(['docker', 'ps', '-a', '--filter', f'name={project}', '--format', '{{.Names}}'],
                            capture_output=True, text=True)
    return result.stdout.strip().splitlines()

def container_is_running(container):
    result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', container],
                            capture_output=True, text=True)
    return result.stdout.strip() == 'true'

def detect_methods():
    m = []
    if which('tmux'): m.append('tmux')
    m.append('inline')
    return m

# === DOCKER ACTIONS ===
def start_lab():
    if not os.path.exists('docker-compose.yml'):
        cprint("\n❌ docker-compose.yml not found!",Colors.RED)
        return
    project = get_project_name()
    running = [c for c in list_containers(project) if container_is_running(c)]
    if running:
        cprint_centered("✅ Lab is already running!", Colors.GREEN, fill='-')
        for c in running:
            print(f"   🔷 {c}")
        print("ℹ️ Use the menu to connect or stop the lab.")
        return
    run_with_spinner(['docker-compose', 'up', '-d'], "🚀 Starting lab…")
    cprint("✅ Lab started.", Colors.GREEN)

def stop_lab():
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        return
    running = [c for c in list_containers(get_project_name()) if container_is_running(c)]
    if not running:
        cprint_centered("🛑 Lab is already stopped", Colors.YELLOW, fill='-')
        print("👉 You can start the lab from the main menu if you want to bring it up.\n")
        return
    run_with_spinner(['docker-compose', 'down'], "🛑 Stopping lab…")
    cprint("✅ Lab stopped.", Colors.GREEN)

def restart_container(container):
    run_with_spinner(['docker', 'restart', container], f"🔄 Restarting {container}…")
    cprint(f"✅ {container} restarted.", Colors.GREEN)

def start_container(container):
    run_with_spinner(['docker', 'start', container], f"🚀 Starting {container}…")
    cprint(f"✅ {container} started.", Colors.GREEN)

def stop_container(container):
    run_with_spinner(['docker', 'stop', container], f"🛑 Stopping {container}…")
    cprint(f"✅ {container} stopped.", Colors.GREEN)

# === STATUS ===
def lab_status():
    project = get_project_name()
    containers = list_containers(project)
    if not containers:
        cprint("\nℹ️ No containers found.", Colors.BOLD)
        return
    cprint_centered(f"🧩 Lab Name: {project}", Colors.YELLOW, fill='-')
    print("📊 Lab Status:")
    for c in containers:
        status = "🟢 running" if container_is_running(c) else "🔴 stopped"
        print(f"  {c} — {status}")

# === CONTROL PANEL ===
def lab_control_panel():
    project = get_project_name()
    containers = list_containers(project)
    if not containers:
        cprint("\nℹ️ No containers to control.", Colors.BOLD)
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
            container_action(containers[int(choice)-1])
        else:
            cprint("\n⚠️ Invalid choice", Colors.YELLOW)

# === CONNECT ===
def connect_to_lab(method=None):
    project = get_project_name()
    methods = detect_methods()
    if method is None:
        method = choose_method(methods)
        if not method:
            return
    if method == 'tmux' and 'TMUX' not in os.environ:
        start_tmux_session(project)
        return
    if method == 'tmux':
        show_tmux_cheat_sheet()
    container_menu(method, project)

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

def start_tmux_session(project):
    result = subprocess.run(['tmux', 'ls'], capture_output=True, text=True)
    if project in result.stdout:
        subprocess.run(['tmux', 'attach-session', '-t', project])
    else:
        subprocess.Popen([
            'tmux', 'new-session', '-s', project,
            f'python3 {sys.argv[0]} --method tmux --action connect'
        ]).wait()

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
            return
        elif choice == 'a':
            for c in containers:
                connect(c, method, project)
        elif choice.isdigit() and 1 <= int(choice) <= len(containers):
            container_action(containers[int(choice)-1])
        else:
            cprint("\n⚠️ Invalid choice", Colors.YELLOW)

def container_action(container):
    while True:
        is_running = container_is_running(container)
        print(f"\n📋 Actions for {container}:")
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
        if choice == '1' and is_running:
            connect(container, 'inline', get_project_name())
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
            cprint("\n⚠️ Invalid choice", Colors.YELLOW)

def connect(container, method, project):
    if method == 'tmux':
        subprocess.Popen(['tmux', 'split-window', '-v', f"docker exec -it {container} Cli"])
        subprocess.Popen(['tmux', 'select-layout', 'tiled'])
    else:
        subprocess.run(['docker', 'exec', '-it', container, 'Cli'])

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
        f.write(re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', sheet))
    print("📄 Cheat sheet saved to tmux-cheatsheet.txt")

# === MAIN ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=['tmux', 'inline'])
    parser.add_argument('--action', choices=['connect'])
    args = parser.parse_args()

    if args.action == 'connect' and args.method == 'tmux':
        connect_to_lab(method='tmux')
    else:
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
                cprint("👋 Goodbye!", Colors.CYAN)
                sys.exit(0)
            else:
                cprint("\n⚠️ Invalid choice", Colors.YELLOW)

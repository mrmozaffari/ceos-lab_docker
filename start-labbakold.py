#!/usr/bin/env python3

import os, subprocess, sys, signal, threading, time, re
from shutil import which

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
    if os.environ.get("TERM_PROGRAM") == "iTerm.app": m.append('iterm')
    if which('gnome-terminal'): m.append('gnome-terminal')
    m.append('inline')
    return m

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

def handle_sigint(sig, frame):
    print("\n⚠️ Use menu to quit. Press 'q'.")

signal.signal(signal.SIGINT, handle_sigint)

# === DOCKER ACTIONS ===
def start_lab():
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        return
    project = get_project_name()
    running = [c for c in list_containers(project) if container_is_running(c)]
    if running:
        print("\n✅ Lab already running with:")
        for c in running:
            print(f"   🔷 {c}")
        print("ℹ️ Use the menu to connect to the lab or stop it.")
        return
    run_with_spinner(['docker-compose', 'up', '-d'], "🚀 Starting lab…")
    print("✅ Lab started.")

def stop_lab():
    if not os.path.exists('docker-compose.yml'):
        print("❌ docker-compose.yml not found!")
        return
    running = [c for c in list_containers(get_project_name()) if container_is_running(c)]
    if not running:
        print("ℹ️ Lab is already stopped.")
        return
    run_with_spinner(['docker-compose', 'down'], "🛑 Stopping lab…")
    print("✅ Lab stopped.")

def restart_container(container):
    run_with_spinner(['docker', 'restart', container], f"🔄 Restarting {container}…")
    print(f"✅ {container} restarted.")

def start_container(container):
    run_with_spinner(['docker', 'start', container], f"🚀 Starting {container}…")
    print(f"✅ {container} started.")

def stop_container(container):
    run_with_spinner(['docker', 'stop', container], f"🛑 Stopping {container}…")
    print(f"✅ {container} stopped.")

# === NETWORK TOOLS ===
def fix_lldp(bridges):
    for b in bridges:
        print(f"🔷 Enabling LLDP on br-{b}")
        subprocess.run(f"echo 16384 > /sys/class/net/br-{b}/bridge/group_fwd_mask", shell=True)

def set_mtu(bridges, mtu_size):
    for b in bridges:
        out = subprocess.check_output(f"brctl show br-{b}", shell=True).decode()
        for line in out.splitlines():
            matches = re.findall(r've\w+', line)
            for iface in matches:
                print(f"🔷 Setting MTU {mtu_size} on {iface}")
                subprocess.run(["ip", "link", "set", "dev", iface, "mtu", str(mtu_size)])

def list_lab_bridges(lab):
    output = subprocess.check_output(["docker", "network", "ls"]).decode()
    pattern = r'{}_(?!default\b)\S+'.format(lab)
    lab_items = re.findall(pattern, output)
    bridges = []
    for line in output.splitlines():
        for item in lab_items:
            if item in line:
                bridges.append(line.split()[0])
    return bridges

def lab_network_tools():
    lab = get_project_name()
    bridges = list_lab_bridges(lab)
    if not bridges:
        print("⚠️ No bridges found for this lab.")
        return
    while True:
        print("\n📡 Lab Network Tools")
        print("  1. Enable LLDP on bridges")
        print("  2. Set MTU on ve* interfaces")
        print("  q. Back")
        choice = input("👉 Your choice: ").strip().lower()
        if choice == '1':
            fix_lldp(bridges)
        elif choice == '2':
            mtu = input("👉 Enter MTU (e.g., 9214): ").strip()
            if mtu.isdigit():
                set_mtu(bridges, mtu)
            else:
                print("⚠️ Invalid MTU.")
        elif choice == 'q':
            return
        else:
            print("⚠️ Invalid choice.")

# === MAIN MENU ===
def main_menu():
    while True:
        print("\n📋 What would you like to do?")
        print("  1. 🚀 Start lab (docker-compose up -d)")
        print("  2. 🔗 Connect to containers")
        print("  3. 🛑 Stop lab (docker-compose down)")
        print("  4. 🔄 Lab control panel (restart/shutdown containers)")
        print("  5. 📊 Lab status")
        print("  6. ⚙️ Lab network tools (LLDP & MTU)")
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
        elif choice == '6':
            lab_network_tools()
        elif choice == 'q':
            print("👋 Goodbye!")
            sys.exit(0)
        else:
            print("⚠️ Invalid choice.")

# === STATUS ===
def lab_status():
    project = get_project_name()
    containers = list_containers(project)
    if not containers:
        print("ℹ️ No containers found.")
        return
    print("\n📊 Lab Status:")
    for c in containers:
        status = "🟢 running" if container_is_running(c) else "🔴 stopped"
        print(f"  {c} — {status}")

# === CONTROL PANEL ===
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
            container_action(containers[int(choice)-1])
        else:
            print("⚠️ Invalid choice.")

# === CONNECT ===
def connect_to_lab():
    project = get_project_name()
    methods = detect_methods()
    if 'TMUX' in os.environ:
        method = 'tmux'
    else:
        method = choose_method(methods)
        if not method:
            return
        if method == 'tmux':
            start_tmux_session(project)
            return
    if method == 'tmux':
        enable_tmux_mouse()
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
            f'python3 {sys.argv[0]} --method tmux'
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
            if method == 'tmux' and 'TMUX' in os.environ:
                subprocess.run(['tmux', 'kill-session', '-t', project])
            return
        elif choice == 'a':
            for c in containers:
                connect(c, method, project)
        elif choice.isdigit() and 1 <= int(choice) <= len(containers):
            container_action(containers[int(choice)-1])
        else:
            print("⚠️ Invalid choice.")

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
            print("⚠️ Invalid choice.")

def connect(container, method, project):
    if method == 'tmux':
        subprocess.Popen(['tmux', 'split-window', '-v', f"docker exec -it {container} Cli"])
        subprocess.Popen(['tmux', 'select-layout', 'tiled'])
    else:
        subprocess.run(['docker', 'exec', '-it', container, 'Cli'])

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

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

# === TMUX ===

def tmux_panes_running_for_container(container):
    """
    Return True if there is already a tmux pane running docker exec for this container.
    """
    result = subprocess.run(
        ['tmux', 'list-panes', '-a', '-F', '#{pane_current_command} #{pane_start_command}'],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if container in line and 'docker' in line:
            return True
    return False

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

def any_container_running(project):
    containers = list_containers(project)
    for c in containers:
        if container_is_running(c):
            return True
    return False

def detect_methods():
    m = []
    if which('tmux'): m.append('tmux')
    m.append('inline')
    return m

# === DOCKER ACTIONS ===
def start_lab():
    if not os.path.exists('docker-compose.yml'):
        cprint("\n❌ docker-compose.yml not found!", Colors.RED)
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


def start_lab_containers():
    project = get_project_name()
    all_containers = list_containers(project)
    if not all_containers:
        cprint_centered("⚠️ No containers exist. Please use 'Start lab (fresh)' instead.", Colors.YELLOW, fill='-')
        return
    stopped = [c for c in all_containers if not container_is_running(c)]
    if not stopped:
        cprint_centered("ℹ️ All containers already running!", Colors.GREEN, fill='-')
        return
    for c in stopped:
        run_with_spinner(['docker', 'start', c], f"🚀 Starting {c}…")
    cprint("✅ All stopped containers started.", Colors.GREEN)

def stop_lab_containers():
    project = get_project_name()
    running = [c for c in list_containers(project) if container_is_running(c)]
    if not running:
        cprint_centered("🛑 Lab is already stopped", Colors.YELLOW, fill='-')
        print("👉 You can start the lab from the main menu if you want to bring it up.\n")
        return
    for c in running:
        run_with_spinner(['docker', 'stop', c], f"🛑 Stopping {c}…")
    cprint("✅ All lab containers stopped (but not removed).", Colors.GREEN)


def delete_lab():
    project = get_project_name()

    if not os.path.exists('docker-compose.yml'):
        cprint("\n❌ docker-compose.yml not found!", Colors.RED)
        return

    containers = list_containers(project)
    if not containers:
        cprint_centered("ℹ️ No lab found to delete!", Colors.YELLOW, fill='-')
        return

    run_with_spinner(['docker-compose', 'down'], "🗑️ Deleting lab…")
    cprint("✅ Lab deleted (containers & networks removed).", Colors.GREEN)

def restart_container(container):
    run_with_spinner(['docker', 'restart', container], f"🔄 Restarting {container}…")
    cprint(f"✅ {container} restarted.", Colors.GREEN)

def start_container(container):
    project = get_project_name()
    containers = list_containers(project)
    #print(f"Project name {project}")
    #print(f"Project Name {containers}")
    if not containers:
        cprint("\nℹ️ No containers found.", Colors.BOLD)
        return
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
        cprint_centered("ℹ️ No containers to control", Colors.YELLOW, fill='-')
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

    if not any_container_running(project):
        cprint_centered("⚠️ No running containers found! Start the lab first.", Colors.YELLOW, fill='-')
        return
    
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
        print("  q. Back & close tmux (if any)")
        choice = input("👉 Enter number, 'a' or 'q': ").strip().lower()
        if choice == 'q':
            if method == 'tmux' and 'TMUX' in os.environ:
                cprint("\n🛑 Closing tmux session…", Colors.YELLOW)
                subprocess.run(['tmux', 'kill-session', '-t', project])
            return
        elif choice == 'a':
            for c in containers:
                if method == 'tmux' and tmux_panes_running_for_container(c):
                    cprint(f"🔷 Already connected to {c} — skipping.", Colors.YELLOW)
                    continue
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

def container_shell(container):
    """cEOS containers use the EOS CLI, plain Linux nodes (label lab.kind=linux) get a shell."""
    out = subprocess.run(['docker', 'inspect', '-f', '{{index .Config.Labels "lab.kind"}}', container],
                         capture_output=True, text=True).stdout.strip()
    return 'sh' if out == 'linux' else 'Cli'

def connect(container, method, project):
    shell = container_shell(container)
    if method == 'tmux':
        subprocess.Popen(['tmux', 'split-window', '-v', f"docker exec -it {container} {shell}"])
        subprocess.Popen(['tmux', 'select-layout', 'tiled'])
    else:
        subprocess.run(['docker', 'exec', '-it', container, shell])

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


# === NETWORK TOOLS ===
def lab_network_tools():
    lab = get_project_name()
    bridges = list_lab_bridges(lab)
    if not bridges:
        cprint_centered("⚠️ No bridges found for this lab ⚠️", Colors.YELLOW, fill='-')
        return
    while True:
        print("\n📡 Lab Network Tools")
        print("  1. Enable LLDP on bridges")
        print("  2. Set MTU on ve* interfaces")
        print("  3. Report MTU on ve* interfaces")
        print("  q. Back")
        choice = input("👉 Your choice: ").strip().lower()
        if choice == '1':
            fix_lldp(bridges)
        elif choice == '2':
            mtu = input("👉 Enter MTU (e.g., 9214): ").strip()
            if mtu.isdigit():
                set_mtu(bridges, mtu)
            else:
                cprint("\n⚠️ Invalid MTU", Colors.YELLOW)
        elif choice == '3':
            report_mtu(bridges)
        elif choice == 'q':
            return
        else:
            cprint("\n⚠️ Invalid choice.", Colors.YELLOW)

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

def report_mtu(bridges):
    """
    Report the current MTU for all ve* interfaces on the lab's bridges.
    """
    cprint_centered("📋 Current MTU Settings", Colors.CYAN, fill='=')
    for b in bridges:
        cprint(f"\n🔷 Bridge: br-{b}", Colors.BOLD)
        try:
            output = subprocess.check_output(f"brctl show br-{b}", shell=True).decode()
            for line in output.splitlines():
                matches = re.findall(r'(ve\w+)', line)
                for iface in matches:
                    mtu = get_interface_mtu(iface)
                    print(f"   {iface}: {mtu}")
        except subprocess.CalledProcessError as e:
            cprint(f"⚠️ Failed to inspect bridge br-{b}: {e}", Colors.RED)

def get_interface_mtu(interface):
    """
    Get the MTU of a given interface.
    """
    try:
        output = subprocess.check_output(
            ["ip", "-o", "link", "show", interface],
            text=True
        )
        m = re.search(r"mtu (\d+)", output)
        if m:
            return m.group(1)
        return "unknown"
    except subprocess.CalledProcessError:
        return "unknown"

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
            print("  1. 🚀 Fresh Start lab (docker-compose up -d ) Fresh Start")
            print("  2. 🚀 Start lab (existing containers only)")
            print("  3. 🔗 Connect to containers")
            print("  4. ⏸️ Stop lab (containers only)")
            print("  5. 🗑️ Delete lab (docker-compose down) Will Clean Everything")
            print("  6. 🔄 Lab control panel (restart/shutdown containers)")
            print("  7. 📊 Lab status")
            print("  8. ⚙️ Lab network tools (LLDP & MTU)")
            print("  q. ❌ Quit")
            choice = input("👉 Your choice: ").strip().lower()
            if choice == '1':
                start_lab()
            elif choice == '2':
                start_lab_containers()
            elif choice == '3':
                connect_to_lab()
            elif choice == '4':
                stop_lab_containers()
            elif choice == '5':
                delete_lab()
            elif choice == '6':
                lab_control_panel()
            elif choice == '7':
                lab_status()
            elif choice == '8':
                lab_network_tools()
            elif choice == 'q':
                cprint("👋 Goodbye!", Colors.CYAN)
                sys.exit(0)
            else:
                cprint("\n⚠️ Invalid choice", Colors.YELLOW)

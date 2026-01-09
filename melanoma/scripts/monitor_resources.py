#!/usr/bin/env python3
"""
Resource monitoring script for Bionocular servers.
Monitors CPU and RAM usage for backend and frontend processes.
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Optional

import psutil


# Color codes for terminal output
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"  # No Color


def get_processes_by_port(port: int) -> list[psutil.Process]:
    """Get all processes listening on a specific port."""
    processes = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr.port == port and conn.status == "LISTEN":
                try:
                    proc = psutil.Process(conn.pid)
                    processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except (psutil.AccessDenied, AttributeError):
        # Fallback: use lsof command
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"], capture_output=True, text=True, check=False
            )
            if result.stdout:
                for pid_str in result.stdout.strip().split("\n"):
                    try:
                        proc = psutil.Process(int(pid_str))
                        processes.append(proc)
                    except (ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except FileNotFoundError:
            pass
    return processes


def get_process_info(port: int, name: str) -> Optional[dict]:
    """Get detailed information about processes on a port."""
    processes = get_processes_by_port(port)

    if not processes:
        return None

    # Get the main process (first one)
    main_proc = processes[0]

    try:
        # Get CPU and memory info
        cpu_percent = main_proc.cpu_percent(interval=0.1)
        memory_info = main_proc.memory_info()
        memory_percent = main_proc.memory_percent()

        # Get process tree to sum up child processes
        children = main_proc.children(recursive=True)
        total_rss = memory_info.rss
        total_cpu = cpu_percent

        for child in children:
            try:
                child_mem = child.memory_info()
                total_rss += child_mem.rss
                total_cpu += child.cpu_percent(interval=0.1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Convert bytes to MB
        rss_mb = total_rss / (1024 * 1024)

        # Get command line
        try:
            cmdline = " ".join(main_proc.cmdline()[:3])  # First 3 args
            if len(main_proc.cmdline()) > 3:
                cmdline += "..."
        except (psutil.AccessDenied, AttributeError):
            cmdline = main_proc.name()

        return {
            "pid": main_proc.pid,
            "name": name,
            "port": port,
            "cpu_percent": total_cpu,
            "memory_mb": rss_mb,
            "memory_percent": memory_percent,
            "num_children": len(children),
            "cmdline": cmdline,
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def get_system_stats() -> dict:
    """Get system-wide resource statistics."""
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)

        return {
            "total_memory_gb": memory.total / (1024**3),
            "available_memory_gb": memory.available / (1024**3),
            "memory_percent": memory.percent,
            "cpu_percent": cpu_percent,
            "load_avg_1min": load_avg[0] if len(load_avg) > 0 else 0,
        }
    except Exception:
        return {}


def format_color(value: float, thresholds: tuple, unit: str = "") -> str:
    """Format a value with color based on thresholds (low, medium, high)."""
    low, medium = thresholds
    if value >= medium:
        color = Colors.RED
    elif value >= low:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN
    return f"{color}{value:.2f}{unit}{Colors.NC}"


def print_header():
    """Print the monitoring header."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}  Bionocular Server Resource Monitor{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


def print_process_info(info: Optional[dict]):
    """Print information about a server process."""
    if info is None:
        print(f"{Colors.RED}✗{Colors.NC} Process not running")
        return

    status = f"{Colors.GREEN}✓{Colors.NC}"
    print(f"{status} {info['name']} (PID: {info['pid']}, Port: {info['port']})")

    cpu_str = format_color(info["cpu_percent"], (20, 50), "%")
    mem_str = format_color(info["memory_mb"], (200, 400), " MB")
    mem_percent_str = format_color(info["memory_percent"], (10, 20), "%")

    print(f"  CPU: {cpu_str} | RAM: {mem_str} ({mem_percent_str})")

    if info["num_children"] > 0:
        print(f"  Children: {info['num_children']} processes")

    if len(info["cmdline"]) > 60:
        cmdline = info["cmdline"][:57] + "..."
    else:
        cmdline = info["cmdline"]
    print(f"  Command: {cmdline}")


def print_system_stats(stats: dict):
    """Print system-wide statistics."""
    if not stats:
        return

    print(f"\n{Colors.CYAN}{'='*70}{Colors.NC}")
    print(f"{Colors.CYAN}  System Resources{Colors.NC}")
    print(f"{Colors.CYAN}{'='*70}{Colors.NC}")

    total_mem = stats.get("total_memory_gb", 0)
    avail_mem = stats.get("available_memory_gb", 0)
    mem_percent = stats.get("memory_percent", 0)
    cpu_percent = stats.get("cpu_percent", 0)
    load_avg = stats.get("load_avg_1min", 0)

    mem_color = Colors.GREEN
    if mem_percent > 80:
        mem_color = Colors.RED
    elif mem_percent > 60:
        mem_color = Colors.YELLOW

    print(f"Total RAM: {total_mem:.2f} GB")
    print(f"Available RAM: {avail_mem:.2f} GB")
    print(f"Memory Used: {mem_color}{mem_percent:.1f}%{Colors.NC}")
    print(f"CPU Usage: {format_color(cpu_percent, (50, 80), '%')}")
    print(f"Load Average (1min): {load_avg:.2f}")


def main():
    """Main monitoring loop."""
    print(f"{Colors.CYAN}Starting resource monitor...{Colors.NC}")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            # Clear screen (works on most terminals)
            os.system("clear" if os.name != "nt" else "cls")

            print_header()

            # Monitor backend (port 8000)
            print(f"{Colors.BLUE}Backend Server{Colors.NC}")
            backend_info = get_process_info(8000, "Backend (FastAPI)")
            print_process_info(backend_info)

            # Monitor frontend (port 3000)
            print(f"\n{Colors.BLUE}Frontend Server{Colors.NC}")
            frontend_info = get_process_info(3000, "Frontend (Next.js)")
            print_process_info(frontend_info)

            # System stats
            system_stats = get_system_stats()
            print_system_stats(system_stats)

            # Memory warnings
            if backend_info and backend_info["memory_mb"] > 400:
                print(
                    f"\n{Colors.YELLOW}⚠ Warning: Backend memory usage is high (>400MB){Colors.NC}"
                )
            if frontend_info and frontend_info["memory_mb"] > 400:
                print(
                    f"{Colors.YELLOW}⚠ Warning: Frontend memory usage is high (>400MB){Colors.NC}"
                )

            print(
                f"\n{Colors.YELLOW}Monitoring every 2 seconds... (Ctrl+C to stop){Colors.NC}"
            )

            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n\n{Colors.CYAN}Monitoring stopped.{Colors.NC}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.NC}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

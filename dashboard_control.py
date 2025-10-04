#!/usr/bin/env python
"""
Dashboard control script - start, stop, restart, and check status.

Usage:
    python dashboard_control.py start    # Start the dashboard
    python dashboard_control.py stop     # Stop the dashboard
    python dashboard_control.py restart  # Restart the dashboard
    python dashboard_control.py status   # Check if running
"""
import sys
import os
import subprocess
import signal
import time
import psutil


def find_dashboard_process():
    """Find the dashboard process if running."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and any('dashboard.app' in arg for arg in cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def find_process_on_port(port=8000):
    """Find process listening on specified port using lsof."""
    try:
        # Use lsof to find process on port (works better on macOS)
        result = subprocess.run(
            ['lsof', '-i', f':{port}', '-t'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            pid = int(result.stdout.strip().split('\n')[0])
            return psutil.Process(pid)
    except (subprocess.SubprocessError, ValueError, psutil.NoSuchProcess):
        pass
    return None


def start_dashboard():
    """Start the dashboard."""
    # Check for .env file first
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found!")
        print("Please create a .env file with your API keys:")
        print("  cp .env.example .env")
        print("  # Then edit .env to add your keys")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Aborted. Please set up your .env file first.")
            return

    proc = find_dashboard_process()
    if proc:
        print(f"Dashboard already running (PID: {proc.pid})")
        return

    # Check if port is in use
    port_proc = find_process_on_port(8000)
    if port_proc:
        print(f"Port 8000 is in use by PID {port_proc.pid}")
        response = input("Kill it and start dashboard? (y/n): ")
        if response.lower() == 'y':
            stop_dashboard()
            time.sleep(1)
        else:
            print("Aborted. Use 'python dashboard_control.py stop' first.")
            return

    print("Starting dashboard...")
    # Start in background using nohup
    subprocess.Popen(
        [sys.executable, "-m", "dashboard.app"],
        stdout=open('dashboard.log', 'a'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )

    # Wait a moment and check if it started
    time.sleep(2)
    proc = find_dashboard_process()
    if proc:
        print(f"Dashboard started successfully (PID: {proc.pid})")
        print("Access at: http://localhost:8000")
        print("Logs at: dashboard.log")
    else:
        print("Failed to start dashboard. Check dashboard.log for errors.")


def stop_dashboard():
    """Stop the dashboard."""
    # First try to find dashboard process
    proc = find_dashboard_process()

    # If not found, check port 8000
    if not proc:
        proc = find_process_on_port(8000)

    if proc:
        print(f"Stopping dashboard (PID: {proc.pid})...")
        try:
            proc.terminate()
            time.sleep(1)
            if proc.is_running():
                proc.kill()
            print("Dashboard stopped.")
        except psutil.NoSuchProcess:
            print("Process already terminated.")
        except Exception as e:
            print(f"Error stopping dashboard: {e}")
    else:
        print("Dashboard is not running.")


def restart_dashboard():
    """Restart the dashboard."""
    print("Restarting dashboard...")
    stop_dashboard()
    time.sleep(1)
    start_dashboard()


def check_status():
    """Check dashboard status."""
    proc = find_dashboard_process()
    port_proc = find_process_on_port(8000)

    if proc:
        print(f"✓ Dashboard is running (PID: {proc.pid})")
        print(f"  Memory: {proc.memory_info().rss / 1024 / 1024:.1f} MB")
        print(f"  CPU: {proc.cpu_percent(interval=0.1):.1f}%")
    else:
        print("✗ Dashboard process not found")

    if port_proc:
        if proc and proc.pid == port_proc.pid:
            print(f"✓ Port 8000 is correctly bound to dashboard")
        else:
            print(f"⚠ Port 8000 is in use by different process (PID: {port_proc.pid})")
    else:
        print("✗ Port 8000 is not in use")

    if os.path.exists('dashboard.log'):
        size = os.path.getsize('dashboard.log') / 1024
        print(f"  Log file: dashboard.log ({size:.1f} KB)")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'start':
        start_dashboard()
    elif command == 'stop':
        stop_dashboard()
    elif command == 'restart':
        restart_dashboard()
    elif command == 'status':
        check_status()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    # Check for required module
    try:
        import psutil
    except ImportError:
        print("Please install psutil: pip install psutil")
        sys.exit(1)

    main()
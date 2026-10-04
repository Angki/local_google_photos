# ==============================================================================
# File: run.py
# Description: One-click application launcher for Google Photos Local Takeout Gallery.
#              Validates environment, checks CUDA/GPU acceleration, initializes
#              database, and launches Uvicorn web server with auto-browser launch.
# ==============================================================================

import argparse
import os
import sys
import time
import webbrowser
from pathlib import Path

# Add project root to sys.path
APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_ROOT))


def parse_arguments():
    """Parses optional CLI arguments for paths and server configuration."""
    parser = argparse.ArgumentParser(
        description="Google Photos Local Takeout Gallery - High-performance local photo archive"
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default=None,
        help="Path to extracted Google Photos Takeout directory (overrides .env / TAKEOUT_DIR)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind server (default: 127.0.0.1 or HOST env)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=None,
        help="Port number to bind server (default: 8000 or PORT env)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Disable automatic browser opening on launch",
    )
    return parser.parse_args()


def check_environment(source_dir: Path, host: str, port: int):
    """Validates local environment, directories, and GPU capabilities."""
    print("=" * 72)
    print("      GOOGLE PHOTOS LOCAL TAKEOUT ARCHIVE (2013 - 2026)")
    print("=" * 72)
    print(f"  [+] Project Root : {APP_ROOT}")
    print(f"  [+] Source Data  : {source_dir}")

    if not source_dir.is_dir():
        print(f"  [!] NOTICE: Source directory does not exist: {source_dir}")
        print("      To specify your Google Photos Takeout folder, either:")
        print("      1. Create a '.env' file with TAKEOUT_DIR=path/to/Google Photos")
        print("      2. Run: python run.py --source \"path/to/Google Photos\"")
    else:
        print("  [+] Source directory verified.")

    # Check GPU / PyTorch status
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "None (CPU Mode)"
        print(f"  [+] Hardware Accel: CUDA={'Enabled' if cuda_ok else 'Disabled'} ({gpu_name})")
    except ImportError:
        print("  [!] PyTorch not found. AI Vision Engine will use heuristic fallback.")

    try:
        from backend.network_helper import get_local_ip, get_tailscale_ip
        local_ip = get_local_ip()
        ts_ip = get_tailscale_ip()
    except Exception:
        local_ip = host
        ts_ip = None

    print(f"  [+] Local Browser   : http://localhost:{port}")
    if local_ip not in ("127.0.0.1", "localhost"):
        print(f"  [+] Home Wi-Fi LAN  : http://{local_ip}:{port} (Buka di browser HP Anda 📱)")
    if ts_ip:
        print(f"  [+] Tailscale (VPN) : http://{ts_ip}:{port} (Akses dari mana saja di HP Anda 🚀)")
    print("=" * 72)


def open_browser(port: int):
    """Opens default web browser once server is initialized."""
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    args = parse_arguments()

    # If --source is provided, override environment variable before importing config
    if args.source:
        os.environ["TAKEOUT_DIR"] = str(Path(args.source).resolve())

    # Import config after env overrides
    from backend.config import HOST, PORT, SOURCE_DATA_DIR

    active_host = args.host if args.host else HOST
    requested_port = args.port if args.port else PORT

    # Check port availability to avoid [WinError 10048]
    import socket
    active_port = requested_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((active_host, requested_port))
        except OSError:
            if args.port:
                print(f"  [!] ERROR: Port {requested_port} is already in use by another process.")
                sys.exit(1)
            # Find next free port
            test_port = requested_port + 1
            while test_port < requested_port + 50:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s2:
                    try:
                        s2.bind((active_host, test_port))
                        active_port = test_port
                        print(f"  [!] NOTICE: Port {requested_port} is busy. Automatically switching to http://{active_host}:{active_port}")
                        break
                    except OSError:
                        test_port += 1

    check_environment(SOURCE_DATA_DIR, active_host, active_port)

    # Launch browser in a background thread if not disabled
    if not args.no_browser:
        import threading
        threading.Thread(target=open_browser, args=(active_port,), daemon=True).start()

    import uvicorn
    uvicorn.run("backend.main:app", host=active_host, port=active_port, reload=False, log_level="info")


if __name__ == "__main__":
    main()

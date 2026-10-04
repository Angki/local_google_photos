# ==============================================================================
# File: backend/network_helper.py
# Description: Local network discovery and QR code generator for instant mobile
#              access over home Wi-Fi (LAN Mode) without internet or third-party cloud.
# ==============================================================================

import io
import logging
import socket
from typing import Any, Dict
import qrcode
import qrcode.image.svg

logger = logging.getLogger("NetworkHelper")


def get_local_ip() -> str:
    """
    Detects the primary active local IPv4 address connected to the home Wi-Fi/LAN.
    Uses UDP route query without making actual outbound internet network traffic.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        # Fallback to hostname resolution
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def generate_qr_code_svg(url: str) -> str:
    """
    Generates a lightweight, scalable SVG string of the QR code pointing to the given URL.
    Can be directly embedded into HTML without any image conversion overhead.
    """
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=factory,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()

    stream = io.BytesIO()
    img.save(stream)
    return stream.getvalue().decode("utf-8")


def get_network_info(port: int = 8000) -> Dict[str, Any]:
    """
    Returns complete local network information, URL, and pre-rendered SVG QR code.
    """
    local_ip = get_local_ip()
    lan_url = f"http://{local_ip}:{port}"
    localhost_url = f"http://localhost:{port}"

    qr_svg = ""
    try:
        qr_svg = generate_qr_code_svg(lan_url)
    except Exception as e:
        logger.warning(f"Failed to generate QR code SVG: {e}")

    return {
        "local_ip": local_ip,
        "port": port,
        "lan_url": lan_url,
        "localhost_url": localhost_url,
        "qr_svg": qr_svg,
        "qr_code_svg": qr_svg,
    }

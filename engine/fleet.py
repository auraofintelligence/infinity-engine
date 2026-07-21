"""Your estate: the devices and accounts the engine can call on.

Reads catalog/fleet.yaml and reports, for each device, whether it is live
right now. This is the "map of everything you own or have an account with"
so the studio can show it and route work to it. Wayfinding for hardware.
"""
from __future__ import annotations

import socket
from pathlib import Path

import yaml


def load_fleet(root: Path) -> dict:
    path = root / "catalog" / "fleet.yaml"
    if not path.exists():
        return {"devices": [], "accounts": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("devices", [])
    data.setdefault("accounts", [])
    return data


def entry_status(entry: dict, connected_server: str | None = None) -> str:
    """online / offline / ready / connected / declared.

    - local        : always online (the brain)
    - comfy + addr : online if ComfyUI answers; 'connected' if it is the box
                     currently in use
    - browser      : ready (a screen you open)
    - account/etc. : declared (sign in when you need it)
    """
    reach = entry.get("reach")
    if reach == "local":
        return "online"
    if reach == "comfy":
        addr = entry.get("address")
        if not addr:
            return "declared"
        if connected_server and addr.rstrip("/") == connected_server.rstrip("/"):
            return "connected"
        from .comfy import ComfyClient
        return "online" if ComfyClient(addr).alive() else "offline"
    if reach == "browser":
        return "ready"
    return "declared"


def fleet_view(root: Path, connected_server: str | None = None) -> dict:
    """The whole estate with a live status stamped on each entry."""
    data = load_fleet(root)
    out = {"devices": [], "accounts": []}
    for group in ("devices", "accounts"):
        for e in data.get(group, []):
            item = dict(e)
            item["status"] = entry_status(e, connected_server)
            out[group].append(item)
    return out


def lan_ip() -> str | None:
    """This machine's LAN address, for the phone-access URL. Best-effort."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))  # no packets sent; picks the iface
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None

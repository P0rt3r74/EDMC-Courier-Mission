import json
import socket
import threading

OVERLAY_HOST = '127.0.0.1'
OVERLAY_PORT = 5010
OVERLAY_ID = "courier_missions"

# (ZielSystem, ZielStation) → Anzahl
mission_counts = {}
# MissionID → key (ZielSystem, ZielStation)
mission_id_map = {}

lock = threading.Lock()

def send_overlay_block(text, x=10, y=300, size="normal", color="#FFFFFF", ttl=5):
    msg = {
        "id": OVERLAY_ID,
        "text": text,
        "size": size,
        "color": color,
        "x": x,
        "y": y,
        "ttl": ttl
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((OVERLAY_HOST, OVERLAY_PORT))
            s.sendall((json.dumps(msg) + "\n").encode('utf-8'))
    except Exception as e:
        print(f"[CourierOverlay] Fehler beim Senden: {e}")

def build_overlay_text():
    lines = []
    lines.append(f"{'System':<25} {'Station':<25} {'#':>3}")
    lines.append("-" * 60)
    with lock:
        for (sysname, station), cnt in mission_counts.items():
            lines.append(f"{sysname:<25} {station:<25} {cnt:>3}")
    return "\n".join(lines)

def update_overlay():
    text = build_overlay_text()
    send_overlay_block(text, x=10, y=300, size="normal", color="#FFFFFF", ttl=5)

def plugin_start3(plugin_dir):
    return

def prefs_changed(cmdr, is_beta):
    return

def journal_entry(cmdr, is_beta, journal):
    ev = journal.get('event')
    if not ev:
        return

    # MissionAccepted
    if ev == 'MissionAccepted':
        mission_id = journal.get('MissionID')
        sys = journal.get('DestinationSystem')
        sta = journal.get('DestinationStation')
        if sys and sta:
            key = (sys, sta)
            with lock:
                mission_id_map[mission_id] = key
                mission_counts[key] = mission_counts.get(key, 0) + 1

    # MissionRedirected (Ziel geändert)
    elif ev == 'MissionRedirected':
        mission_id = journal.get('MissionID')
        new_sys = journal.get('NewDestinationSystem')
        new_sta = journal.get('NewDestinationStation')
        if mission_id in mission_id_map and new_sys and new_sta:
            with lock:
                old_key = mission_id_map[mission_id]
                # dekrementiere alten Zielzähler
                mission_counts[old_key] = mission_counts.get(old_key, 1) - 1
                if mission_counts[old_key] <= 0:
                    del mission_counts[old_key]
                # setze neuen Ziel
                new_key = (new_sys, new_sta)
                mission_id_map[mission_id] = new_key
                mission_counts[new_key] = mission_counts.get(new_key, 0) + 1

    # MissionCompleted oder MissionAbandoned oder MissionFailed
    elif ev in ('MissionCompleted', 'MissionAbandoned', 'MissionFailed'):
        mission_id = journal.get('MissionID')
        if mission_id in mission_id_map:
            with lock:
                key = mission_id_map.pop(mission_id)
                # dekrementiere
                mission_counts[key] = mission_counts.get(key, 1) - 1
                if mission_counts[key] <= 0:
                    del mission_counts[key]

    # Nach Änderungen Overlay updaten
    update_overlay()

def plugin_stop():
    # löschen
    try:
        send_overlay_block("", x=0, y=0, size="normal", color="#000000", ttl=0)
    except:
        pass
    return

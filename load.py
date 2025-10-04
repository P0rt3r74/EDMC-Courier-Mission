import os
import json
import threading
import tkinter as tk
import logging
from theme import theme
from config import appname

# === Logger Setup ===
plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(plugin_name)
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    fh = logging.FileHandler(os.path.join(os.path.dirname(__file__), 'courier.log'), encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.addHandler(fh)

# === Globale Daten ===
mission_counts = {}
mission_id_map = {}
lock = threading.Lock()

ui_frame = None
rows_widgets = []

logger.info("Courier Plugin gestartet")
# === Plugin-UI ===
def plugin_app(parent: tk.Frame):
    global ui_frame
    ui_frame = tk.Frame(parent)

    header = tk.Label(ui_frame, text="Courier-Missions", font=("TkDefaultFont", 10, "bold"))
    header.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(2,2))

    tk.Label(ui_frame, text="System").grid(row=1, column=0, sticky=tk.W, padx=2)
    tk.Label(ui_frame, text="Station").grid(row=1, column=1, sticky=tk.W, padx=2)
    tk.Label(ui_frame, text="Count.").grid(row=1, column=2, sticky=tk.E, padx=2)

    theme.update(ui_frame)
    ui_frame.after(0, update_ui_table)
    return ui_frame

def update_ui_table():
    global rows_widgets
    if ui_frame is None:
        return

    for (w0, w1, w2) in rows_widgets:
        w0.destroy()
        w1.destroy()
        w2.destroy()
    rows_widgets.clear()

    with lock:
        items = list(mission_counts.items())

    start_row = 2
    for i, ((sysname, station), count) in enumerate(items):
        w0 = tk.Label(ui_frame, text=sysname)
        w1 = tk.Label(ui_frame, text=station)
        w2 = tk.Label(ui_frame, text=str(count))
        w0.grid(row=start_row + i, column=0, sticky=tk.W, padx=2)
        w1.grid(row=start_row + i, column=1, sticky=tk.W, padx=2)
        w2.grid(row=start_row + i, column=2, sticky=tk.E, padx=2)
        rows_widgets.append((w0, w1, w2))

    theme.update(ui_frame)

# === Plugin-Klasse ===
def journal_entry(cmdr, is_beta, system, station, entry, state):
    ev = entry.get("event")
    if ev == "LoadGame":
        do_catchup()
    if ev == "MissionAccepted":
        mid = entry.get("MissionID")
        sysn = entry.get("DestinationSystem")
        sta = entry.get("DestinationStation")
        if mid and sysn and sta:
            with lock:
                mission_id_map[mid] = (sysn, sta)
                mission_counts[(sysn, sta)] = mission_counts.get((sysn, sta), 0) + 1

    elif ev == "MissionRedirected":
        mid = entry.get("MissionID")
        newsys = entry.get("NewDestinationSystem")
        newsta = entry.get("NewDestinationStation")
        if mid in mission_id_map and newsys and newsta:
            with lock:
                old = mission_id_map[mid]
                mission_counts[old] = mission_counts.get(old, 1) - 1
                if mission_counts[old] <= 0:
                    del mission_counts[old]
                newkey = (newsys, newsta)
                mission_id_map[mid] = newkey
                mission_counts[newkey] = mission_counts.get(newkey, 0) + 1

    elif ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed"):
        mid = entry.get("MissionID")
        if mid in mission_id_map:
            with lock:
                key = mission_id_map.pop(mid)
                mission_counts[key] = mission_counts.get(key, 1) - 1
                if mission_counts[key] <= 0:
                    del mission_counts[key]

    try:
        ui_frame.after(0, update_ui_table)
    except Exception as e:
        logger.error(f"Fehler beim UI-Update: {e}")

# === Catchup beim Start ===
def do_catchup():
    logger.info("do_catchup() gestartet")
    home = os.path.expanduser("~")
    journal_dir = os.path.join(home, "Saved Games", "Frontier Developments", "Elite Dangerous")
    logger.info(f"do_catchup: Journal-Verzeichnis = {journal_dir}")
    if not os.path.isdir(journal_dir):
        logger.warning(f"Journal-Verzeichnis nicht gefunden: {journal_dir}")
        return

    try:
        files = sorted(f for f in os.listdir(journal_dir) if f.startswith("Journal") and f.endswith(".log"))
        logger.info(f"Journal-Dateien: {files}")
    except Exception as e:
        logger.error(f"Fehler beim Auflisten des Journal-Ordners: {e}")
        return

    

    # 1. Zuerst alle aktiven MissionIDs aus "Missions"-Event sammeln
    active_mission_ids = set()
    for fname in reversed(files):  # reverse = neueste zuerst, um aktuelle Missionen zu finden
        full = os.path.join(journal_dir, fname)
        try:
            with open(full, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("event") == "Missions":
                        active = obj.get("Active", [])
                        for mission in active:
                            mid = mission.get("MissionID")
                            if mid is not None:
                                active_mission_ids.add(mid)
                        # Annahme: Nur ein Missions-Event pro Datei oder wir sammeln alle
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Journal-Datei {full}: {e}")

    logger.info(f"Gefundene aktive MissionIDs: {active_mission_ids}")

    # 2. Suche nun nach System & Station zu den aktiven MissionIDs
    for fname in files:
        full = os.path.join(journal_dir, fname)
        try:
            with open(full, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ev = obj.get("event")

                    if ev == "MissionAccepted":
                        mid = obj.get("MissionID")
                        if mid in active_mission_ids:
                            sysn = obj.get("DestinationSystem")
                            sta = obj.get("DestinationStation")
                            if sysn and sta:
                                with lock:
                                    if mid not in mission_id_map:
                                        mission_id_map[mid] = (sysn, sta)
                                        mission_counts[(sysn, sta)] = mission_counts.get((sysn, sta), 0) + 1
                                        logger.info(f"do_catchup: MissionAccepted: {mid} → {(sysn, sta)}")

                    elif ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed"):
                        mid = obj.get("MissionID")
                        if mid in active_mission_ids:
                            with lock:
                                if mid in mission_id_map:
                                    key = mission_id_map.pop(mid)
                                    mission_counts[key] = mission_counts.get(key, 1) - 1
                                    if mission_counts[key] <= 0:
                                        mission_counts.pop(key, None)
                                    logger.info(f"do_catchup: Mission beendet: {mid} → {key}")

        except Exception as e:
            logger.error(f"Fehler beim Lesen der Journal-Datei {full}: {e}")

# === Plugin Einstiegspunkte ===
def plugin_start3(plugin_dir):
    do_catchup()
    return "Courier"

def plugin_load():
    return plugin_instance

def plugin_stop():
    pass

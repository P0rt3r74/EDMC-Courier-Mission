import os
import json
import threading
import tkinter as tk
import myNotebook as nb
import logging
import fnmatch
from theme import theme
from config import appname
from config import config
from typing import Optional
import settings

def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> Optional[tk.Frame]:
    logger.info("plugin_prefs() aufgerufen")
    try:
        return settings.plugin_prefs(parent, cmdr, is_beta)
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des Settings-Frames: {e}")
        return None
        
def prefs_changed(cmdr, is_beta):
    try:
        settings.prefs_changed(cmdr, is_beta)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Settings: {e}")


# === helper setup ===
def is_courier(mis_name):
    if fnmatch.fnmatch(mis_name, "Mission_Courier*"):
        return True
    else:
        return False
        
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

# === Global data ===
mission_counts = {}
mission_id_map = {}
lock = threading.Lock()
ui_frame: Optional[tk.Frame] = None
rows_widgets = []

logger.info("Courier Plugin starting")

# === Plugin-UI ===
def plugin_app(parent: tk.Frame):
    global ui_frame
    ui_frame = tk.Frame(parent)

    # Main Header in UI
    header = tk.Label(ui_frame, text="Courier-Missions", font=("TkDefaultFont", 9, "bold"))
    header.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(2,1))

    theme.update(ui_frame)
    ui_frame.after(0, update_ui_table)
    return ui_frame

def update_ui_table():
    global rows_widgets
    if ui_frame is None:
        logger.error("uiframe is none returning")
        return
        
    # Remove old Widgets
    for w in rows_widgets:
        w.destroy()
    rows_widgets.clear()

    with lock:
        items = list(mission_counts.items())

    start_row = 2
    if items:
        # Show headers
        lbl_sys = tk.Label(ui_frame, text="System")
        lbl_sta = tk.Label(ui_frame, text="Station")
        lbl_sys.grid(row=1, column=0, sticky=tk.W, padx=2)
        lbl_sta.grid(row=1, column=1, sticky=tk.W, padx=2)
        rows_widgets.extend([lbl_sys, lbl_sta])
        if config.get_bool("EDMC-Courier-Mission.display_mission_count"):
            lbl_cnt = tk.Label(ui_frame, text="Count")
            lbl_cnt.grid(row=1, column=2, sticky=tk.E, padx=2)
            rows_widgets.extend([lbl_cnt])
        

        # Show mission data
        for i, (sys_sta, cnt) in enumerate(items):
            sysname, station = sys_sta
            w0 = tk.Label(ui_frame, text=sysname)
            w1 = tk.Label(ui_frame, text=station)
            w0.grid(row=start_row + i, column=0, sticky=tk.W, padx=2)
            w1.grid(row=start_row + i, column=1, sticky=tk.W, padx=2)
            rows_widgets.extend([w0, w1])
            if config.get_bool("EDMC-Courier-Mission.display_mission_count"):
                w2 = tk.Label(ui_frame, text=str(cnt))
                w2.grid(row=start_row + i, column=2, sticky=tk.E, padx=2)
                rows_widgets.extend([w2])
    else:
        # No missions - show hint
        hint = tk.Label(ui_frame, text="No active missions", fg="gray")
        hint.grid(row=1, column=0, columnspan=3, pady=3)
        rows_widgets.append(hint)

    theme.update(ui_frame)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    ev = entry.get("event")
    if ev == "LoadGame":
        do_catchup()
    if (ev == "MissionAccepted") and (is_courier(entry.get("Name"))):
        mid = entry.get("MissionID")
        sysn = entry.get("DestinationSystem")
        sta = entry.get("DestinationStation")
        if mid and sysn and sta:
            with lock:
                mission_id_map[mid] = (sysn, sta)
                mission_counts[(sysn, sta)] = mission_counts.get((sysn, sta), 0) + 1

    elif (ev == "MissionRedirected") and (is_courier(entry.get("Name"))):
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

    elif (ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed")) and (is_courier(entry.get("Name"))):
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
        logger.error(f"Error while updating the UI: {e}")

# === Catchup from Journals ===
def do_catchup():
    logger.info("do_catchup() gestartet")
    home = os.path.expanduser("~")
    journal_dir = os.path.join(home, "Saved Games", "Frontier Developments", "Elite Dangerous")
    logger.info(f"do_catchup: Journal-Path = {journal_dir}")
    if not os.path.isdir(journal_dir):
        logger.warning(f"Journal-Path not found: {journal_dir}")
        return

    try:
        files = sorted(f for f in os.listdir(journal_dir) if f.startswith("Journal") and f.endswith(".log"))
        logger.info(f"Journal-Dateien: {files}")
    except Exception as e:
        logger.error(f"Error while listing the Journals: {e}")
        return

    

    # 1. collect all active Missions
    active_mission_ids = set()
    for fname in reversed(files):
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
                            if fnmatch.fnmatch(mission.get("Name"), "Mission_Courier_*"):
                                mid = mission.get("MissionID")
                                logger.info(f"Found Courier Mission in Active missions ID: {mid}")
                                if mid is not None:
                                    active_mission_ids.add(mid)
        except Exception as e:
            logger.error(f"Error while reading the Journal 1 {full}: {e}")

    logger.info(f"Found active missionIDs: {active_mission_ids}")

    # 2. get System and Station of active missionIDs
    for fname in reversed(files):
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
                    na = obj.get("Name")

                    if (ev == "MissionAccepted"):
                        mid = obj.get("MissionID")
                        if mid in active_mission_ids:
                            sysn = obj.get("DestinationSystem")
                            sta = obj.get("DestinationStation")
                            if sysn and sta:
                                with lock:
                                    if mid not in mission_id_map:
                                        mission_id_map[mid] = (sysn, sta)
                                        mission_counts[(sysn, sta)] = mission_counts.get((sysn, sta), 0) + 1
                                        logger.info(f"do_catchup: MissionAccepted: {mid} → {(sysn, sta, na)}")

                    elif (ev in ("MissionCompleted", "MissionAbandoned", "MissionFailed")):
                        mid = obj.get("MissionID")
                        if mid in active_mission_ids:
                            with lock:
                                if mid in mission_id_map:
                                    key = mission_id_map.pop(mid)
                                    mission_counts[key] = mission_counts.get(key, 1) - 1
                                    if mission_counts[key] <= 0:
                                        mission_counts.pop(key, None)
                                    logger.info(f"do_catchup: Mission ended: {mid} → {key},, {na}")

        except Exception as e:
            logger.error(f"Error while reading the Journal 2 {full}: {e}")

# === Plugin entry ===
def plugin_start3(plugin_dir):
    do_catchup()
    return "EDMC-Courier-Mission"

def plugin_load():
    return plugin_instance

def plugin_stop():
    pass

import threading
import tkinter as tk
from theme import theme
import logging

mission_counts = {}
mission_id_map = {}
lock = threading.Lock()

ui_frame = None
rows_widgets = []  # Liste mit Zeilen (je 3 Labels)

def plugin_start3(plugin_dir):
    return "Courier"

def plugin_app(parent: tk.Frame):
    global ui_frame, rows_widgets

    ui_frame = tk.Frame(parent)
    # Überschrift
    header = tk.Label(ui_frame, text="Courier-Missionen", font=("TkDefaultFont", 10, "bold"))
    header.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(2,2))

    # Spaltenüberschriften
    lbl_sys = tk.Label(ui_frame, text="System")
    lbl_sta = tk.Label(ui_frame, text="Station")
    lbl_cnt = tk.Label(ui_frame, text="Anz.")
    lbl_sys.grid(row=1, column=0, sticky=tk.W, padx=2)
    lbl_sta.grid(row=1, column=1, sticky=tk.W, padx=2)
    lbl_cnt.grid(row=1, column=2, sticky=tk.E, padx=2)

    # Keine festen Zeilen mehr anlegen, wird dynamisch gebaut
    rows_widgets.clear()

    theme.update(ui_frame)
    return ui_frame

def update_ui_table():
    global rows_widgets
    if ui_frame is None:
        return

    # Zuerst alte Zeilen löschen
    for (w0, w1, w2) in rows_widgets:
        w0.destroy()
        w1.destroy()
        w2.destroy()
    rows_widgets.clear()

    with lock:
        items = list(mission_counts.items())

    # Neue Zeilen dynamisch erzeugen
    start_row = 2  # unter Überschrift und Kopfzeile
    for i, (sys_sta, count) in enumerate(items):
        sysname, station = sys_sta
        w0 = tk.Label(ui_frame, text=sysname)
        w1 = tk.Label(ui_frame, text=station)
        w2 = tk.Label(ui_frame, text=str(count))
        w0.grid(row=start_row + i, column=0, sticky=tk.W, padx=2)
        w1.grid(row=start_row + i, column=1, sticky=tk.W, padx=2)
        w2.grid(row=start_row + i, column=2, sticky=tk.E, padx=2)
        rows_widgets.append((w0, w1, w2))

    theme.update(ui_frame)

def journal_entry(cmdr, is_beta, journal):
    ev = journal.get("event")
    if not ev:
        return
    if ev == "MissionAccepted":
        mid = journal.get("MissionID")
        sysn = journal.get("DestinationSystem")
        sta = journal.get("DestinationStation")
        if mid and sysn and sta:
            with lock:
                mission_id_map[mid] = (sysn, sta)
                mission_counts[(sysn, sta)] = mission_counts.get((sysn, sta), 0) + 1
    elif ev == "MissionRedirected":
        mid = journal.get("MissionID")
        newsys = journal.get("NewDestinationSystem")
        newsta = journal.get("NewDestinationStation")
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
        mid = journal.get("MissionID")
        if mid in mission_id_map:
            with lock:
                key = mission_id_map.pop(mid)
                mission_counts[key] = mission_counts.get(key, 1) - 1
                if mission_counts[key] <= 0:
                    del mission_counts[key]

    try:
        ui_frame.after(0, update_ui_table)
    except Exception as e:
        logging.getLogger().error(f"Error updating UI: {e}")

def plugin_stop():
    return

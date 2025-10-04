import tkinter as tk
import myNotebook as nb
import logging
from load import logger
from typing import Optional
from config import config
from ttkHyperlinkLabel import HyperlinkLabel

# Settings-Variablen global halten, damit prefs_changed darauf zugreifen kann
check_updates_var: Optional[tk.IntVar] = None
display_mission_count_var: Optional[tk.IntVar] = None
# ... andere Variablen falls nötig
download_url = "https://github.com/P0rt3r74/EDMC-Courier-Mission"

def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> Optional[tk.Frame]:
    logger.info("plugin_prefs() aus settings.py aufgerufen")
    
    global check_updates_var, display_mission_count_var
    
    frame = nb.Frame(parent)  # Wichtig: Großes F bei Frame
    
    # Initialwerte aus config laden
    check_updates_var = tk.IntVar(value=config.get_bool("EDMC-Courier-Mission.check_updates"))
    display_mission_count_var = tk.IntVar(value=config.get_bool("EDMC-Courier-Mission.display_mission_count"))

    nb.Label(frame, text="Courier-Mission Plugin Settings", font=("TkDefaultFont", 10)).grid(row=0, column=0, sticky=tk.W, pady=10, padx=10)
    
    nb.Checkbutton(frame, text="Check for Updates on Start", variable=check_updates_var).grid(row=1, column=0, sticky=tk.W, padx=20)
    nb.Checkbutton(frame, text="Display Mission Count", variable=display_mission_count_var).grid(row=2, column=0, sticky=tk.W, padx=20)
    
    
    # Beispiel: Hyperlink zu Github
    HyperlinkLabel(frame, text="Github", background=nb.Label().cget("background"), url=download_url, underline=True)\
        .grid(row=3, column=0, sticky=tk.W, padx=20, pady=10)
        
    
    nb.Label(frame, text="Made by CMDR P0rt3r").grid(row=4, column=0, sticky=tk.W, pady=5, padx=10)
    
    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Wird vom EDMC-Framework aufgerufen, wenn die Einstellungen geschlossen wurden.
    """
    logger.info("prefs_changed() aus settings.py aufgerufen - Einstellungen speichern")

    if check_updates_var is not None:
        config.set("EDMC-Courier-Mission.check_updates", bool(check_updates_var.get()))
    if display_mission_count_var is not None:
        config.set("EDMC-Courier-Mission.display_mission_count", bool(display_mission_count_var.get()))

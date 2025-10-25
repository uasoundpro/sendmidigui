import difflib
import tkinter as tk
import subprocess
import csv
import os
import ctypes
import sys
import time
import threading
import json
from datetime import datetime
import shutil

# =================== MIDI DEVICE SETUP =====================
DEFAULT_DEVICE = "loopMIDI Port"
ALT_DEVICE = "Morningstar MC8 Pro"
QUAD_CORTEX_DEVICE = "Quad Cortex MIDI Control"  # Added new device for monitoring
SENDMIDI_PATH = "C:\\Tools\\sendmidi\\sendmidi.exe"
ICON_FILE = "sendmidi.ico"
SCRIPT_PATH = os.path.abspath(__file__)
CSV_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList.csv")  # This will be updated dynamically
CONFIG_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), "config.json")
SETLIST_FOLDER = os.path.join(os.path.dirname(SCRIPT_PATH), "Setlist")
CSV_FILE_DEFAULT_SOURCE = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList-DEFAULT.csv")  # Added for clarity

# ================ DARK THEME COLORS ===============
DARK_BG = "#1e1e1e"
DARK_FG = "#ffffff"
BUTTON_BG = "#2d2d2d"
BUTTON_HL = "#3c3c3c"
DISABLED_BG = "#555555"
HIGHLIGHT_BG = "#5b82a7"
SCROLLBAR_COLOR = "#444444"

big_font = ("Comic Sans MS", 20)
narrow_font_plain = ("Arial", 10)
narrow_font_small = ("Arial", 9)

# Declare setlist_display_label as a global variable so it can be consistently accessed
setlist_display_label = None


# =================== GLOBAL CONFIG MANAGEMENT =====================
def save_config(device=None, csv_file_used=None, relaunch_on_monitor_fail=None, current_setlist_display_name=None):
    """Saves application configuration to config.json."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}  # handle corrupted config
    if device is not None:
        config["device"] = device
    if csv_file_used is not None:
        config["csv_file_used"] = os.path.abspath(csv_file_used)  # Store absolute path
    if relaunch_on_monitor_fail is not None:
        config["relaunch_on_monitor_fail"] = relaunch_on_monitor_fail
    if current_setlist_display_name is not None:
        config["current_setlist_display_name"] = current_setlist_display_name
    config["last_run"] = time.time()  # Always update last_run
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


# =================== UTILITY FUNCTIONS (moved to global scope) =====================
def create_ordered_setlist_csv(setlist_path, base_csv_path, output_csv_path):
    """
    Creates an ordered CSV from a setlist file and a base CSV.
    Songs not found in the base CSV will be marked as '# MISSING'.
    """
    try:
        with open(setlist_path, "r", encoding="utf-8") as f:
            song_names = [line.strip() for line in f if line.strip()]

        with open(base_csv_path, "r", encoding="utf-8") as f:
            all_rows = [row for row in csv.reader(f.read().splitlines()) if row]
        label_lookup = {row[0].strip(): row for row in all_rows}
        # Fix: Removed duplicate 'k' in dictionary comprehension
        lower_keys = {k.lower(): k for k in label_lookup}

        pinned_top = ["MUTE", "DEFAULT (JCM800)", "DEFAULT (RVerb)"]
        pinned_bottom = ["TEST 123"]
        all_requested = pinned_top + song_names + pinned_bottom

        output_rows = []
        for name in all_requested:
            match_key = lower_keys.get(name.lower())
            if match_key:
                output_rows.append(label_lookup[match_key])
            else:
                close_matches = difflib.get_close_matches(name.lower(), lower_keys.keys(), n=1, cutoff=0.7)
                if close_matches:
                    best_match = lower_keys[close_matches[0]]
                    output_rows.append(label_lookup[best_match])
                else:
                    output_rows.append([name, "", "", "# MISSING"])

        with open(output_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(output_rows)

    except Exception as e:
        print("Error generating setlist CSV:", e)
        # Fallback to base_csv_path if setlist creation fails
        shutil.copyfile(base_csv_path, output_csv_path)


# =================== SETLIST SELECTION PROMPT (initial launch) =====================
def choose_setlist():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}

    # Check if relaunch is due to monitor failure
    if config.get("relaunch_on_monitor_fail"):
        # If so, skip setlist prompt and proceed to device selection
        choose_device_and_launch()
        return

    def launch_with(file_path_for_csv, display_name):
        # Always copy the chosen or default CSV to the main MidiList.csv path
        # This makes it consistent for the main app to always read from CSV_FILE
        temp_path = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList.csv")
        if os.path.abspath(file_path_for_csv) != os.path.abspath(temp_path):
            shutil.copyfile(file_path_for_csv, temp_path)

        save_config(csv_file_used=file_path_for_csv,
                    current_setlist_display_name=display_name)  # Save chosen CSV & display name

        choose_device_and_launch()

    def choose_setlist_file():
        setlist_window.destroy()  # Correctly destroys initial window here
        setlist_file_window = tk.Tk()
        setlist_file_window.title("Select Setlist File")
        setlist_file_window.configure(bg=DARK_BG)
        setlist_file_window.geometry("600x600+200+100")

        tk.Label(setlist_file_window, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=DARK_BG,
                 fg=DARK_FG).pack(pady=20)

        files_frame = tk.Frame(setlist_file_window, bg=DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(files_frame, bg=DARK_BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(files_frame, orient="vertical", command=canvas.yview,
                                 bg=SCROLLBAR_COLOR, troughcolor=DARK_BG, highlightbackground=DARK_BG)
        scrollbar.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollable_buttons_frame = tk.Frame(canvas, bg=DARK_BG)
        canvas_frame = canvas.create_window((0, 0), window=scrollable_buttons_frame, anchor="nw")

        scrollable_buttons_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        if not os.path.exists(SETLIST_FOLDER):
            os.makedirs(SETLIST_FOLDER)

        setlist_files = [f for f in os.listdir(SETLIST_FOLDER) if f.endswith(".txt")]
        if not setlist_files:
            tk.Label(scrollable_buttons_frame, text="No setlist files found.", font=narrow_font_plain, bg=DARK_BG,
                     fg=DARK_FG).pack(pady=10)
        else:
            for sl_file in setlist_files:
                file_path = os.path.join(SETLIST_FOLDER, sl_file)
                first_line = ""
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if not first_line:
                            first_line = sl_file  # Fallback to filename if first line is empty
                except Exception as e:
                    first_line = f"Error reading {sl_file}"
                    print(f"Error reading first line of {sl_file}: {e}")

                btn = tk.Button(scrollable_buttons_frame, text=first_line, font=("Arial", 13),
                                width=65, pady=13,
                                command=lambda path=file_path: process_selected_setlist(path, setlist_file_window),
                                bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL, activeforeground=DARK_FG)
                btn.pack(pady=5, padx=10)

        setlist_file_window.mainloop()

    def process_selected_setlist(selected_setlist_path, current_window):
        current_window.destroy()
        temp_csv = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList_Set.csv")
        create_ordered_setlist_csv(selected_setlist_path, CSV_FILE_DEFAULT_SOURCE, temp_csv)

        # Read the first line of the selected .txt file for display name
        display_name = ""
        try:
            with open(selected_setlist_path, "r", encoding="utf-8") as f:
                display_name = f.readline().strip()
        except Exception as e:  # Corrected indentation
            print(f"Error reading first line of {selected_setlist_path}: {e}")

        if not display_name:  # Fallback to filename if first line is empty or error
            display_name = os.path.basename(selected_setlist_path).replace(".txt", "")

        launch_with(temp_csv, display_name)

    # --- Initial setlist prompt always appears normally ---
    setlist_window = tk.Tk()
    setlist_window.title("Load Setlist?")
    setlist_window.configure(bg=DARK_BG)
    setlist_window.geometry("600x300+{}+{}".format(
        setlist_window.winfo_screenwidth() // 2 - 300,
        setlist_window.winfo_screenheight() // 2 - 150
    ))

    tk.Label(setlist_window, text="Load Setlist or Default Songs?", font=big_font, bg=DARK_BG, fg=DARK_FG).pack(pady=20)

    frame = tk.Frame(setlist_window, bg=DARK_BG)
    frame.pack(pady=10)

    def handle_default_launch():
        setlist_window.destroy()
        launch_with(CSV_FILE_DEFAULT_SOURCE, "Default Songs")  # Pass "Default Songs" as display name

    tk.Button(frame, text="Setlist", font=big_font, width=12, height=2,
              command=choose_setlist_file, bg="#2a8f44", fg="white").grid(row=0, column=0, padx=10)

    tk.Button(frame, text="Default", font=big_font, width=12, height=2,
              command=handle_default_launch, bg="#28578f", fg="white").grid(row=0, column=1, padx=10)

    setlist_window.mainloop()


# ================== DEVICE SELECTION PROMPT =====================
def choose_device_and_launch():
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}

    # Check if relaunch is due to monitor failure
    if config.get("relaunch_on_monitor_fail"):
        # If so, skip device prompt and proceed to main app
        launch_main_app()
        return

    def select_device(device):
        chooser.destroy()
        selected = DEFAULT_DEVICE if device == "BT" else ALT_DEVICE
        save_config(device=selected)  # Use the unified save_config
        os.environ["MIDI_DEVICE"] = selected
        launch_main_app()

    def timeout_default():
        # Only run timeout_default if the chooser window still exists
        if chooser.winfo_exists():
            chooser.destroy()
            save_config(device=DEFAULT_DEVICE)  # Use the unified save_config
            os.environ["MIDI_DEVICE"] = DEFAULT_DEVICE
            launch_main_app()

    # Instance variable for the "List MIDI Devices" popup in the chooser window
    list_devices_chooser_popup_instance = None

    def list_devices():
        nonlocal list_devices_chooser_popup_instance  # Declare nonlocal

        # Check if an instance of the list devices popup is already open
        if list_devices_chooser_popup_instance and list_devices_chooser_popup_instance.winfo_exists():
            list_devices_chooser_popup_instance.lift()  # Bring it to the front
            return

        try:
            result = subprocess.run([SENDMIDI_PATH, "list"], capture_output=True, text=True)
            device_list = result.stdout.strip().splitlines()
        except Exception as e:
            print(f"Error listing devices: {e}")
            return

        if not device_list:
            print("No MIDI devices found.")
            return

        list_window = tk.Toplevel(chooser)
        list_devices_chooser_popup_instance = list_window  # Store the instance

        def on_list_devices_chooser_popup_close():
            nonlocal list_devices_chooser_popup_instance
            list_devices_chooser_popup_instance = None  # Reset the instance variable on close
            list_window.destroy()

        list_window.protocol("WM_DELETE_WINDOW", on_list_devices_chooser_popup_close)  # Handle window close event

        list_window.title("Available MIDI Devices")
        list_window.configure(bg=DARK_BG)
        list_window.geometry("400x600+200+100")

        tk.Label(list_window, text="Select a MIDI Device:", font=big_font, bg=DARK_BG, fg=DARK_FG).pack(pady=10)

        active_devices = []
        disabled_devices = []

        for dev in device_list:
            is_disabled = dev == "Microsoft GS Wavetable Synth" or dev.startswith("MIDIOUT")
            if is_disabled:
                disabled_devices.append(dev)
            else:
                active_devices.append(dev)

        # Create buttons for active devices first
        for dev in active_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=BUTTON_BG, fg=DARK_FG,
                activebackground=BUTTON_HL, activeforeground=DARK_FG,
                command=(lambda d=dev: select_from_list(d, list_window))
            )
            btn.pack(pady=5)

        # Then create buttons for disabled devices
        for dev in disabled_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=DISABLED_BG, fg="#999999",
                activebackground=DISABLED_BG, activeforeground="#999999",  # No active highlight for disabled
                state="disabled"
            )
            btn.pack(pady=5)

    def select_from_list(device_name, window):
        nonlocal list_devices_chooser_popup_instance  # Declare nonlocal to reset instance

        window.destroy()
        list_devices_chooser_popup_instance = None  # Reset instance variable when closed programmatically

        chooser.destroy()

        # Map Quad Cortex to ALT_DEVICE for consistent behavior
        actual_device_to_set = device_name
        if device_name == QUAD_CORTEX_DEVICE:
            actual_device_to_set = ALT_DEVICE

        save_config(device=actual_device_to_set)
        os.environ["MIDI_DEVICE"] = actual_device_to_set
        launch_main_app()

    chooser = tk.Tk()
    chooser.title("Select MIDI Device")
    chooser.configure(bg=DARK_BG)
    chooser.geometry("700x300+{}+{}".format(
        chooser.winfo_screenwidth() // 2 - 350,
        chooser.winfo_screenheight() // 2 - 150
    ))
    tk.Label(chooser, text="Select MIDI Device:", bg=DARK_BG, fg=DARK_FG, font=big_font).pack(pady=10)

    btn_frame = tk.Frame(chooser, bg=DARK_BG)
    btn_frame.pack(pady=5)

    btn_bt = tk.Button(btn_frame, text="BT (Default)", font=big_font, width=12, height=2,
                       command=lambda: select_device("BT"), bg="#2a8f44", fg="white")
    btn_bt.grid(row=0, column=0, padx=5)

    btn_usb = tk.Button(btn_frame, text="USB", font=big_font, width=12, height=2,
                        command=lambda: select_device("USB"), bg="#28578f", fg="white")
    btn_usb.grid(row=0, column=1, padx=5)

    btn_list = tk.Button(chooser, text="List MIDI Devices", font=narrow_font_plain, command=list_devices,
                         bg="#444444", fg=DARK_FG, activebackground=BUTTON_HL, activeforeground=DARK_FG, bd=0, padx=6,
                         pady=6, height=2)
    btn_list.pack(pady=5)

    timer_label = tk.Label(chooser, text="", bg=DARK_BG, fg=DARK_FG, font=narrow_font_plain)
    timer_label.pack(pady=5)

    timer_count = [10]

    def countdown():
        # Only run countdown if the chooser window still exists
        if chooser.winfo_exists() and timer_count[0] > 0:
            timer_label.config(text=f"Defaulting to BT in {timer_count[0]}s")
            timer_count[0] -= 1
            chooser.after(1000, countdown)
        elif chooser.winfo_exists() and timer_count[0] == 0:
            timeout_default()

    countdown()
    chooser.mainloop()


# =================== LAUNCH MAIN GUI =====================
def launch_main_app():
    global CSV_FILE, setlist_display_label  # Declare setlist_display_label as global here
    MIDI_DEVICE = os.environ.get("MIDI_DEVICE", DEFAULT_DEVICE)

    root = tk.Tk()
    root.title("MIDI Patch Sender")
    root.configure(bg=DARK_BG)

    icon_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), ICON_FILE)
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
            if sys.platform == "win32":
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sendmidi.gui")
        except Exception as e:
            print(f"Icon load error: {e}")

    window_width = 500
    window_height = 1150
    screen_width = root.winfo_screenwidth()
    x = screen_width - window_width
    y = 0
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def on_close():
        save_config(device=MIDI_DEVICE)  # Use the unified save_config
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # Load config to check if this launch is due to monitor failure and get setlist name
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}

    # If this launch was due to monitor failure, reset the flag in config
    if config.get("relaunch_on_monitor_fail"):
        save_config(relaunch_on_monitor_fail=False)

    current_setlist_name_for_display = config.get("current_setlist_display_name", "Unknown Setlist")

    switch_confirmed = False
    switch_timer_id = None
    last_press_time = 0  # Moved to main app scope
    last_selected_button = None  # Moved to main app scope
    all_buttons = []  # Moved to main app scope
    testing_toast_label = None  # To manage the "TESTING" toast
    usb_stable_start_time = None  # New variable for failback stability tracking
    # New flag to track if the user declined the USB switch
    user_declined_usb_switch = False

    # Instance variables for managing single popup windows from the main GUI
    setlist_popup_window_instance = None
    list_devices_popup_window_instance = None

    def show_toast(msg, duration=2000, bg="#303030", fg="white"):
        # Destroy any existing general toast
        for widget in root.winfo_children():
            if isinstance(widget,
                          tk.Label) and widget.winfo_y() < 50 and widget != testing_toast_label:  # Heuristic to identify toast
                widget.destroy()

        toast = tk.Label(root, text=msg, bg=bg, fg=fg, font=narrow_font_small)
        toast.place(relx=0.5, rely=0.01, anchor="n")
        root.after(duration, toast.destroy)

    def send_midi(command_list):
        for command in command_list:
            # Determine the target device for the current command
            target_device = MIDI_DEVICE  # Default target is the globally selected MIDI_DEVICE

            # Apply specific routing only when in ALT_DEVICE (Morningstar MC8 Pro) mode
            if MIDI_DEVICE == ALT_DEVICE:
                # Check if the command is a channel message (starts with "ch")
                if len(command) > 1 and command[0] == "ch":
                    channel_str = command[1]  # The channel number as a string
                    if channel_str == "2":
                        target_device = ALT_DEVICE  # Send channel 2 messages to Morningstar MC8 Pro
                    elif channel_str == "1":
                        target_device = QUAD_CORTEX_DEVICE  # Send channel 1 messages to Quad Cortex MIDI Control
                    # If it's a channel message but not 1 or 2, it will default to ALT_DEVICE as target_device is already set to ALT_DEVICE.
                # If it's not a "ch" command, it will also default to ALT_DEVICE.

            # Construct and run the subprocess command with the determined target_device
            full_cmd = [SENDMIDI_PATH, "dev", target_device]
            # Ensure each element in the command is a string
            full_cmd.extend([str(arg) for arg in command])
            subprocess.run(full_cmd)

    # --- New functions for setlist selection from main GUI ---
    def show_setlist_selection_popup():
        nonlocal setlist_popup_window_instance  # Declare nonlocal

        # Check if an instance of the setlist popup is already open
        if setlist_popup_window_instance and setlist_popup_window_instance.winfo_exists():
            setlist_popup_window_instance.lift()  # Bring it to the front
            return

        setlist_popup = tk.Toplevel(root)
        setlist_popup_window_instance = setlist_popup  # Store the instance

        def on_setlist_popup_close():
            nonlocal setlist_popup_window_instance
            setlist_popup_window_instance = None  # Reset the instance variable on close
            setlist_popup.destroy()

        setlist_popup.protocol("WM_DELETE_WINDOW", on_setlist_popup_close)  # Handle window close event

        setlist_popup.title("Select Setlist File")
        setlist_popup.configure(bg=DARK_BG)
        setlist_popup.geometry("600x600+200+100")  # Adjust as needed

        tk.Label(setlist_popup, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=DARK_BG, fg=DARK_FG).pack(
            pady=20)

        files_frame = tk.Frame(setlist_popup, bg=DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_popup = tk.Canvas(files_frame, bg=DARK_BG, highlightthickness=0)
        canvas_popup.pack(side="left", fill="both", expand=True)

        scrollbar_popup = tk.Scrollbar(files_frame, orient="vertical", command=canvas_popup.yview,
                                       bg=SCROLLBAR_COLOR, troughcolor=DARK_BG, highlightbackground=DARK_BG)
        scrollbar_popup.pack(side="right", fill="y")

        canvas_popup.configure(yscrollcommand=scrollbar_popup.set)  # Corrected: use scrollbar_popup
        scrollable_buttons_frame_popup = tk.Frame(canvas_popup, bg=DARK_BG)
        canvas_frame_popup = canvas_popup.create_window((0, 0), window=scrollable_buttons_frame_popup, anchor="nw")

        scrollable_buttons_frame_popup.bind("<Configure>",
                                            lambda e: canvas_popup.configure(scrollregion=canvas_popup.bbox("all")))
        canvas_popup.bind("<Configure>", lambda e: canvas_popup.itemconfig(canvas_frame_popup, width=e.width))
        canvas_popup.bind_all("<MouseWheel>", lambda e: canvas_popup.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Add "Load Default Songs" button option at the top
        tk.Button(scrollable_buttons_frame_popup, text="Load Default Songs", font=("Arial", 13),
                  width=65, pady=13,
                  command=lambda: _process_selected_setlist_from_main_gui(
                      CSV_FILE_DEFAULT_SOURCE, setlist_popup
                  ),
                  bg="#28578f", fg="white", activebackground=BUTTON_HL, activeforeground=DARK_FG).pack(pady=5, padx=10)

        if not os.path.exists(SETLIST_FOLDER):
            os.makedirs(SETLIST_FOLDER)

        setlist_files = [f for f in os.listdir(SETLIST_FOLDER) if f.endswith(".txt")]
        if not setlist_files:
            tk.Label(scrollable_buttons_frame_popup, text="No setlist files found.", font=narrow_font_plain, bg=DARK_BG,
                     fg=DARK_FG).pack(pady=10)
        else:
            for sl_file in setlist_files:
                file_path = os.path.join(SETLIST_FOLDER, sl_file)
                first_line_content = ""
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        first_line_content = f.readline().strip()
                        if not first_line_content:
                            first_line_content = sl_file  # Fallback to filename if first line is empty
                except Exception as e:
                    first_line_content = f"Error reading {sl_file}"
                    print(f"Error reading first line of {sl_file}: {e}")

                btn = tk.Button(scrollable_buttons_frame_popup, text=first_line_content, font=("Arial", 13),
                                width=65, pady=13,
                                command=lambda path=file_path: _process_selected_setlist_from_main_gui(path,
                                                                                                       setlist_popup),
                                bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL, activeforeground=DARK_FG)
                btn.pack(pady=5, padx=10)

    def _process_selected_setlist_from_main_gui(selected_setlist_path, current_popup_window):
        global CSV_FILE, setlist_display_label  # Access global setlist_display_label
        nonlocal current_setlist_name_for_display  # Update the variable for display
        nonlocal setlist_popup_window_instance  # Declare nonlocal to reset instance

        current_popup_window.destroy()
        setlist_popup_window_instance = None  # Reset instance variable when closed programmatically

        if selected_setlist_path.endswith(".txt"):
            temp_csv = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList_Set.csv")
            create_ordered_setlist_csv(selected_setlist_path, CSV_FILE_DEFAULT_SOURCE, temp_csv)
            CSV_FILE = temp_csv

            display_name = ""
            try:
                with open(selected_setlist_path, "r", encoding="utf-8") as f:
                    display_name = f.readline().strip()
            except Exception as e:  # Corrected indentation
                print(f"Error reading first line of {selected_setlist_path}: {e}")

            if not display_name:  # Fallback to filename if first line is empty or error
                display_name = os.path.basename(selected_setlist_path).replace(".txt", "")

            current_setlist_name_for_display = display_name
        else:  # It's already a CSV (like MidiList-DEFAULT.csv)
            CSV_FILE = selected_setlist_path
            current_setlist_name_for_display = "Default Songs"

        save_config(csv_file_used=CSV_FILE,
                    current_setlist_display_name=current_setlist_name_for_display)  # Save the new chosen CSV file and display name

        # Added check for setlist_display_label existence before configuring
        if setlist_display_label and setlist_display_label.winfo_exists():
            setlist_display_label.config(text=f"Setlist: {current_setlist_name_for_display}")  # Update label
        _load_and_display_patches()  # Reload patches with the new CSV_FILE
        show_toast(f"Setlist loaded: {current_setlist_name_for_display}")

    # --- End of new setlist functions ---

    def switch_mode():
        nonlocal switch_confirmed, switch_timer_id, MIDI_DEVICE, user_declined_usb_switch
        if not switch_confirmed:
            show_toast("Press again to switch MIDI mode")
            switch_btn.config(bg="#e6c34d")
            switch_confirmed = True
            if switch_timer_id:
                root.after_cancel(switch_timer_id)
            switch_timer_id = root.after(1000, reset_switch_button)
        else:
            new_device = ALT_DEVICE if MIDI_DEVICE == DEFAULT_DEVICE else DEFAULT_DEVICE
            save_config(device=new_device)  # Use the unified save_config
            os.environ["MIDI_DEVICE"] = new_device  # Ensure environment variable is updated
            MIDI_DEVICE = new_device  # Update the current MIDI_DEVICE
            mode_label.config(text=f"Using {MIDI_DEVICE}")  # Update the display
            show_toast(f"Switched to {MIDI_DEVICE}")
            switch_confirmed = False
            switch_btn.config(bg="#b02f2f")  # Reset button color after successful switch
            # If the user manually switches to USB, reset the decline flag
            if MIDI_DEVICE == ALT_DEVICE:
                user_declined_usb_switch = False

    def reset_switch_button():
        nonlocal switch_confirmed, switch_timer_id
        switch_confirmed = False
        switch_timer_id = None
        switch_btn.config(bg="#b02f2f")

    def list_devices():
        nonlocal list_devices_popup_window_instance  # Declare nonlocal

        # Check if an instance of the list devices popup is already open
        if list_devices_popup_window_instance and list_devices_popup_window_instance.winfo_exists():
            list_devices_popup_window_instance.lift()  # Bring it to the front
            return

        try:
            result = subprocess.run([SENDMIDI_PATH, "list"], capture_output=True, text=True)
            device_list = result.stdout.strip().splitlines()
        except Exception as e:
            print(f"Error listing devices: {e}")
            show_toast(f"Error listing devices: {e}")  # Show toast for error
            return

        if not device_list:
            show_toast("No MIDI devices found.")
            return

        list_window = tk.Toplevel(root)
        list_devices_popup_window_instance = list_window  # Store the instance

        def on_list_devices_popup_close():
            nonlocal list_devices_popup_window_instance
            list_devices_popup_window_instance = None  # Reset the instance variable on close
            list_window.destroy()

        list_window.protocol("WM_DELETE_WINDOW", on_list_devices_popup_close)  # Handle window close event

        list_window.title("Available MIDI Devices")
        list_window.configure(bg=DARK_BG)
        list_window.geometry("400x600+200+100")

        tk.Label(list_window, text="Select a MIDI Device:", font=big_font, bg=DARK_BG, fg=DARK_FG).pack(pady=10)

        active_devices = []
        disabled_devices = []

        for dev in device_list:
            is_disabled = dev == "Microsoft GS Wavetable Synth" or dev.startswith("MIDIOUT")
            if is_disabled:
                disabled_devices.append(dev)
            else:
                active_devices.append(dev)

        # Create buttons for active devices first
        for dev in active_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=BUTTON_BG, fg=DARK_FG,
                activebackground=BUTTON_HL, activeforeground=DARK_FG,
                command=(lambda d=dev: select_new_device(d, list_window))
            )
            btn.pack(pady=5)

        # Then create buttons for disabled devices
        for dev in disabled_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=DISABLED_BG, fg="#999999",
                activebackground=DISABLED_BG, activeforeground="#999999",  # No active highlight for disabled
                state="disabled"
            )
            btn.pack(pady=5)

    def select_new_device(device_name, window):
        nonlocal MIDI_DEVICE, user_declined_usb_switch  # Access MIDI_DEVICE and user_declined_usb_switch
        nonlocal list_devices_popup_window_instance  # Declare nonlocal to reset instance

        window.destroy()
        list_devices_popup_window_instance = None  # Reset instance variable when closed programmatically

        # Map Quad Cortex to ALT_DEVICE for consistent behavior
        actual_device_to_set = device_name
        if device_name == QUAD_CORTEX_DEVICE:
            actual_device_to_set = ALT_DEVICE

        save_config(device=actual_device_to_set)  # Save the new device choice
        os.environ["MIDI_DEVICE"] = actual_device_to_set  # Ensure environment variable is updated
        MIDI_DEVICE = actual_device_to_set  # Update the current MIDI_DEVICE
        mode_label.config(text=f"Using {MIDI_DEVICE}")  # Update the display
        show_toast(f"Switched to {MIDI_DEVICE}")
        # If the user manually switches to USB, reset the decline flag
        if MIDI_DEVICE == ALT_DEVICE:
            user_declined_usb_switch = False
        # Removed subprocess.Popen and root.destroy() to prevent re-launch

    top_bar = tk.Frame(root, bg=DARK_BG)
    top_bar.pack(fill="x", pady=2, padx=2)

    mode_label = tk.Label(top_bar, text=f"Using {MIDI_DEVICE}", fg=DARK_FG, bg=DARK_BG, font=narrow_font_plain)
    mode_label.pack(side="right", padx=4)

    switch_btn = tk.Button(top_bar, text="Switch Mode", font=narrow_font_plain, command=switch_mode,
                           bg="#b02f2f", fg=DARK_FG, activebackground="#902020", activeforeground=DARK_FG, bd=0, padx=6,
                           pady=6, height=2)
    switch_btn.pack(side="left")

    list_btn = tk.Button(top_bar, text="List MIDI Devices", font=narrow_font_plain,
                         command=list_devices, bg="#444444", fg=DARK_FG, activebackground=BUTTON_HL,
                         activeforeground=DARK_FG, bd=0, padx=6, pady=6, height=2)
    list_btn.pack(side="left", padx=(5, 0))

    # --- New "Choose Setlist" button ---
    choose_setlist_btn = tk.Button(top_bar, text="Choose Setlist", font=narrow_font_plain,
                                   command=show_setlist_selection_popup, bg="#444444", fg=DARK_FG,
                                   activebackground=BUTTON_HL,
                                   activeforeground=DARK_FG, bd=0, padx=6, pady=6, height=2)
    choose_setlist_btn.pack(side="left", padx=(5, 0))
    # --- End of new button ---

    # --- Setlist Name Display Frame and Label ---
    setlist_display_frame = tk.Frame(root, bg=DARK_BG)
    setlist_display_frame.pack(fill="x", pady=5)  # This frame will be between top_bar and up_button_frame

    setlist_display_label = tk.Label(setlist_display_frame, text=f"Setlist: {current_setlist_name_for_display}",
                                     fg=DARK_FG, bg=DARK_BG, font=narrow_font_plain)
    setlist_display_label.pack(side="left", padx=5)  # Pack the label within its new frame
    # --- End Setlist Name Display Frame and Label ---

    up_button_frame = tk.Frame(root, bg=DARK_BG)
    up_button_frame.pack(fill="x")

    def scroll_up():
        btn_up.config(relief="sunken")  # Simulate press
        canvas.yview_scroll(-1, "units")
        root.after(150, lambda: btn_up.config(relief="raised"))  # Revert after short delay

    btn_up = tk.Button(up_button_frame, text="↑", font=("Arial", 36, "bold"), height=1,
                       command=scroll_up, bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL,
                       activeforeground=DARK_FG, relief="raised", bd=2)  # Added relief and bd
    btn_up.pack(fill="x")

    main_frame = tk.Frame(root, bg=DARK_BG)
    main_frame.pack(fill="both", expand=True)

    canvas = tk.Canvas(main_frame, bg=DARK_BG, highlightthickness=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview,
                             bg=SCROLLBAR_COLOR, troughcolor=DARK_BG, highlightbackground=DARK_BG)
    scrollbar.config(width=50)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)
    scrollable_frame = tk.Frame(canvas, bg=DARK_BG)
    # Fix: Changed 'scrollable_buttons_frame' to 'scrollable_frame'
    canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    def patch_func_factory(current_btn, label, prog1, prog2, cc):  # Modified: added current_btn
        def patch_func():
            nonlocal last_press_time, last_selected_button, testing_toast_label
            now = time.time()
            if now - last_press_time < 1:
                return
            last_press_time = now

            if last_selected_button and last_selected_button != current_btn:  # Used current_btn
                last_selected_button.config(bg=BUTTON_BG)
            current_btn.config(bg=HIGHLIGHT_BG)  # Used current_btn
            last_selected_button = current_btn  # Used current_btn

            for b in all_buttons:
                b.config(state="disabled")

            # --- MIDI Commands preparation ---
            initial_commands = [
                ["ch", "2", "pc", "127"],
                ["ch", "1", "cc", "47", "2"],
                ["ch", "1", "pc", str(prog1)],
                ["ch", "2", "pc", str(prog2)]
            ]

            all_midi_commands = initial_commands + cc  # Combine all MIDI commands

            # --- Specific logic for "TEST 123" ---
            if label == "TEST 123":
                # Hide any existing testing toast
                if testing_toast_label and testing_toast_label.winfo_exists():
                    testing_toast_label.destroy()

                # Create the red "TESTING" toast
                testing_toast_label = tk.Label(root, text="TESTING", bg="red", fg="white", font=big_font)
                testing_toast_label.place(relx=0.5, rely=0.1, anchor="n")  # Slightly lower to avoid switch mode toast

                current_command_index = 0

                def _send_next_command():
                    nonlocal current_command_index
                    if current_command_index < len(all_midi_commands):
                        command = all_midi_commands[current_command_index]
                        send_midi([command])  # Send one command at a time
                        current_command_index += 1
                        if current_command_index < len(all_midi_commands):
                            root.after(500, _send_next_command)  # Schedule next command after 0.5s
                        else:
                            # All commands sent, re-enable buttons and destroy toast
                            root.after(0, lambda: [b.config(state="normal") for b in all_buttons])
                            if testing_toast_label and testing_toast_label.winfo_exists():
                                testing_toast_label.destroy()
                    else:
                        # Fallback for unexpected state, ensure buttons re-enable
                        root.after(0, lambda: [b.config(state="normal") for b in all_buttons])
                        if testing_toast_label and testing_toast_label.winfo_exists():
                            testing_toast_label.destroy()

                _send_next_command()  # Start the sequence
            else:
                # --- Normal patch execution ---
                send_midi(all_midi_commands)
                root.after(1000, lambda: [b.config(state="normal") for b in all_buttons])

        return patch_func

    # --- Refactored patch loading into a function ---
    def _load_and_display_patches():
        nonlocal last_selected_button  # Ensure we can reset this
        # Clear existing buttons
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        all_buttons.clear()  # Clear the list of buttons too
        last_selected_button = None  # Reset selected button state

        try:
            with open(CSV_FILE, "r", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile.read().splitlines())
                for row in reader:
                    if len(row) >= 3:
                        label = row[0].strip()
                        try:
                            prog1 = int(row[1].strip())
                            prog2 = int(row[2].strip())
                            cc_commands = []
                            cc_data = row[3:]
                            for i in range(0, len(cc_data), 3):
                                try:
                                    ch = int(cc_data[i].strip())
                                    cc = int(cc_data[i + 1].strip())
                                    val = int(cc_data[i + 2].strip())
                                    cc_commands.append(["ch", str(ch), "cc", str(cc), str(val)])
                                except (ValueError, IndexError):
                                    continue
                            btn = tk.Button(scrollable_frame, text=label, font=big_font, padx=20, pady=10,
                                            bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL,
                                            activeforeground=DARK_FG,
                                            bd=0)
                            btn.config(
                                command=patch_func_factory(btn, label, prog1, prog2, cc_commands))  # Modified: pass btn
                            btn.pack(pady=5, padx=10, fill="x")
                            all_buttons.append(btn)
                        except ValueError:
                            print(f"Skipping invalid row: {row}")
            # Ensure canvas updates its scrollregion after new buttons are packed
            canvas.config(scrollregion=canvas.bbox("all"))

        except FileNotFoundError:
            print(f"CSV file '{CSV_FILE}' not found.")
            show_toast(f"Error: CSV file '{CSV_FILE}' not found. Please ensure it exists.")

    # --- Initial load of patches when main app starts ---
    # Load previously used CSV from config, if available and exists
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}

    if "csv_file_used" in config and os.path.exists(config["csv_file_used"]):
        CSV_FILE = config["csv_file_used"]
    # Else, CSV_FILE remains at its default value (MidiList.csv) which should have been copied already
    # by choose_setlist if it ran.

    _load_and_display_patches()
    # --- End of initial load ---

    down_button_frame = tk.Frame(root, bg=DARK_BG)
    down_button_frame.pack(fill="x")

    def scroll_down():
        btn_down.config(relief="sunken")  # Simulate press
        canvas.yview_scroll(1, "units")
        root.after(150, lambda: btn_down.config(relief="raised"))  # Revert after short delay

    btn_down = tk.Button(down_button_frame, text="↓", font=("Arial", 36, "bold"), height=1,
                         command=scroll_down, bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL,
                         activeforeground=DARK_FG, relief="raised", bd=2)  # Added relief and bd
    btn_down.pack(fill="x")

    def monitor_midi_device():
        nonlocal MIDI_DEVICE, usb_stable_start_time, user_declined_usb_switch  # Use nonlocal for shared variables
        try:
            result = subprocess.run([SENDMIDI_PATH, "list"], capture_output=True, text=True)
            devices = result.stdout.strip().splitlines()

            # The key change: device presence is determined solely by their names appearing in the sendmidi.exe output.
            morningstar_present = ALT_DEVICE in devices
            quad_cortex_present = QUAD_CORTEX_DEVICE in devices

            # --- Failover Logic (from USB to BT) ---
            if MIDI_DEVICE == ALT_DEVICE:
                # Display general monitoring toast if actively using ALT_DEVICE
                show_toast("Monitoring Morningstar MC8 Pro and Quad Cortex MIDI Control...")

                # If either of the expected USB devices is not found in the sendmidi list
                if not (morningstar_present and quad_cortex_present):
                    # Reset decline flag as USB is now disconnected
                    user_declined_usb_switch = False
                    # Trigger failover to BT
                    popup = tk.Toplevel(root)
                    popup.title("USB Device Disconnected!")
                    popup.configure(bg=DARK_BG)

                    # Calculate position to center the popup over the main screen
                    popup_width = 700
                    popup_height = 400
                    screen_width = root.winfo_screenwidth()
                    screen_height = root.winfo_screenheight()
                    x_pos = (screen_width // 2) - (popup_width // 2)
                    y_pos = (screen_height // 2) - (popup_height // 2)
                    popup.geometry(f"{popup_width}x{popup_height}+{x_pos}+{y_pos}")

                    # Make it modal and transient
                    popup.grab_set()
                    popup.transient(root)

                    tk.Label(popup, text="USB Device failed!", font=("Arial", 24, "bold"),
                             bg=DARK_BG, fg="red").pack(pady=20)
                    tk.Label(popup,
                             text="Check MIDIberry settings. Defaulting to BLUETOOTH connection\n(power on rack WIDI jack first).",
                             font=("Arial", 14), bg=DARK_BG, fg=DARK_FG).pack(pady=10)

                    def on_ok_clicked():
                        popup.destroy()

                    ok_button = tk.Button(popup, text="OK", font=("Arial", 16),
                                          command=on_ok_clicked, bg=BUTTON_BG, fg=DARK_FG,
                                          activebackground=BUTTON_HL, activeforeground=DARK_FG,
                                          width=10, height=2)
                    ok_button.pack(pady=20)

                    # Block execution until the popup is closed
                    root.wait_window(popup)

                    # --- After popup is dismissed, proceed with re-launch ---
                    # Removed explicit setlist default, allowing it to load the last selected from config
                    save_config(device=DEFAULT_DEVICE, relaunch_on_monitor_fail=True)
                    new_env = os.environ.copy()
                    new_env["MIDI_DEVICE"] = DEFAULT_DEVICE

                    subprocess.Popen([sys.executable, SCRIPT_PATH], env=new_env)
                    root.destroy()  # Destroy current GUI instance
                    return  # Exit the monitoring function as we are re-launching

            # --- Failback Logic (from BT to USB) ---
            elif MIDI_DEVICE == DEFAULT_DEVICE:
                # If both expected USB devices are now present in the sendmidi list
                if morningstar_present and quad_cortex_present:
                    if usb_stable_start_time is None:
                        usb_stable_start_time = time.time()
                        show_toast("USB devices detected. Checking for stability...", duration=3000)
                    elif (time.time() - usb_stable_start_time) >= 10:
                        # USB stable for 10 seconds, trigger failback or toast
                        usb_stable_start_time = None  # Reset for next cycle

                        if user_declined_usb_switch:
                            # User previously declined, so just show a toast, don't show the popup
                            show_toast("Morningstar MC8 Pro and Quad Cortex MIDI control available...", duration=3000)
                        else:
                            # Create the Acknowledge popup
                            popup = tk.Toplevel(root)
                            popup.title("USB Devices Reconnected!")
                            popup.configure(bg=DARK_BG)

                            # Calculate position to center the popup over the main screen
                            popup_width = 700
                            popup_height = 400
                            screen_width = root.winfo_screenwidth()
                            screen_height = root.winfo_screenheight()
                            x_pos = (screen_width // 2) - (popup_width // 2)
                            y_pos = (screen_height // 2) - (popup_height // 2)
                            popup.geometry(f"{popup_width}x{popup_height}+{x_pos}+{y_pos}")

                            popup.grab_set()
                            popup.transient(root)

                            tk.Label(popup,
                                     text="Both Morningstar MC8 Pro and Quad Cortex MIDI Control\nhave reconnected via USB.",
                                     font=("Arial", 18, "bold"),
                                     bg=DARK_BG, fg="#2a8f44", justify="center").pack(pady=20)
                            tk.Label(popup, text="Do you want to switch back to USB mode?",
                                     font=("Arial", 14), bg=DARK_BG, fg=DARK_FG).pack(pady=10)

                            switch_to_usb_clicked = False  # Flag to track user choice

                            def on_acknowledge_clicked():
                                nonlocal switch_to_usb_clicked, user_declined_usb_switch
                                switch_to_usb_clicked = True
                                user_declined_usb_switch = False  # Reset if they acknowledge and switch
                                popup.destroy()

                            def on_decline_clicked():
                                nonlocal switch_to_usb_clicked, user_declined_usb_switch
                                switch_to_usb_clicked = False
                                user_declined_usb_switch = True  # Set the flag if user declines
                                popup.destroy()

                            btn_frame_popup = tk.Frame(popup, bg=DARK_BG)
                            btn_frame_popup.pack(pady=20)

                            ack_button = tk.Button(btn_frame_popup, text="Acknowledge & Switch to USB",
                                                   font=("Arial", 16),
                                                   command=on_acknowledge_clicked, bg="#2a8f44", fg="white",
                                                   activebackground="#207030", activeforeground="white",
                                                   width=30, height=2)
                            ack_button.pack(side="left", padx=10)

                            decline_button = tk.Button(btn_frame_popup, text="No, stay on Bluetooth",
                                                       font=("Arial", 16),
                                                       command=on_decline_clicked, bg="#b02f2f", fg="white",
                                                       activebackground="#902020", activeforeground="white",
                                                       width=30, height=2)
                            decline_button.pack(side="right", padx=10)

                            # Block execution until the popup is closed
                            root.wait_window(popup)

                            # Check user's choice after popup is closed
                            if switch_to_usb_clicked:
                                # Set relaunch_on_monitor_fail to True so the new instance skips initial prompts.
                                # Removed explicit setlist default, allowing it to load the last selected from config
                                save_config(device=ALT_DEVICE, relaunch_on_monitor_fail=True)
                                new_env = os.environ.copy()
                                new_env["MIDI_DEVICE"] = ALT_DEVICE  # Set to USB device
                                subprocess.Popen([sys.executable, SCRIPT_PATH], env=new_env)
                                root.destroy()  # Destroy current GUI instance
                                return  # Exit the monitoring function if popup was shown and user clicked acknowledge
                            else:
                                # User declined, stay on current device, do not re-launch
                                show_toast("Staying on Bluetooth mode.")
                                # The monitor function will reschedule itself at the end if not re-launched
                else:
                    # If devices are not present or stability is lost, reset the timer and decline flag
                    usb_stable_start_time = None
                    user_declined_usb_switch = False  # Reset if USB devices are no longer present

        except Exception as e:
            show_toast(f"Device check failed: {e}")
        # Always re-schedule the monitor function unless a re-launch occurred
        root.after(5000, monitor_midi_device)

    monitor_midi_device()  # Start the monitoring loop
    root.mainloop()


if __name__ == "__main__":
    choose_setlist()
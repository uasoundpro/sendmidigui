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
# USB_DIRECT_DEVICE is the name used internally by sendmidi for the MC8 (USB Direct)
USB_DIRECT_DEVICE = "Morningstar MC8 Pro" 
# HYBRID_DEVICE is the name used internally by sendmidi for the MC8 (Hybrid mode)
HYBRID_DEVICE = "Morningstar MC8 Pro" 
QUAD_CORTEX_DEVICE = "Quad Cortex MIDI Control"
SENDMIDI_PATH = "C:\\Tools\\sendmidi\\sendmidi.exe"
RECEIVEMIDI_PATH = "C:\\Tools\\receivemidi\\receivemidi.exe"
ICON_FILE = "sendmidi.ico"
SCRIPT_PATH = os.path.abspath(__file__)
CSV_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList.csv")
CONFIG_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), "config.json")
SETLIST_FOLDER = os.path.join(os.path.dirname(SCRIPT_PATH), "Setlist")
CSV_FILE_DEFAULT_SOURCE = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList-DEFAULT.csv")

# ================ DARK THEME COLORS ===============
DARK_BG = "#1e1e1e"
DARK_FG = "#ffffff"
BUTTON_BG = "#2d2d2d"
BUTTON_HL = "#3c3c3c"
DISABLED_BG = "#555555"
HIGHLIGHT_BG = "#5b82a7"
SCROLLBAR_COLOR = "#444444"

# --- STATUS COLORS FOR CHECKBOX ---
USB_AVAILABLE_COLOR = "#2a8f44" # Green
USB_UNAVAILABLE_COLOR = "#b02f2f" # Red
USB_AVAILABLE_ACTIVE_COLOR = "#207030" # Darker Green for click active
USB_UNAVAILABLE_ACTIVE_COLOR = "#902020" # Darker Red for click active
# --- END STATUS COLORS ---

big_font = ("Comic Sans MS", 20)
narrow_font_plain = ("Arial", 10)
narrow_font_small = ("Arial", 9)

# Declare labels as global variables so they can be consistently accessed
setlist_display_label = None
mode_label = None
usb_lock_checkbox = None # Added for global access in monitor_midi_device

# Global variable for receivemidi process
_receivemidi_process = None
_receivemidi_stdout_thread = None
_receivemidi_stderr_thread = None

# --- GLOBAL VARIABLE FOR HYBRID MODE REROUTING ---
# This will be updated by monitor_midi_device
_qc_midi_target_device = QUAD_CORTEX_DEVICE

# =================== GLOBAL CONFIG MANAGEMENT =====================
def save_config(device=None, csv_file_used=None, relaunch_on_monitor_fail=None, current_setlist_display_name=None, usb_lock_active=None, debug_enabled=None):
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
    if usb_lock_active is not None:
        config["usb_lock_active"] = usb_lock_active
    if debug_enabled is not None:
        config["debug_enabled"] = debug_enabled
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
        # Try reading with utf-8 first, then fall back to latin-1
        try:
            with open(setlist_path, "r", encoding="utf-8") as f:
                song_names = [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            with open(setlist_path, "r", encoding="latin-1") as f:
                song_names = [line.strip() for line in f if line.strip()]

        try:
            with open(base_csv_path, "r", encoding="utf-8") as f:
                all_rows = [row for row in csv.reader(f.read().splitlines()) if row]
        except UnicodeDecodeError:
            with open(base_csv_path, "r", encoding="latin-1") as f:
                all_rows = [row for row in csv.reader(f.read().splitlines()) if row]

        label_lookup = {row[0].strip(): row for row in all_rows}
        lower_keys = {k.lower(): k for k in label_lookup}

        pinned_top = ["MUTE", "DEFAULT (JCM800)", "DEFAULT (RVerb)"]
        all_requested = pinned_top + song_names + ["TEST 123"] # Always add test at bottom

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


# =================== MIDI RECEIVE PROCESS MANAGEMENT =====================
def _read_receivemidi_output(pipe, stream_name):
    """Reads output from a pipe and prints it to the console."""
    global _receivemidi_process
    while _receivemidi_process and _receivemidi_process.poll() is None:  # Continue as long as process is running
        line = pipe.readline()
        if line:
            print(f"[receivemidi {stream_name}]: {line.strip()}")
        else:
            # If pipe is empty and process is still running, wait a bit
            time.sleep(0.01)  # Small delay to prevent busy-waiting
    # After process has exited, read any remaining output
    for line in pipe.readlines():
        print(f"[receivemidi {stream_name}]: {line.strip()}")
    print(f"receivemidi {stream_name} reader thread finished.")


def kill_receivemidi():
    """Terminates the receivemidi process and its output threads if it's running."""
    global _receivemidi_process, _receivemidi_stdout_thread, _receivemidi_stderr_thread
    if _receivemidi_process and _receivemidi_process.poll() is None:  # Check if process is still running
        try:
            print("Attempting to terminate receivemidi process...")
            _receivemidi_process.terminate()  # Request termination
            _receivemidi_process.wait(timeout=2)  # Wait a bit for it to terminate
            print("receivemidi process terminated.")
        except Exception as e:
            print(f"Error terminating receivemidi process: {e}")

    _receivemidi_process = None  # Clear the process reference

    # Join the threads to ensure they finish gracefully
    if _receivemidi_stdout_thread and _receivemidi_stdout_thread.is_alive():
        _receivemidi_stdout_thread.join(timeout=1)
    if _receivemidi_stderr_thread and _receivemidi_stderr_thread.is_alive():
        _receivemidi_stderr_thread.join(timeout=1)

    _receivemidi_stdout_thread = None
    _receivemidi_stderr_thread = None
    print("receivemidi cleanup complete.")


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
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)),
                                                                      "units") if canvas.winfo_exists() else None)

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

        # Initialize display_name with a fallback (filename)
        display_name = os.path.basename(selected_setlist_path).replace(".txt", "")
        try:
            with open(selected_setlist_path, "r", encoding="utf-8") as f:
                first_line_content = f.readline().strip()
                if first_line_content:  # Only update if first line is not empty
                    display_name = first_line_content
        except Exception as e:
            print(f"Error reading first line of {selected_setlist_path}: {e}")

        if selected_setlist_path.endswith(".txt"):
            temp_csv = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList_Set.csv")
            create_ordered_setlist_csv(selected_setlist_path, CSV_FILE_DEFAULT_SOURCE, temp_csv)
            # CSV_FILE is not globally updated here, the main app reads the config
            current_setlist_name_for_display = display_name  # Use the determined display_name
        else:  # It's already a CSV (like MidiList-DEFAULT.csv)
            # CSV_FILE is not globally updated here, the main app reads the config
            current_setlist_name_for_display = "Default Songs"

        save_config(csv_file_used=temp_csv,
                    current_setlist_display_name=current_setlist_name_for_display)  # Save the new chosen CSV file and display name

        choose_device_and_launch()

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

    def select_device(mode):
        chooser.destroy()
        if mode == "BT":
            selected = DEFAULT_DEVICE
        elif mode == "HYBRID":
            selected = HYBRID_DEVICE 
        elif mode == "USB_DIRECT":
            selected = USB_DIRECT_DEVICE
        else: # Should not happen, fallback
            selected = DEFAULT_DEVICE
        
        # Debug state is already saved by toggle_debug_logging command
        os.environ["MIDI_DEVICE"] = selected
        os.environ["MODE_TYPE"] = mode # Pass the mode type
        launch_main_app()

    def timeout_default():
        # Only run timeout_default if the chooser window still exists
        if chooser.winfo_exists():
            chooser.destroy()
            # Debug state is already saved by toggle_debug_logging command
            os.environ["MIDI_DEVICE"] = DEFAULT_DEVICE
            os.environ["MODE_TYPE"] = "BT"
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

        # Determine the mode based on the device name
        mode_type = "UNKNOWN"
        actual_device_to_set = device_name

        if device_name == USB_DIRECT_DEVICE:
            mode_type = "USB_DIRECT"
        elif device_name == HYBRID_DEVICE:
            mode_type = "HYBRID"
        elif device_name == DEFAULT_DEVICE:
            mode_type = "BT"
        elif device_name == QUAD_CORTEX_DEVICE:
            # If QC is selected directly, treat it as USB Direct/MC8 as that's the intended path
            actual_device_to_set = USB_DIRECT_DEVICE
            mode_type = "USB_DIRECT"
        
        # If the user selects a custom device, we assume it's like Hybrid (no receivemidi)
        if mode_type == "UNKNOWN":
            mode_type = "CUSTOM_NO_RX"
        
        # Debug state is already saved by toggle_debug_logging command
        os.environ["MIDI_DEVICE"] = actual_device_to_set
        os.environ["MODE_TYPE"] = mode_type
        launch_main_app()

    chooser = tk.Tk()
    chooser.title("Select MIDI Device")
    chooser.configure(bg=DARK_BG)
    chooser.geometry("900x600+{}+{}".format( # Adjusted height for vertical stacking
        chooser.winfo_screenwidth() // 2 - 450,
        chooser.winfo_screenheight() // 2 - 175
    ))
    tk.Label(chooser, text="Select MIDI Device Mode:", bg=DARK_BG, fg=DARK_FG, font=big_font).pack(pady=10)

    btn_frame = tk.Frame(chooser, bg=DARK_BG)
    btn_frame.pack(pady=5)

    # --- Vertical Stacking of Device Buttons (Initial Chooser) ---
    btn_bt = tk.Button(btn_frame, text="BT (Default)", font=big_font, width=30, height=2,
                       command=lambda: select_device("BT"), bg="#2a8f44", fg="white")
    btn_bt.grid(row=0, column=0, pady=5, padx=5)

    btn_usb_direct = tk.Button(btn_frame, text="USB Direct\n(Uses receivemidi)", font=big_font, width=30, height=2,
                        command=lambda: select_device("USB_DIRECT"), bg="#b02f2f", fg="white")
    btn_usb_direct.grid(row=1, column=0, pady=5, padx=5)

    btn_hybrid = tk.Button(btn_frame, text="Hybrid\n(No receivemidi)", font=big_font, width=30, height=2,
                        command=lambda: select_device("HYBRID"), bg="#28578f", fg="white")
    btn_hybrid.grid(row=2, column=0, pady=5, padx=5)
    # --- END Vertical Stacking ---
    
    # --- NEW DEBUG TOGGLE LOGIC ---
    initial_debug_state = config.get("debug_enabled", False)
    debug_var = tk.BooleanVar(value=initial_debug_state)
    
    def toggle_debug_logging():
        # This saves the state immediately when the checkbox is clicked
        save_config(debug_enabled=debug_var.get())
        
    debug_checkbox = tk.Checkbutton(
        chooser,
        text="Enable MIDI Debug Logging (Prints commands to console)",
        variable=debug_var,
        command=toggle_debug_logging,
        bg=DARK_BG,
        fg=DARK_FG,
        selectcolor=DARK_BG, # Ensures background is dark even when checked
        activebackground=DARK_BG,
        activeforeground=DARK_FG,
        font=narrow_font_plain
    )
    debug_checkbox.pack(pady=(20, 10))
    # --- END NEW DEBUG TOGGLE LOGIC ---

    btn_list = tk.Button(chooser, text="List MIDI Devices", font=narrow_font_plain, command=list_devices,
                         bg="#444444", fg=DARK_FG, activebackground=BUTTON_HL, activeforeground=DARK_FG, bd=0, padx=6,
                         pady=6, height=2)
    btn_list.pack(pady=5)

    timer_label = tk.Label(chooser, text="", bg=DARK_BG, fg=DARK_FG, font=narrow_font_plain)
    timer_label.pack(pady=5)

    timer_count = [15]

    def countdown():
        # Only run countdown if the chooser window still exists
        if chooser.winfo_exists() and timer_count[0] > 0:
            timer_label.config(text=f"Defaulting to BT in {timer_count[0]}s")
            timer_count[0] -= 1
            chooser.after(1500, countdown)
        elif chooser.winfo_exists() and timer_count[0] == 0:
            timeout_default()

    countdown()
    chooser.mainloop()

# =================== LAUNCH MAIN GUI =====================
def launch_main_app():
    global CSV_FILE, setlist_display_label, mode_label, usb_lock_checkbox # Declare labels as global

    MIDI_DEVICE = os.environ.get("MIDI_DEVICE", DEFAULT_DEVICE)
    MODE_TYPE = os.environ.get("MODE_TYPE", "BT") # Retrieve the mode type

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
        kill_receivemidi()  # Ensure receivemidi is killed on app close
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
        
    # --- Set environment variable for debug state ---
    initial_debug_state = config.get("debug_enabled", False) 
    os.environ["MIDI_DEBUG_ENABLED"] = str(initial_debug_state) 
    # --- END ---

    current_setlist_name_for_display = config.get("current_setlist_display_name", "Unknown Setlist")

    # USB Lock Variable Initialization
    initial_usb_lock_state = config.get("usb_lock_active", False) # Default to False if not in config
    usb_lock_var = tk.BooleanVar(value=initial_usb_lock_state)

    last_press_time = 0
    last_selected_button = None
    all_buttons = []
    testing_toast_label = None
    usb_stable_start_time = None
    user_declined_usb_switch = False
    _usb_disconnect_warning_shown = False # State for intermittent USB disconnect toast

    # Instance variables for managing single popup windows from the main GUI
    setlist_popup_window_instance = None
    list_devices_popup_window_instance = None
    device_change_popup_instance = None 
    device_switch_popup_instance = None

    def show_toast(msg, duration=2000, bg="#303030", fg="white"):
        # Destroy any existing general toast
        for widget in root.winfo_children():
            # Heuristic to identify toast (small label near the top)
            if isinstance(widget, tk.Label) and widget.winfo_y() < 50 and widget != testing_toast_label: 
                widget.destroy()

        toast = tk.Label(root, text=msg, bg=bg, fg=fg, font=narrow_font_small)
        toast.place(relx=0.5, rely=0.01, anchor="n")
        root.after(duration, toast.destroy)

    def send_midi(command_list):
        # Access the global routing variable
        global _qc_midi_target_device
        
        for command in command_list:
            # Determine the target device for the current command
            target_device = MIDI_DEVICE  # Default target is the globally selected MIDI_DEVICE

            # Specific routing applies only when targeting the MC8 (USB Direct or Hybrid)
            if MIDI_DEVICE == USB_DIRECT_DEVICE or MIDI_DEVICE == HYBRID_DEVICE:
                # Check if the command is a channel message (starts with "ch")
                if len(command) > 1 and command[0] == "ch":
                    channel_str = command[1]  # The channel number as a string
                    if channel_str == "2":
                        # Channel 2 messages should always go to the MC8 itself (which is MIDI_DEVICE)
                        target_device = MIDI_DEVICE
                    elif channel_str == "1":
                        # Channel 1 messages should go to the determined QC target device
                        target_device = _qc_midi_target_device # Use the global target
                # If it's not a "ch" command, it defaults to the main MIDI_DEVICE (MC8)

            # Construct and run the subprocess command with the determined target_device
            full_cmd = [SENDMIDI_PATH, "dev", target_device]
            # Ensure each element in the command is a string
            full_cmd.extend([str(arg) for arg in command])
            
            # 💡 DEBUGGING LINE: Conditional based on environment variable set at launch
            if os.environ.get("MIDI_DEBUG_ENABLED") == "True":
                print(f"[MIDI DEBUG] Executing: {' '.join(full_cmd)}")
            
            subprocess.run(full_cmd)

    # Helper function to launch receivemidi
    def _launch_receivemidi_if_usb_direct():
        """Helper function to launch receivemidi only if in USB_DIRECT mode."""
        # Only launch if the mode is explicitly set to USB_DIRECT
        if MODE_TYPE == "USB_DIRECT":
            global _receivemidi_process, _receivemidi_stdout_thread, _receivemidi_stderr_thread
            try:
                # Command: receivemidi dev "Morningstar MC8 Pro" pass "Quad Cortex MIDI Control"
                receivemidi_cmd = [
                    RECEIVEMIDI_PATH,
                    "dev", "Morningstar MC8 Pro",
                    "pass", "Quad Cortex MIDI Control"
                ]
                print(f"Launching receivemidi: {' '.join(receivemidi_cmd)}")
                _receivemidi_process = subprocess.Popen(receivemidi_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                        text=True)

                # Start threads to read stdout and stderr
                _receivemidi_stdout_thread = threading.Thread(target=_read_receivemidi_output,
                                                              args=(_receivemidi_process.stdout, "stdout"))
                _receivemidi_stderr_thread = threading.Thread(target=_read_receivemidi_output,
                                                              args=(_receivemidi_process.stderr, "stderr"))
                _receivemidi_stdout_thread.daemon = True
                _receivemidi_stderr_thread.daemon = True
                _receivemidi_stdout_thread.start()
                _receivemidi_stderr_thread.start()

                print(f"receivemidi process started with PID: {_receivemidi_process.pid}")
            except FileNotFoundError:
                show_toast(f"Error: {RECEIVEMIDI_PATH} not found. Please check the path.", bg="red", duration=5000)
            except Exception as e:
                show_toast(f"Error launching receivemidi: {e}", bg="red", duration=5000)

    # --- New functions for setlist selection from main GUI ---
    def show_setlist_selection_popup():
        nonlocal setlist_popup_window_instance

        if setlist_popup_window_instance and setlist_popup_window_instance.winfo_exists():
            setlist_popup_window_instance.lift()
            return

        setlist_popup = tk.Toplevel(root)
        setlist_popup_window_instance = setlist_popup

        def on_setlist_popup_close():
            nonlocal setlist_popup_window_instance
            setlist_popup_window_instance = None
            setlist_popup.destroy()

        setlist_popup.protocol("WM_DELETE_WINDOW", on_setlist_popup_close)

        setlist_popup.title("Select Setlist File")
        setlist_popup.configure(bg=DARK_BG)
        setlist_popup.geometry("600x600+200+100")

        tk.Label(setlist_popup, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=DARK_BG, fg=DARK_FG).pack(
            pady=20)

        files_frame = tk.Frame(setlist_popup, bg=DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas_popup = tk.Canvas(files_frame, bg=DARK_BG, highlightthickness=0)
        canvas_popup.pack(side="left", fill="both", expand=True)

        scrollbar_popup = tk.Scrollbar(files_frame, orient="vertical", command=canvas_popup.yview,
                                       bg=SCROLLBAR_COLOR, troughcolor=DARK_BG, highlightbackground=DARK_BG)
        scrollbar_popup.pack(side="right", fill="y")

        canvas_popup.configure(yscrollcommand=scrollbar_popup.set)
        scrollable_buttons_frame_popup = tk.Frame(canvas_popup, bg=DARK_BG)
        canvas_frame_popup = canvas_popup.create_window((0, 0), window=scrollable_buttons_frame_popup, anchor="nw")

        scrollable_buttons_frame_popup.bind("<Configure>",
                                            lambda e: canvas_popup.configure(scrollregion=canvas_popup.bbox("all")))
        canvas_popup.bind("<Configure>", lambda e: canvas_popup.itemconfig(canvas_frame_popup, width=e.width))
        canvas_popup.bind_all("<MouseWheel>", lambda e: canvas_popup.yview_scroll(int(-1 * (e.delta / 120)),
                                                                                  "units") if canvas_popup.winfo_exists() else None)

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


        setlist_popup.mainloop()

    def _process_selected_setlist_from_main_gui(selected_setlist_path, current_popup_window):
        global CSV_FILE, setlist_display_label
        nonlocal current_setlist_name_for_display
        nonlocal setlist_popup_window_instance

        current_popup_window.destroy()
        setlist_popup_window_instance = None

        temp_csv = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList_Set.csv")

        if selected_setlist_path.endswith(".txt"):
            create_ordered_setlist_csv(selected_setlist_path, CSV_FILE_DEFAULT_SOURCE, temp_csv)
            CSV_FILE = temp_csv

            display_name = os.path.basename(selected_setlist_path).replace(".txt", "")
            try:
                with open(selected_setlist_path, "r", encoding="utf-8") as f:
                    first_line_content = f.readline().strip()
                    if first_line_content:
                        display_name = first_line_content
            except Exception as e:
                print(f"Error reading first line of {selected_setlist_path}: {e}")

            current_setlist_name_for_display = display_name
        else:
            # If default is selected, use the default source path directly
            shutil.copyfile(selected_setlist_path, os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList.csv"))
            CSV_FILE = os.path.join(os.path.dirname(SCRIPT_PATH), "MidiList.csv")
            current_setlist_name_for_display = "Default Songs"

        save_config(csv_file_used=CSV_FILE,
                    current_setlist_display_name=current_setlist_name_for_display)

        if setlist_display_label and setlist_display_label.winfo_exists():
            setlist_display_label.config(text=f"Setlist: {current_setlist_name_for_display}")

        kill_receivemidi()
        _load_and_display_patches()
        show_toast(f"Setlist loaded: {current_setlist_name_for_display}")

    # --- End of new setlist functions ---

    def _set_device_mode(new_mode_type, new_device, should_relaunch=False):
        nonlocal MIDI_DEVICE, MODE_TYPE, user_declined_usb_switch, _usb_disconnect_warning_shown # Added: _usb_disconnect_warning_shown
        global mode_label, _qc_midi_target_device # Access global mode_label and _qc_midi_target_device

        # 1. Update globals and config
        kill_receivemidi()
        save_config(device=new_device)
        
        # 2. Update runtime variables
        os.environ["MIDI_DEVICE"] = new_device
        os.environ["MODE_TYPE"] = new_mode_type
        MIDI_DEVICE = new_device
        MODE_TYPE = new_mode_type
        
        # Reset the QC target device on mode switch. Monitor will update it shortly.
        _qc_midi_target_device = QUAD_CORTEX_DEVICE
        
        # Update the status label on the main GUI (REMOVED MIDI_DEVICE tag)
        if mode_label and mode_label.winfo_exists():
             mode_label.config(text=f"Current Mode: {MODE_TYPE}")

        # Reset decline flag if switching to a USB mode
        if MODE_TYPE == "USB_DIRECT" or MODE_TYPE == "HYBRID":
            user_declined_usb_switch = False
            _usb_disconnect_warning_shown = False # Reset on mode switch to allow warning if it fails again
            
        # 3. Handle re-launch if requested (used for monitor fail/failback)
        if should_relaunch:
            save_config(relaunch_on_monitor_fail=True)
            new_env = os.environ.copy()
            # Preserve the MIDI_DEBUG_ENABLED state in the new environment
            new_env["MIDI_DEBUG_ENABLED"] = os.environ.get("MIDI_DEBUG_ENABLED", "False") 
            subprocess.Popen([sys.executable, SCRIPT_PATH], env=new_env)
            root.destroy()
            return

        # 4. Handle receivemidi for the current instance (only launch for USB_DIRECT)
        _launch_receivemidi_if_usb_direct()
        show_toast(f"Switched to {MODE_TYPE} mode: {MIDI_DEVICE}")

    def show_device_switch_popup():
        nonlocal device_switch_popup_instance

        if device_switch_popup_instance and device_switch_popup_instance.winfo_exists():
            device_switch_popup_instance.lift()
            return
        
        popup = tk.Toplevel(root)
        device_switch_popup_instance = popup

        def on_switch_popup_close():
            nonlocal device_switch_popup_instance
            device_switch_popup_instance = None
            popup.destroy()

        popup.protocol("WM_DELETE_WINDOW", on_switch_popup_close)
        popup.title("Select MIDI Device Mode")
        popup.configure(bg=DARK_BG)
        popup.geometry("900x550+{}+{}".format( # Adjusted height for vertical stacking
            popup.winfo_screenwidth() // 2 - 450,
            popup.winfo_screenheight() // 2 - 175
        ))

        tk.Label(popup, text="Select New MIDI Device Mode:", bg=DARK_BG, fg=DARK_FG, font=big_font).pack(pady=10)

        btn_frame = tk.Frame(popup, bg=DARK_BG)
        btn_frame.pack(pady=20)

        def switch_and_close(mode, device, current_popup):
            _set_device_mode(mode, device)
            current_popup.destroy()

        # --- Vertical Stacking of Device Buttons (Switch Popup) ---
        btn_bt = tk.Button(btn_frame, text="BT (Default)", font=big_font, width=30, height=2,
                        command=lambda: switch_and_close("BT", DEFAULT_DEVICE, popup), bg="#2a8f44", fg="white")
        btn_bt.pack(pady=5)

        btn_usb_direct = tk.Button(btn_frame, text="USB Direct\n(Uses receivemidi)", font=big_font, width=30, height=2,
                            command=lambda: switch_and_close("USB_DIRECT", USB_DIRECT_DEVICE, popup), bg="#b02f2f", fg="white")
        btn_usb_direct.pack(pady=5)

        btn_hybrid = tk.Button(btn_frame, text="Hybrid\n(No receivemidi)", font=big_font, width=30, height=2,
                            command=lambda: switch_and_close("HYBRID", HYBRID_DEVICE, popup), bg="#28578f", fg="white")
        btn_hybrid.pack(pady=5)
        # --- END Vertical Stacking ---

    def list_devices():
        nonlocal list_devices_popup_window_instance

        if list_devices_popup_window_instance and list_devices_popup_window_instance.winfo_exists():
            list_devices_popup_window_instance.lift()
            return

        try:
            result = subprocess.run([SENDMIDI_PATH, "list"], capture_output=True, text=True)
            device_list = result.stdout.strip().splitlines()
        except Exception as e:
            print(f"Error listing devices: {e}")
            show_toast(f"Error listing devices: {e}")
            return

        if not device_list:
            show_toast("No MIDI devices found.")
            return

        list_window = tk.Toplevel(root)
        list_devices_popup_window_instance = list_window

        def on_list_devices_popup_close():
            nonlocal list_devices_popup_window_instance
            list_devices_popup_window_instance = None
            list_window.destroy()

        list_window.protocol("WM_DELETE_WINDOW", on_list_devices_popup_close)

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

        def select_new_device_from_list(device_name, window):
            nonlocal list_devices_popup_window_instance

            window.destroy()
            list_devices_popup_window_instance = None

            # Determine the mode based on the device name
            mode_type = "UNKNOWN"
            actual_device_to_set = device_name

            if device_name == USB_DIRECT_DEVICE:
                mode_type = "USB_DIRECT"
            elif device_name == HYBRID_DEVICE:
                mode_type = "HYBRID"
            elif device_name == DEFAULT_DEVICE:
                mode_type = "BT"
            elif device_name == QUAD_CORTEX_DEVICE:
                actual_device_to_set = USB_DIRECT_DEVICE
                mode_type = "USB_DIRECT"
            
            if mode_type == "UNKNOWN":
                mode_type = "CUSTOM_NO_RX"

            # Update the device mode without re-launching the whole app
            _set_device_mode(mode_type, actual_device_to_set, should_relaunch=False)

        for dev in active_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=BUTTON_BG, fg=DARK_FG,
                activebackground=BUTTON_HL, activeforeground=DARK_FG,
                command=(lambda d=dev: select_new_device_from_list(d, list_window))
            )
            btn.pack(pady=5)

        for dev in disabled_devices:
            btn = tk.Button(
                list_window, text=dev, font=narrow_font_plain, width=40, pady=10,
                bg=DISABLED_BG, fg="#999999",
                activebackground=DISABLED_BG, activeforeground="#999999",
                state="disabled"
            )
            btn.pack(pady=5)
    
    # --- GUI LAYOUT REVISION ---

    # 1. Status Frame (Device Monitor - TOP)
    status_frame = tk.Frame(root, bg=DARK_BG)
    status_frame.pack(fill="x", pady=2, padx=2)

    # REMOVED MIDI_DEVICE tag
    mode_label = tk.Label(status_frame, text=f"Current Mode: {MODE_TYPE}", fg=DARK_FG, bg=DARK_BG, font=("Arial", 12, "bold"))
    mode_label.pack(side="left", padx=4)

    # 2. Setlist Name Display Frame (Below Status)
    setlist_display_frame = tk.Frame(root, bg=DARK_BG)
    setlist_display_frame.pack(fill="x", pady=5)

    setlist_display_label = tk.Label(setlist_display_frame, text=f"Setlist: {current_setlist_name_for_display}",
                                     fg=DARK_FG, bg=DARK_BG, font=narrow_font_plain)
    setlist_display_label.pack(side="left", padx=5)

    # 3. Controls Frame (Buttons)
    controls_frame = tk.Frame(root, bg=DARK_BG)
    controls_frame.pack(fill="x", pady=5)

    # Device Switch Button
    switch_btn = tk.Button(controls_frame, text="Switch Mode", font=narrow_font_plain, command=show_device_switch_popup,
                           bg="#b02f2f", fg=DARK_FG, activebackground="#902020", activeforeground=DARK_FG, bd=0, padx=6,
                           pady=6, height=2)
    switch_btn.pack(side="left", padx=(5, 0))

    # List Devices Button
    list_btn = tk.Button(controls_frame, text="List MIDI Devices", font=narrow_font_plain,
                         command=list_devices, bg="#444444", fg=DARK_FG, activebackground=BUTTON_HL,
                         activeforeground=DARK_FG, bd=0, padx=6, pady=6, height=2)
    list_btn.pack(side="left", padx=(5, 0))

    # Choose Setlist Button
    choose_setlist_btn = tk.Button(controls_frame, text="Choose Setlist", font=narrow_font_plain,
                                   command=show_setlist_selection_popup, bg="#444444", fg=DARK_FG,
                                   activebackground=BUTTON_HL,
                                   activeforeground=DARK_FG, bd=0, padx=6, pady=6, height=2)
    choose_setlist_btn.pack(side="left", padx=(5, 0))

    # USB Lock Checkbox (New Position)
    usb_lock_checkbox = tk.Checkbutton(
        controls_frame, 
        text="Lock USB/Autoswitch", 
        variable=usb_lock_var, 
        command=lambda: save_config(usb_lock_active=usb_lock_var.get()),
        bg=DARK_BG, 
        fg=DARK_FG,
        selectcolor=DARK_BG, 
        activebackground=DARK_BG,
        activeforeground=DARK_FG,
        font=narrow_font_plain,
        relief="raised", 
        bd=2 
    )
    usb_lock_checkbox.pack(side="left", padx=(5, 0))

    # --- End GUI LAYOUT REVISION ---


    up_button_frame = tk.Frame(root, bg=DARK_BG)
    up_button_frame.pack(fill="x")

    def scroll_up():
        btn_up.config(relief="sunken")
        canvas.yview_scroll(-1, "units")
        root.after(150, lambda: btn_up.config(relief="raised"))

    btn_up = tk.Button(up_button_frame, text="↑", font=("Arial", 36, "bold"), height=1,
                       command=scroll_up, bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL,
                       activeforeground=DARK_FG, relief="raised", bd=2)
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
    canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))


    def patch_func_factory(current_btn, label, prog1, prog2, cc):
        def patch_func():
            nonlocal last_press_time, last_selected_button, testing_toast_label
            now = time.time()
            if now - last_press_time < 1:
                return
            last_press_time = now

            if last_selected_button and last_selected_button != current_btn:
                last_selected_button.config(bg=BUTTON_BG)
            current_btn.config(bg=HIGHLIGHT_BG)
            last_selected_button = current_btn

            for b in all_buttons:
                b.config(state="disabled")

            # Kill any existing receivemidi process BEFORE starting new sequence
            kill_receivemidi()

            all_commands_for_this_patch = [
                                              ["ch", "2", "pc", "127"],
                                              ["ch", "1", "cc", "47", "2"],
                                              ["ch", "1", "pc", str(prog1)],
                                              ["ch", "2", "pc", str(prog2)]
                                          ] + cc

            commands_ch1_before_receivemidi = []
            commands_after_receivemidi_start = []

            # Only special routing when targeting MC8 (USB Direct or Hybrid)
            if MIDI_DEVICE == USB_DIRECT_DEVICE or MIDI_DEVICE == HYBRID_DEVICE:
                for cmd in all_commands_for_this_patch:
                    # A command goes into commands_ch1_before_receivemidi if it's a channel 1 command 
                    # AND we are in USB_DIRECT mode (where Quad Cortex is the target) and it's a PC command
                    if MODE_TYPE == "USB_DIRECT" and len(cmd) > 1 and cmd[0] == "ch" and cmd[1] == "1" and cmd[2] == "pc":
                        commands_ch1_before_receivemidi.append(cmd)
                    else:
                        commands_after_receivemidi_start.append(cmd)
            else:
                # If not using the MC8, all commands can be sent immediately as there's no complex routing
                commands_after_receivemidi_start = all_commands_for_this_patch

            if label == "TEST 123" and ["ch", "1", "pc", "126"] not in commands_ch1_before_receivemidi and MODE_TYPE != "BT":
                commands_ch1_before_receivemidi.insert(0, ["ch", "1", "pc", "126"])

            # --- Function to run in a separate thread for MIDI sending and delays ---
            def _send_patch_commands_in_thread():
                # 1. Send commands that must go to Channel 1 (QC) BEFORE receivemidi starts (only relevant for USB_DIRECT).
                for cmd in commands_ch1_before_receivemidi:
                    send_midi([cmd])
                if commands_ch1_before_receivemidi:
                    time.sleep(0.05)

                # 2. Launch receivemidi ONLY if in USB_DIRECT mode.
                _launch_receivemidi_if_usb_direct() # This function internally checks for MODE_TYPE == "USB_DIRECT"

                # 3. Add 1-second delay after potential receivemidi launches
                time.sleep(1)

                # 4. Send the remaining commands
                if label == "TEST 123":
                    def create_and_place_toast():
                        nonlocal testing_toast_label
                        if testing_toast_label and testing_toast_label.winfo_exists():
                            testing_toast_label.destroy()
                        testing_toast_label = tk.Label(root, text="TESTING", bg="red", fg="white", font=big_font)
                        testing_toast_label.place(relx=0.5, rely=0.1, anchor="n")

                    root.after(0, create_and_place_toast)

                    for i, command in enumerate(commands_after_receivemidi_start):
                        send_midi([command])
                        if i < len(commands_after_receivemidi_start) - 1:
                            time.sleep(0.25)

                    root.after(0, lambda: [b.config(state="normal") for b in all_buttons])
                    root.after(0,
                               lambda: testing_toast_label.destroy() if testing_toast_label and testing_toast_label.winfo_exists() else None)

                else:
                    for i, command in enumerate(commands_after_receivemidi_start):
                        send_midi([command])
                        if i < len(commands_after_receivemidi_start) - 1:
                            time.sleep(0.25)
                    root.after(0, lambda: [b.config(state="normal") for b in all_buttons])

            midi_send_thread = threading.Thread(target=_send_patch_commands_in_thread)
            midi_send_thread.daemon = True
            midi_send_thread.start()

        return patch_func

    # --- Refactored patch loading into a function ---
    def _load_and_display_patches():
        nonlocal last_selected_button
        # Clear existing buttons
        for widget in scrollable_frame.winfo_children():
            widget.destroy()
        all_buttons.clear()
        last_selected_button = None

        try:
            try:
                with open(CSV_FILE, "r", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile.read().splitlines())
            except UnicodeDecodeError:
                with open(CSV_FILE, "r", encoding="latin-1") as csvfile:
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

                        btn.config(command=patch_func_factory(btn, label, prog1, prog2, cc_commands))


                        btn.pack(pady=5, padx=10, fill="x")
                        all_buttons.append(btn)
                    except ValueError:
                        print(f"Skipping invalid row: {row}")
            canvas.config(scrollregion=canvas.bbox("all"))

        except FileNotFoundError:
            print(f"CSV file '{CSV_FILE}' not found.")
            show_toast(f"Error: CSV file '{CSV_FILE}' not found. Please ensure it exists.")

    # --- Initial load of patches when main app starts ---
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}

    if "csv_file_used" in config and os.path.exists(config["csv_file_used"]):
        CSV_FILE = config["csv_file_used"]

    _load_and_display_patches()
    
    # Initial launch of receivemidi if in USB_DIRECT mode, when the main app starts
    _launch_receivemidi_if_usb_direct()
    # --- End of initial load ---

    down_button_frame = tk.Frame(root, bg=DARK_BG)
    down_button_frame.pack(fill="x")

    def scroll_down():
        btn_down.config(relief="sunken")
        canvas.yview_scroll(1, "units")
        root.after(150, lambda: btn_down.config(relief="raised"))

    btn_down = tk.Button(down_button_frame, text="↓", font=("Arial", 36, "bold"), height=1,
                         command=scroll_down, bg=BUTTON_BG, fg=DARK_FG, activebackground=BUTTON_HL,
                         activeforeground=DARK_FG, relief="raised", bd=2)
    btn_down.pack(fill="x")

    def _create_device_popup(title, message, ack_text, decline_text, is_failback):
        nonlocal device_change_popup_instance, user_declined_usb_switch
        
        # Prevent multiple popups
        if device_change_popup_instance and device_change_popup_instance.winfo_exists():
            return
        
        popup = tk.Toplevel(root)
        popup.title(title)
        popup.configure(bg=DARK_BG)
        
        popup_width = 800
        popup_height = 400
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x_pos = (screen_width // 2) - (popup_width // 2)
        y_pos = (screen_height // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{x_pos}+{y_pos}")

        popup.grab_set()
        popup.transient(root)
        device_change_popup_instance = popup

        tk.Label(popup, text=title.replace("!", ""), font=("Arial", 24, "bold"),
                 bg=DARK_BG, fg=("red" if not is_failback else "#2a8f44")).pack(pady=20)
        tk.Label(popup, text=message, font=("Arial", 14), bg=DARK_BG, fg=DARK_FG, justify="center").pack(pady=10)

        switch_choice = [None] # Use a list to pass choice back from internal functions

        def on_ack_clicked():
            switch_choice[0] = True
            if is_failback:
                user_declined_usb_switch = False
            popup.destroy()

        def on_decline_clicked():
            switch_choice[0] = False
            if is_failback:
                user_declined_usb_switch = True
            popup.destroy()
            
        btn_frame_popup = tk.Frame(popup, bg=DARK_BG)
        btn_frame_popup.pack(pady=20)
        
        ack_button = tk.Button(btn_frame_popup, text=ack_text, font=("Arial", 16),
                               command=on_ack_clicked, bg=("#b02f2f" if not is_failback else "#2a8f44"), 
                               fg="white", activebackground=("#902020" if not is_failback else "#207030"), 
                               activeforeground="white", width=30, height=2)
        ack_button.pack(side="left", padx=10)
        
        if decline_text:
            decline_button = tk.Button(btn_frame_popup, text=decline_text, font=("Arial", 16),
                                       command=on_decline_clicked, bg=("#28578f" if is_failback else "#444444"), 
                                       fg="white", activebackground=BUTTON_HL, activeforeground="white",
                                       width=30, height=2)
            decline_button.pack(side="right", padx=10)


        # Block execution until the popup is closed
        root.wait_window(popup)
        device_change_popup_instance = None # Reset instance
        return switch_choice[0]

    def monitor_midi_device(): # Removed usb_lock_checkbox from args, accessing it as global
        nonlocal MIDI_DEVICE, MODE_TYPE, usb_stable_start_time, user_declined_usb_switch, _usb_disconnect_warning_shown
        global mode_label, usb_lock_checkbox, _qc_midi_target_device # Access global routing variable

        try:
            result = subprocess.run([SENDMIDI_PATH, "list"], capture_output=True, text=True)
            devices = result.stdout.strip().splitlines()

            morningstar_present = USB_DIRECT_DEVICE in devices or HYBRID_DEVICE in devices
            quad_cortex_present = QUAD_CORTEX_DEVICE in devices
            
            # Simplified check for USB availability: both critical devices must be visible for a "Full USB" state
            usb_devices_present = morningstar_present and quad_cortex_present
            
            # --- HYBRID MODE REROUTING LOGIC ---
            if MODE_TYPE == "HYBRID":
                if not quad_cortex_present:
                    # QC is missing, REROUTE QC messages (Ch 1) to MC8 (Hybrid Device)
                    _qc_midi_target_device = HYBRID_DEVICE 
                    # Use a slightly modified text for the status label
                    mode_label_text = f"Current Mode: {MODE_TYPE} (QC REROUTED to MC8)"
                else:
                    # QC is present, send QC messages (Ch 1) directly to QC device
                    _qc_midi_target_device = QUAD_CORTEX_DEVICE
                    mode_label_text = f"Current Mode: {MODE_TYPE} (QC DIRECT)"
            else:
                # All other modes, QC target is direct
                _qc_midi_target_device = QUAD_CORTEX_DEVICE
                mode_label_text = f"Current Mode: {MODE_TYPE}"
            # --- END HYBRID MODE REROUTING LOGIC ---
            
            # --- STATUS LABEL AND CHECKBOX COLORING LOGIC ---
            if mode_label and mode_label.winfo_exists() and usb_lock_checkbox and usb_lock_checkbox.winfo_exists():
                
                # REVISED: Use mode_label_text for status text
                if MODE_TYPE == "USB_DIRECT" or MODE_TYPE == "HYBRID":
                    if not usb_devices_present:
                        # USB Mode, Disconnected: RED status and checkbox
                        mode_label.config(text=f"{mode_label_text}", fg="red")
                        usb_lock_checkbox.config(bg=USB_UNAVAILABLE_COLOR, activebackground=USB_UNAVAILABLE_ACTIVE_COLOR)
                    else:
                        # USB Mode, Connected: GREEN status and checkbox
                        mode_label.config(text=f"{mode_label_text}", fg=USB_AVAILABLE_COLOR) 
                        usb_lock_checkbox.config(bg=USB_AVAILABLE_COLOR, activebackground=USB_AVAILABLE_ACTIVE_COLOR) 
                
                elif MODE_TYPE == "BT":
                    if usb_devices_present:
                        # BT Mode, USB Available: GREEN status and checkbox
                        mode_label.config(text=f"{mode_label_text} (USB AVAILABLE)", fg=USB_AVAILABLE_COLOR)
                        usb_lock_checkbox.config(bg=USB_AVAILABLE_COLOR, activebackground=USB_AVAILABLE_ACTIVE_COLOR)
                    else:
                        # BT Mode, USB Unavailable: Default status and checkbox
                        mode_label.config(text=f"{mode_label_text}", fg=DARK_FG)
                        usb_lock_checkbox.config(bg=DARK_BG, activebackground=DARK_BG)
            
            # --- END STATUS LABEL AND CHECKBOX COLORING LOGIC ---

            # --- Failover Logic (from USB Direct/Hybrid to BT) ---
            if MODE_TYPE == "USB_DIRECT" or MODE_TYPE == "HYBRID":
                if not usb_devices_present:
                    
                    if usb_lock_var.get():
                        # LOCK IS ACTIVE: Prevent forced switch to BT.
                        # LOGIC ADDED: Only show toast if the warning hasn't been shown yet
                        if not _usb_disconnect_warning_shown:
                            show_toast(f"USB disconnected! Switch to BT prevented by lock.", bg="red", duration=5000)
                            _usb_disconnect_warning_shown = True # Set flag after showing
                        # No 'return' here, so monitoring will reschedule at the end.
                        
                    else:
                        # LOCK IS INACTIVE: Proceed with switch to BT
                        user_declined_usb_switch = False
                        _usb_disconnect_warning_shown = False # RESET FLAG before switching
                        kill_receivemidi()

                        message = "USB Device failed! Check MIDIberry settings. Defaulting to BLUETOOTH connection\n(power on rack WIDI jack first)."
                        _create_device_popup("USB Device Disconnected!", message, "OK", None, False)

                        # --- After popup is dismissed, proceed with re-launch ---
                        _set_device_mode("BT", DEFAULT_DEVICE, should_relaunch=True)
                        return # Exit function as a new instance is launched

                else:
                    # USB devices ARE present while in USB_DIRECT/HYBRID mode
                    _usb_disconnect_warning_shown = False # RESET FLAG when USB is reconnected

            # --- Failback Logic (from BT to USB Direct) ---
            elif MODE_TYPE == "BT":
                if usb_devices_present:
                    if usb_stable_start_time is None:
                        usb_stable_start_time = time.time()
                        show_toast("USB devices detected. Checking for stability...", duration=3000)
                    elif (time.time() - usb_stable_start_time) >= 10:
                        usb_stable_start_time = None

                        if usb_lock_var.get() or user_declined_usb_switch:
                            show_toast("USB devices available, but switch declined/locked.")
                        else:
                            message = "Both Morningstar MC8 Pro and Quad Cortex MIDI Control\nhave reconnected via USB. Do you want to switch back to USB Direct mode?"
                            choice = _create_device_popup("USB Devices Reconnected!", message, 
                                                           "Acknowledge & Switch to USB Direct", "No, stay on Bluetooth", True)

                            if choice == True:
                                # Switch to USB Direct, which uses receivemidi
                                _set_device_mode("USB_DIRECT", USB_DIRECT_DEVICE, should_relaunch=True)
                                return
                            # If choice is False, user_declined_usb_switch is set to True inside the popup logic

                else:
                    # If devices are not present, reset the timer and decline flag
                    usb_stable_start_time = None
                    user_declined_usb_switch = False

        except Exception as e:
            show_toast(f"Device check failed: {e}")
            
        # Always re-schedule the monitor function unless a re-launch occurred
        root.after(5000, monitor_midi_device)

    monitor_midi_device()
    root.mainloop()


if __name__ == "__main__":
    choose_setlist()
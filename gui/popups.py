import tkinter as tk
import os
import shutil
import subprocess
import config
import utils
import time
import sys
import traceback

# --- !! DEBUG LOGGING !! ---
try:
    POPUP_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = os.path.abspath(os.path.join(POPUP_SCRIPT_DIR, ".."))
    LOG_FILE_PATH = os.path.join(BASE_DIR, "debug_log.txt")
except Exception as e:
    print(f"FATAL: gui/popups.py cannot find log file path. {e}")

def write_log(message):
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            f.write(f"[{timestamp}] [gui.popups] {message}\n")
    except Exception as e:
        print(f"POPUP LOG FAIL: {e}. Message: {message}")
# --- !! END DEBUG LOGGING !! ---


# --- SETLIST CHOOSER (Top Level) ---

def show_setlist_chooser(root):
    write_log("show_setlist_chooser() called.")
    try:
        conf = config.load_config()
        write_log("Config loaded.")

        if conf.get("relaunch_on_monitor_fail"):
            write_log("Relaunch on fail detected. Skipping setlist prompt.")
            return
        write_log("Not a relaunch. Proceeding to create popup.")

        write_log("Creating Toplevel popup window...")
        popup = tk.Toplevel(root)
        write_log("Toplevel popup created.")
        
        popup.title("Load Setlist?")
        popup.configure(bg=config.DARK_BG)
        
        write_log("Calculating geometry...")
        win_width = 600
        win_height = 300
        popup.update_idletasks() 
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x}+{y}")
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
        write_log("Popup geometry set.")
        
        # --- !! CRASH FIX !! ---
        # The combination of a withdrawn root, Toplevel, and grab_set()
        # causes a fatal crash on some systems. Removing them.
        # popup.grab_set() 
        # popup.transient(root)
        write_log("Skipping grab_set() and transient() to prevent crash.")
        # --- !! END FIX !! ---

        # --- Nested functions ---
        def launch_with(file_path_for_csv, display_name):
            write_log(f"launch_with() called. Path: {file_path_for_csv}, Name: {display_name}")
            temp_path = config.CSV_FILE_DEFAULT
            if os.path.abspath(file_path_for_csv) != os.path.abspath(temp_path):
                write_log("Copying setlist file...")
                shutil.copyfile(file_path_for_csv, temp_path)
            
            write_log("Saving config...")
            config.save_config(csv_file_used=file_path_for_csv,
                                current_setlist_display_name=display_name)
            write_log("Destroying popup.")
            popup.destroy()

        def handle_default_launch():
            write_log("handle_default_launch() called.")
            launch_with(config.CSV_FILE_DEFAULT_SOURCE, "Default Songs")

        def choose_setlist_file():
            write_log("choose_setlist_file() called. Destroying this popup.")
            popup.destroy()
            write_log("Calling _show_setlist_file_picker().")
            _show_setlist_file_picker(root)
        # --- End Nested functions ---

        write_log("Creating widgets for setlist chooser...")
        tk.Label(popup, text="Load Setlist or Default Songs?", font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=20)
        frame = tk.Frame(popup, bg=config.DARK_BG)
        frame.pack(pady=10)
        tk.Button(frame, text="Setlist", font=config.big_font, width=12, height=2,
                  command=choose_setlist_file, bg="#2a8f44", fg="white").grid(row=0, column=0, padx=10)
        tk.Button(frame, text="Default", font=config.big_font, width=12, height=2,
                  command=handle_default_launch, bg="#28578f", fg="white").grid(row=0, column=1, padx=10)
        write_log("Widgets created.")

        write_log("Calling root.wait_window(popup)... (Window should be visible NOW)")
        root.wait_window(popup) # This will still work and pause main.py
        write_log("root.wait_window(popup) has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_setlist_chooser ---")
        write_log(traceback.format_exc())
        # --- !! BUG FIX !! ---
        # Only destroy the popup that failed, not the main root window.
        if popup and popup.winfo_exists():
            popup.destroy()
        # --- !! END FIX !! ---


# --- SETLIST FILE PICKER (Second Level) ---

def _show_setlist_file_picker(root):
    write_log("_show_setlist_file_picker() called.")
    try:
        popup = tk.Toplevel(root)
        popup.title("Select Setlist File")
        popup.configure(bg=config.DARK_BG)
        
        write_log("Calculating geometry for setlist picker...")
        win_width = 600
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        x_offset = x + 40
        y_offset = y + 40
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x_offset}+{y_offset}")
        popup.geometry(f"{win_width}x{win_height}+{x_offset}+{y_offset}")
        
        # --- !! CRASH FIX !! ---
        # popup.grab_set()
        # popup.transient(root)
        write_log("Skipping grab_set() and transient() to prevent crash.")
        # --- !! END FIX !! ---
        
        write_log("Setlist picker popup created and configured.")

        def process_selected_setlist(selected_setlist_path):
            write_log(f"process_selected_setlist() called with: {selected_setlist_path}")
            temp_csv = os.path.join(config.SCRIPT_PATH, "MidiList_Set.csv")
            write_log(f"Creating ordered CSV at: {temp_csv}")
            utils.create_ordered_setlist_csv(selected_setlist_path, config.CSV_FILE_DEFAULT_SOURCE, temp_csv)
            write_log("CSV created.")

            display_name = os.path.basename(selected_setlist_path).replace(".txt", "")
            try:
                with open(selected_setlist_path, "r", encoding="utf-8") as f:
                    first_line_content = f.readline().strip()
                    if first_line_content:
                        display_name = first_line_content
                write_log(f"Display name set to: {display_name}")
            except Exception as e:
                write_log(f"Error reading display name: {e}")

            config.save_config(csv_file_used=temp_csv,
                                current_setlist_display_name=display_name)
            write_log("Config saved. Destroying popup.")
            popup.destroy()


        tk.Label(popup, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=config.DARK_BG,
                 fg=config.DARK_FG).pack(pady=20)
        
        write_log("Creating canvas and scrollbar for setlist picker...")
        files_frame = tk.Frame(popup, bg=config.DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)
        canvas = tk.Canvas(files_frame, bg=config.DARK_BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(files_frame, orient="vertical", command=canvas.yview,
                                 bg=config.SCROLLBAR_COLOR, troughcolor=config.DARK_BG, highlightbackground=config.DARK_BG)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollable_buttons_frame = tk.Frame(canvas, bg=config.DARK_BG)
        canvas_frame = canvas.create_window((0, 0), window=scrollable_buttons_frame, anchor="nw")
        scrollable_buttons_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_frame, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)),
                                                                      "units") if canvas.winfo_exists() else None)
        write_log("Canvas and scrollbar created.")

        if not os.path.exists(config.SETLIST_FOLDER):
            write_log(f"Setlist folder not found. Creating: {config.SETLIST_FOLDER}")
            os.makedirs(config.SETLIST_FOLDER)

        write_log("Reading setlist files...")
        setlist_files = [f for f in os.listdir(config.SETLIST_FOLDER) if f.endswith(".txt")]
        if not setlist_files:
            write_log("No setlist files found.")
            tk.Label(scrollable_buttons_frame, text="No setlist files found.", font=config.narrow_font_plain, bg=config.DARK_BG,
                     fg=config.DARK_FG).pack(pady=10)
        else:
            write_log(f"Found {len(setlist_files)} setlist files. Creating buttons...")
            for sl_file in setlist_files:
                file_path = os.path.join(config.SETLIST_FOLDER, sl_file)
                first_line = ""
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if not first_line:
                            first_line = sl_file
                except Exception as e:
                    first_line = f"Error reading {sl_file}"
                    write_log(f"Error reading first line of {sl_file}: {e}")

                btn = tk.Button(scrollable_buttons_frame, text=first_line, font=("Arial", 13),
                                width=65, pady=13,
                                command=lambda path=file_path: process_selected_setlist(path),
                                bg=config.BUTTON_BG, fg=config.DARK_FG, activebackground=config.BUTTON_HL, activeforeground=config.DARK_FG)
                btn.pack(pady=5, padx=10)
            write_log("Setlist buttons created.")

        write_log("Calling root.wait_window(popup) for setlist picker... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for setlist picker has finished.")
    
    except Exception as e:
        write_log(f"--- CRASH in _show_setlist_file_picker ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()


# --- DEVICE CHOOSER ---

def show_device_chooser(root):
    write_log("show_device_chooser() called.")
    try:
        conf = config.load_config()
        write_log("Config loaded.")
        
        if conf.get("relaunch_on_monitor_fail"):
            write_log("Relaunch on fail detected. Skipping device prompt.")
            device = conf.get("device", config.DEFAULT_DEVICE)
            os.environ["MIDI_DEVICE"] = device
            
            if device == config.USB_DIRECT_DEVICE: os.environ["MODE_TYPE"] = "USB_DIRECT"
            elif device == config.HYBRID_DEVICE: os.environ["MODE_TYPE"] = "HYBRID"
            elif device == config.DEFAULT_DEVICE: os.environ["MODE_TYPE"] = "BT"
            else: os.environ["MODE_TYPE"] = "CUSTOM_NO_RX"
            write_log(f"Environment set from config: {device}, {os.environ['MODE_TYPE']}")
            return
        write_log("Not a relaunch. Proceeding to create device chooser.")

        popup = tk.Toplevel(root)
        popup.title("Select MIDI Device")
        popup.configure(bg=config.DARK_BG)
        
        write_log("Calculating geometry for device chooser...")
        win_width = 900
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        write_log(f"Screen dims: {screen_width}x{screen_height}. Window pos: +{x}+{y}")
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
        # --- !! CRASH FIX !! ---
        # popup.grab_set()
        # popup.transient(root)
        write_log("Skipping grab_set() and transient() to prevent crash.")
        # --- !! END FIX !! ---
        
        write_log("Device chooser popup created and configured.")

        list_devices_popup_instance = None 

        def select_device(mode):
            write_log(f"select_device() called with mode: {mode}")
            if mode == "BT": selected = config.DEFAULT_DEVICE
            elif mode == "HYBRID": selected = config.HYBRID_DEVICE
            elif mode == "USB_DIRECT": selected = config.USB_DIRECT_DEVICE
            else: selected = config.DEFAULT_DEVICE
            
            os.environ["MIDI_DEVICE"] = selected
            os.environ["MODE_TYPE"] = mode
            config.save_config(device=selected)
            write_log(f"Device saved to config. Destroying popup.")
            popup.destroy()

        def timeout_default():
            write_log("timeout_default() called.")
            if popup.winfo_exists():
                select_device("BT")

        def select_from_list(device_name, window):
            write_log(f"select_from_list() called with: {device_name}")
            nonlocal list_devices_popup_instance
            window.destroy()
            list_devices_popup_instance = None
            
            mode_type = "UNKNOWN"
            actual_device_to_set = device_name

            if device_name == config.USB_DIRECT_DEVICE: mode_type = "USB_DIRECT"
            elif device_name == config.HYBRID_DEVICE: mode_type = "HYBRID"
            elif device_name == config.DEFAULT_DEVICE: mode_type = "BT"
            elif device_name == config.QUAD_CORTEX_DEVICE:
                actual_device_to_set = config.USB_DIRECT_DEVICE
                mode_type = "USB_DIRECT"
            
            if mode_type == "UNKNOWN": mode_type = "CUSTOM_NO_RX"
            
            os.environ["MIDI_DEVICE"] = actual_device_to_set
            os.environ["MODE_TYPE"] = mode_type
            config.save_config(device=actual_device_to_set)
            write_log(f"Device selected from list. Destroying main chooser popup.")
            popup.destroy()

        def list_devices():
            write_log("list_devices() called.")
            nonlocal list_devices_popup_instance
            if list_devices_popup_instance and list_devices_popup_instance.winfo_exists():
                list_devices_popup_instance.lift()
                return
            
            try:
                write_log(f"Running: {config.SENDMIDI_PATH} list")
                result = subprocess.run([config.SENDMIDI_PATH, "list"], capture_output=True, text=True, check=True)
                device_list = result.stdout.strip().splitlines()
                write_log(f"Found devices: {device_list}")
            except Exception as e:
                write_log(f"Error listing devices: {e}")
                return

            if not device_list:
                write_log("No MIDI devices found.")
                return

            list_window = tk.Toplevel(popup)
            list_devices_popup_instance = list_window
            
            def on_list_devices_popup_close():
                write_log("list_devices popup closed by user.")
                nonlocal list_devices_popup_instance
                list_devices_popup_instance = None
                list_window.destroy()

            list_window.protocol("WM_DELETE_WINDOW", on_list_devices_popup_close)

            list_window.title("Available MIDI Devices")
            list_window.configure(bg=config.DARK_BG)
            
            win_width_list = 400
            win_height_list = 600
            list_window.update_idletasks()
            screen_width_list = list_window.winfo_screenwidth()
            screen_height_list = list_window.winfo_screenheight()
            x_list = (screen_width_list // 2) - (win_width_list // 2)
            y_list = (screen_height_list // 2) - (win_height_list // 2)
            x_list_offset = x_list - 200
            y_list_offset = y_list + 50
            write_log(f"List_devices popup geometry: +{x_list_offset}+{y_list_offset}")
            list_window.geometry(f"{win_width_list}x{win_height_list}+{x_list_offset}+{y_list_offset}")
            
            tk.Label(list_window, text="Select a MIDI Device:", font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=10)
            active_devices, disabled_devices = [], []
            for dev in device_list:
                if dev == "Microsoft GS Wavetable Synth" or dev.startswith("MIDIOUT"):
                    disabled_devices.append(dev)
                else: active_devices.append(dev)
            for dev in active_devices:
                tk.Button(list_window, text=dev, font=config.narrow_font_plain, width=40, pady=10,
                          bg=config.BUTTON_BG, fg=config.DARK_FG,
                          command=(lambda d=dev: select_from_list(d, list_window))).pack(pady=5)
            for dev in disabled_devices:
                tk.Button(list_window, text=dev, font=config.narrow_font_plain, width=40, pady=10,
                          bg=config.DISABLED_BG, fg="#999999", state="disabled").pack(pady=5)
            write_log("List devices popup created.")

        
        # --- Main Widgets for Device Chooser ---
        write_log("Creating main widgets for device chooser...")
        tk.Label(popup, text="Select MIDI Device Mode:", bg=config.DARK_BG, fg=config.DARK_FG, font=config.big_font).pack(pady=10)
        btn_frame = tk.Frame(popup, bg=config.DARK_BG)
        btn_frame.pack(pady=5)
        
        tk.Button(btn_frame, text="BT (Default)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("BT"), bg="#2a8f44", fg="white").grid(row=0, column=0, pady=5, padx=5)
        tk.Button(btn_frame, text="USB Direct\n(Uses receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("USB_DIRECT"), bg="#b02f2f", fg="white").grid(row=1, column=0, pady=5, padx=5)
        tk.Button(btn_frame, text="Hybrid\n(No receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: select_device("HYBRID"), bg="#28578f", fg="white").grid(row=2, column=0, pady=5, padx=5)
        
        initial_debug_state = conf.get("debug_enabled", False)
        debug_var = tk.BooleanVar(value=initial_debug_state)
        
        def toggle_debug_logging():
            write_log(f"Debug logging toggled to: {debug_var.get()}")
            config.save_config(debug_enabled=debug_var.get())
            
        tk.Checkbutton(popup, text="Enable MIDI Debug Logging (Prints commands to console)",
                       variable=debug_var, command=toggle_debug_logging, bg=config.DARK_BG,
                       fg=config.DARK_FG, selectcolor=config.DARK_BG, activebackground=config.DARK_BG,
                       activeforeground=config.DARK_FG, font=config.narrow_font_plain).pack(pady=(20, 10))
        
        tk.Button(popup, text="List MIDI Devices", font=config.narrow_font_plain, command=list_devices,
                  bg="#444444", fg=config.DARK_FG, bd=0, padx=6, pady=6, height=2).pack(pady=5)

        timer_label = tk.Label(popup, text="", bg=config.DARK_BG, fg=config.DARK_FG, font=config.narrow_font_plain)
        timer_label.pack(pady=5)
        timer_count = [15]
        write_log("Starting countdown timer...")
        def countdown():
            if popup.winfo_exists() and timer_count[0] > 0:
                timer_label.config(text=f"Defaulting to BT in {timer_count[0]}s")
                timer_count[0] -= 1
                popup.after(1500, countdown)
            elif popup.winfo_exists() and timer_count[0] == 0:
                write_log("Countdown finished. Timing out to default.")
                timeout_default()
        countdown()
        
        write_log("Calling root.wait_window(popup) for device chooser... (Window should be visible NOW)")
        root.wait_window(popup)
        write_log("root.wait_window(popup) for device chooser has finished.")

    except Exception as e:
        write_log(f"--- CRASH in show_device_chooser ---")
        write_log(traceback.format_exc())
        if popup and popup.winfo_exists():
            popup.destroy()
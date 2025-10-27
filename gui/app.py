import tkinter as tk
import os
import sys
import ctypes
import time
import threading
import shutil
import csv
import subprocess
import config
import utils
from midi_manager import MidiManager
import traceback # Import traceback

class MidiSenderApp:
    def __init__(self, root):
        self.root = root
        self.midi_manager = MidiManager(self.handle_monitor_event)
        self.midi_manager.set_root(root)

        try:
            self.config = config.load_config()

            # --- !! Set initial device/mode based on environment !! ---
            self.midi_device = os.environ.get("MIDI_DEVICE", config.DEVICE_NAME_BT)
            self.mode_type = os.environ.get("MODE_TYPE", "BT")
            # --- !! End Set initial !! ---

            self.debug_enabled = self.config.get("debug_enabled", False)
            self.debug_var = tk.BooleanVar(value=self.debug_enabled)

            # --- !! NEW: Load CH1 override state !! ---
            self.ch1_override_active = self.config.get("ch1_override_active", False)
            self.ch1_override_var = tk.BooleanVar(value=self.ch1_override_active)
            # --- !! END NEW !! ---

            self.midi_manager.set_mode(self.midi_device, self.mode_type, self.debug_enabled)

            # Clear flag if it exists (though not used for relaunch signal anymore)
            if self.config.get("relaunch_on_monitor_fail"):
                config.save_config(relaunch_on_monitor_fail=False)

            self.current_setlist_name = self.config.get("current_setlist_display_name", "Unknown Setlist")
            self.csv_file = self.config.get("csv_file_used", config.CSV_FILE_DEFAULT)
            if not os.path.exists(self.csv_file):
                self.csv_file = config.CSV_FILE_DEFAULT_SOURCE

            self.last_press_time = 0
            self.last_selected_button = None
            self.all_buttons = []
            self.testing_toast_label = None

            self.setlist_popup_window = None
            self.list_devices_popup_window = None
            self.device_change_popup = None
            self.device_switch_popup = None

            self.toast_label = None
            self.toast_timer = None

            self._setup_window()
            self._build_gui()
            self._load_and_display_patches()

            # --- !! NEW: Update override checkbox state initially !! ---
            self._update_override_checkbox_state()
            # --- !! END NEW !! ---

            self.midi_manager.start_receivemidi()
            self.midi_manager.start_monitoring()

        except Exception as e:
            print("---!! FATAL ERROR ON APP INIT !!---")
            traceback.print_exc()
            try:
                error_popup = tk.Toplevel()
                error_popup.title("FATAL ERROR")
                tk.Label(error_popup, text=f"Failed to initialize app:\n{e}\n\nSee console for details.").pack(padx=20, pady=20)
                tk.Button(error_popup, text="Quit", command=self.root.destroy).pack(pady=10)
            except:
                 if self.root and self.root.winfo_exists(): self.root.destroy()

    def _setup_window(self):
        self.root.title("MIDI Patch Sender v2.x.x EXPERIMENTAL")
        self.root.configure(bg=config.DARK_BG)

        if os.path.exists(config.ICON_FILE):
            try:
                self.root.iconbitmap(config.ICON_FILE)
                if sys.platform == "win32":
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("sendmidi.gui")
            except Exception as e:
                print(f"Icon load error: {e}")

        window_width = 650
        window_height = 1150 # Adjusted height slightly if needed for checkbox text

        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()

        x = screen_width - window_width
        self.root.geometry(f"{window_width}x{window_height}+{x}+0")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Handle window close event."""
        if self.toast_timer:
            try:
                self.root.after_cancel(self.toast_timer)
            except:
                pass
        self.midi_manager.kill_receivemidi()
        # Save the *last active* device before closing, used by non-relaunch starts
        config.save_config(device=self.midi_device)
        if self.root and self.root.winfo_exists():
             self.root.destroy()

    def _build_gui(self):
        """Creates all the widgets for the main window."""

        status_frame = tk.Frame(self.root, bg=config.DARK_BG)
        status_frame.pack(fill="x", pady=2, padx=2)
        self.mode_label = tk.Label(status_frame, text=f"Current Mode: {self.mode_type}",
                                   fg=config.DARK_FG, bg=config.DARK_BG, font=("Arial", 12, "bold"))
        self.mode_label.pack(side="left", padx=4)

        setlist_display_frame = tk.Frame(self.root, bg=config.DARK_BG)
        setlist_display_frame.pack(fill="x", pady=5)
        self.setlist_display_label = tk.Label(setlist_display_frame, text=f"Setlist: {self.current_setlist_name}",
                                              fg=config.DARK_FG, bg=config.DARK_BG, font=config.narrow_font_plain)
        self.setlist_display_label.pack(side="left", padx=5)

        controls_frame = tk.Frame(self.root, bg=config.DARK_BG)
        controls_frame.pack(fill="x", pady=5)

        tk.Button(controls_frame, text="Switch Mode", font=config.narrow_font_plain,
                  command=self.show_device_switch_popup, bg="#b02f2f", fg=config.DARK_FG,
                  bd=0, padx=6, pady=6, height=2).pack(side="left", padx=(5, 0))

        tk.Button(controls_frame, text="List MIDI Devices", font=config.narrow_font_plain,
                  command=self.list_devices, bg="#444444", fg=config.DARK_FG,
                  bd=0, padx=6, pady=6, height=2).pack(side="left", padx=(5, 0))

        tk.Button(controls_frame, text="Choose Setlist", font=config.narrow_font_plain,
                  command=self.show_setlist_selection_popup, bg="#444444", fg=config.DARK_FG,
                  bd=0, padx=6, pady=6, height=2).pack(side="left", padx=(5, 0))

        # --- !! NEW: Frame for stacked checkboxes !! ---
        checkbox_frame = tk.Frame(controls_frame, bg=config.DARK_BG)
        checkbox_frame.pack(side="left", padx=(5, 0), anchor="n")
        # --- !! END NEW !! ---

        # --- !! NEW: CH1 Override Checkbox (added to checkbox_frame) !! ---
        self.ch1_override_checkbox = tk.Checkbutton(
            checkbox_frame, text="Force CH1 Reroute (Hybrid)", variable=self.ch1_override_var, # Added (Hybrid) hint
            command=self.toggle_ch1_override,
            bg=config.DARK_BG, fg=config.DARK_FG, selectcolor=config.DARK_BG,
            activebackground=config.DARK_BG, activeforeground=config.DARK_FG,
            font=config.narrow_font_plain, relief="raised", bd=2
        )
        self.ch1_override_checkbox.pack(side="top", anchor="w") # Pack to top
        # --- !! END NEW !! ---

        # --- !! MODIFIED: Moved to checkbox_frame and packed below !! ---
        initial_usb_lock_state = self.config.get("usb_lock_active", False)
        self.usb_lock_var = tk.BooleanVar(value=initial_usb_lock_state)
        self.usb_lock_checkbox = tk.Checkbutton(
            checkbox_frame, text="Lock USB/Autoswitch", variable=self.usb_lock_var,
            command=lambda: config.save_config(usb_lock_active=self.usb_lock_var.get()),
            bg=config.DARK_BG, fg=config.DARK_FG, selectcolor=config.DARK_BG,
            activebackground=config.DARK_BG, font=config.narrow_font_plain, relief="raised", bd=2
        )
        self.usb_lock_checkbox.pack(side="top", anchor="w", pady=(5,0)) # Pack to top, below new one
        # --- !! END MODIFIED !! ---

        debug_checkbox_main = tk.Checkbutton(
            controls_frame,
            text="Debug",
            variable=self.debug_var,
            command=self.toggle_debug_logging,
            bg=config.DARK_BG, fg=config.DARK_FG, selectcolor=config.DARK_BG,
            activebackground=config.DARK_BG, activeforeground=config.DARK_FG,
            font=config.narrow_font_plain, relief="raised", bd=2
        )
        debug_checkbox_main.pack(side="left", padx=(5, 0), anchor="n")


        up_button_frame = tk.Frame(self.root, bg=config.DARK_BG)
        up_button_frame.pack(fill="x")
        self.btn_up = tk.Button(up_button_frame, text="↑", font=("Arial", 36, "bold"), height=1,
                                command=self.scroll_up, bg=config.BUTTON_BG, fg=config.DARK_FG, relief="raised", bd=2)
        self.btn_up.pack(fill="x")

        main_frame = tk.Frame(self.root, bg=config.DARK_BG)
        main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(main_frame, bg=config.DARK_BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview,
                                 bg=config.SCROLLBAR_COLOR, troughcolor=config.DARK_BG, width=50)
        scrollbar.pack(side="right", fill="y")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.scrollable_frame = tk.Frame(self.canvas, bg=config.DARK_BG)
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_frame, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        down_button_frame = tk.Frame(self.root, bg=config.DARK_BG)
        down_button_frame.pack(fill="x")
        self.btn_down = tk.Button(down_button_frame, text="↓", font=("Arial", 36, "bold"), height=1,
                                  command=self.scroll_down, bg=config.BUTTON_BG, fg=config.DARK_FG, relief="raised", bd=2)
        self.btn_down.pack(fill="x")

    def toggle_debug_logging(self):
        """Called when the main debug checkbox is clicked."""
        new_state = self.debug_var.get()
        self.debug_enabled = new_state
        self.midi_manager.set_debug_state(new_state)
        config.save_config(debug_enabled=new_state)
        print(f"Debug logging {'enabled' if new_state else 'disabled'} by main checkbox.")

    # --- !! NEW: Handler for CH1 Override Checkbox !! ---
    def toggle_ch1_override(self):
        """Called when the CH1 override checkbox is clicked."""
        new_state = self.ch1_override_var.get()
        self.ch1_override_active = new_state
        config.save_config(ch1_override_active=new_state)
        print(f"CH1 Override {'enabled' if new_state else 'disabled'}.")
        # Update color immediately
        self._update_override_checkbox_state()
        # The monitor loop will also pick this up on its next cycle if needed
    # --- !! END NEW !! ---


    def scroll_up(self):
        self.btn_up.config(relief="sunken")
        self.canvas.yview_scroll(-1, "units")
        self.root.after(150, lambda: self.btn_up.config(relief="raised"))

    def scroll_down(self):
        self.btn_down.config(relief="sunken")
        self.canvas.yview_scroll(1, "units")
        self.root.after(150, lambda: self.btn_down.config(relief="raised"))

    def show_toast(self, msg, duration=2000, bg="#303030", fg="white"):
        """
        Thread-safe method to show a toast. Schedules it on the main GUI thread.
        """
        if self.root and self.root.winfo_exists():
            self.root.after(0, self._show_toast_on_main_thread, msg, duration, bg, fg)

    def _show_toast_on_main_thread(self, msg, duration=2000, bg="#303030", fg="white"):
        """Internal function that *must* run on the main thread."""
        try:
            if not self.root or not self.root.winfo_exists(): return
            if self.toast_timer: self.root.after_cancel(self.toast_timer); self.toast_timer = None
            if not self.toast_label or not self.toast_label.winfo_exists():
                self.toast_label = tk.Label(self.root, font=config.narrow_font_small)
            self.toast_label.config(text=msg, bg=bg, fg=fg)
            self.toast_label.place(relx=1.0, rely=0, anchor="ne", x=-5, y=5)
            self.toast_label.lift()
            self.toast_timer = self.root.after(duration, self._hide_toast)
        except Exception as e: print(f"Error in _show_toast_on_main_thread: {e}")

    def _hide_toast(self):
        """Hides the persistent toast label. Runs on main thread."""
        try:
            if self.root and self.root.winfo_exists() and self.toast_label and self.toast_label.winfo_exists():
                self.toast_label.place_forget()
            self.toast_timer = None
        except Exception as e: print(f"Error in _hide_toast: {e}")

    # --- !! NEW: Helper to enable/disable override checkbox !! ---
    def _update_override_checkbox_state(self):
        """Enables/disables and styles the CH1 override checkbox based on mode."""
        if hasattr(self, 'ch1_override_checkbox') and self.ch1_override_checkbox.winfo_exists():
            is_hybrid = self.mode_type == "HYBRID"
            new_state = tk.NORMAL if is_hybrid else tk.DISABLED
            self.ch1_override_checkbox.config(state=new_state)

            if not is_hybrid:
                # If not hybrid, ensure it's unchecked and greyed out
                self.ch1_override_var.set(False) # Force uncheck
                self.ch1_override_checkbox.config(bg=config.DISABLED_BG, activebackground=config.DISABLED_BG, fg="#999999")
            else:
                 # If hybrid, set color based on whether it's *checked*
                 is_checked = self.ch1_override_var.get()
                 if is_checked:
                    self.ch1_override_checkbox.config(bg=config.USB_UNAVAILABLE_COLOR, activebackground=config.USB_UNAVAILABLE_ACTIVE_COLOR, fg=config.DARK_FG)
                 else:
                    self.ch1_override_checkbox.config(bg=config.DARK_BG, activebackground=config.DARK_BG, fg=config.DARK_FG)
    # --- !! END NEW !! ---

    def _set_device_mode(self, new_mode_type, new_device, should_relaunch=False):
        """Sets the MIDI device and mode, optionally relaunching the app."""
        self.midi_manager.kill_receivemidi()
        # Don't save device here, only on clean exit (on_close) or manual switch (switch_and_close)

        self.midi_device = new_device
        self.mode_type = new_mode_type

        # Update manager state
        self.midi_manager.set_mode(self.midi_device, self.mode_type, self.debug_enabled)

        # Update GUI label if it exists
        if hasattr(self, 'mode_label') and self.mode_label and self.mode_label.winfo_exists():
             self.mode_label.config(text=f"Current Mode: {self.mode_type}")

        # --- !! NEW: Update checkbox state after mode change !! ---
        self._update_override_checkbox_state()
        # --- !! END NEW !! ---

        if should_relaunch:
            print(f"Relaunching into mode: {new_mode_type} with device: {new_device}")
            new_env = os.environ.copy()
            new_env["MIDI_DEBUG_ENABLED"] = str(self.debug_enabled)
            # --- !! MODIFICATION: Pass target device via env var for relaunch !! ---
            new_env["RELAUNCH_MIDI_DEVICE"] = new_device # Use this in main.py
            # --- !! END MODIFICATION !! ---

            # --- !! MODIFICATION: Pass target mode via command line arg !! ---
            relaunch_command = [sys.executable, sys.argv[0], f"--relaunch={new_mode_type}"]
            # --- !! END MODIFICATION !! ---

            subprocess.Popen(relaunch_command, env=new_env, creationflags=subprocess.CREATE_NO_WINDOW)

            if self.root and self.root.winfo_exists(): self.root.destroy()
            return

        # If not relaunching, start receivemidi if needed
        self.midi_manager.start_receivemidi()
        self.show_toast(f"Switched to {self.mode_type} mode: {self.midi_device}")

    def _load_and_display_patches(self):
        # (Function content unchanged - Keep previous version)
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.all_buttons.clear()
        self.last_selected_button = None

        try:
            try:
                with open(self.csv_file, "r", encoding="utf-8") as csvfile:
                    reader = csv.reader(csvfile.read().splitlines())
            except UnicodeDecodeError:
                with open(self.csv_file, "r", encoding="latin-1") as csvfile:
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

                        btn = tk.Button(self.scrollable_frame, text=label, font=config.big_font,
                                        padx=20, pady=10, bg=config.BUTTON_BG, fg=config.DARK_FG,
                                        activebackground=config.BUTTON_HL, bd=0)
                        btn.config(command=self.patch_func_factory(btn, label, prog1, prog2, cc_commands))
                        btn.pack(pady=5, padx=10, fill="x")
                        self.all_buttons.append(btn)
                    except ValueError:
                        print(f"Skipping invalid row: {row}")
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

        except FileNotFoundError:
            msg = f"Error: CSV file '{self.csv_file}' not found."
            print(msg)
            self.show_toast(msg, bg="red")
        except Exception as e: # Catch other potential errors
            msg = f"Error loading CSV '{self.csv_file}': {e}"
            print(msg)
            traceback.print_exc()
            self.show_toast(msg, bg="red")

    def patch_func_factory(self, current_btn, label, prog1, prog2, cc_commands):
        # (Function content unchanged - Keep previous version)
        def patch_func():
            now = time.time()
            if now - self.last_press_time < 1:
                return
            self.last_press_time = now

            if self.last_selected_button and self.last_selected_button.winfo_exists():
                 try: self.last_selected_button.config(bg=config.BUTTON_BG)
                 except tk.TclError: pass
            if current_btn.winfo_exists():
                 try: current_btn.config(bg=config.HIGHLIGHT_BG)
                 except tk.TclError: pass
            self.last_selected_button = current_btn

            for b in self.all_buttons:
                if b.winfo_exists():
                     try: b.config(state="disabled")
                     except tk.TclError: pass

            self.midi_manager.kill_receivemidi()

            all_commands_for_this_patch = [
                ["ch", "2", "pc", "127"], ["ch", "1", "cc", "47", "2"],
                ["ch", "1", "pc", str(prog1)], ["ch", "2", "pc", str(prog2)]
            ] + cc_commands

            commands_ch1_before = []
            commands_after = []

            if self.midi_device == config.DEVICE_NAME_CH2:
                for cmd in all_commands_for_this_patch:
                    if self.mode_type == "USB_DIRECT" and len(cmd) > 1 and cmd[0] == "ch" and cmd[1] == "1" and cmd[2] == "pc":
                        commands_ch1_before.append(cmd)
                    else:
                        commands_after.append(cmd)
            else:
                commands_after = all_commands_for_this_patch

            if label == "TEST 123" and ["ch", "1", "pc", "126"] not in commands_ch1_before and self.mode_type != "BT":
                commands_ch1_before.insert(0, ["ch", "1", "pc", "126"])

            def _send_patch_commands_in_thread():
                root_exists = self.root and self.root.winfo_exists()
                try: # Add try/except around MIDI sending
                    for cmd in commands_ch1_before:
                        self.midi_manager.send_midi([cmd])
                    if commands_ch1_before:
                        time.sleep(0.05)

                    self.midi_manager.start_receivemidi()
                    time.sleep(1)

                    if label == "TEST 123":
                        def create_test_toast():
                            if self.root and self.root.winfo_exists():
                                if self.testing_toast_label and self.testing_toast_label.winfo_exists():
                                    self.testing_toast_label.destroy()
                                self.testing_toast_label = tk.Label(self.root, text="TESTING", bg="red", fg="white", font=config.big_font)
                                self.testing_toast_label.place(relx=0.5, rely=0.1, anchor="n")
                                self.testing_toast_label.lift()

                        if root_exists: self.root.after(0, create_test_toast)

                        for cmd in commands_after:
                            self.midi_manager.send_midi([cmd])
                            time.sleep(0.25)

                        if root_exists:
                            self.root.after(0, lambda: [
                                self.testing_toast_label.destroy()
                                if self.testing_toast_label and self.testing_toast_label.winfo_exists() else None
                            ])

                    else:
                        for cmd in commands_after:
                            self.midi_manager.send_midi([cmd])
                            time.sleep(0.25)

                except Exception as midi_err:
                    print(f"Error during MIDI send thread: {midi_err}")
                    traceback.print_exc()
                    if root_exists:
                        self.root.after(0, lambda: self.show_toast(f"MIDI Send Error: {midi_err}", bg="red", duration=5000))

                finally: # Ensure buttons are re-enabled even if an error occurs
                    if root_exists:
                        self.root.after(0, lambda: [
                            b.config(state="normal") for b in self.all_buttons if b.winfo_exists()
                        ])

            threading.Thread(target=_send_patch_commands_in_thread, daemon=True).start()

        return patch_func


    def show_device_switch_popup(self):
        # (Function content unchanged - Keep previous version)
        if self.device_switch_popup and self.device_switch_popup.winfo_exists():
            self.device_switch_popup.lift()
            return

        popup = tk.Toplevel(self.root)
        self.device_switch_popup = popup
        popup.title("Select MIDI Device Mode")
        popup.configure(bg=config.DARK_BG)

        win_width = 900
        win_height = 550
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")

        try: popup.grab_set()
        except tk.TclError: print("Grab_set failed in show_device_switch_popup")


        tk.Label(popup, text="Select New MIDI Device Mode:", bg=config.DARK_BG, fg=config.DARK_FG, font=config.big_font).pack(pady=10)
        btn_frame = tk.Frame(popup, bg=config.DARK_BG)
        btn_frame.pack(pady=20)

        def switch_and_close(mode, device):
            # Save the manually selected device here
            config.save_config(device=device)
            self._set_device_mode(mode, device, should_relaunch=False)
            popup.destroy()

        tk.Button(btn_frame, text="BT (Default)", font=config.big_font, width=30, height=2,
                  command=lambda: switch_and_close("BT", config.DEVICE_NAME_BT), bg="#2a8f44", fg="white").pack(pady=5)
        tk.Button(btn_frame, text="USB Direct\n(Uses receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: switch_and_close("USB_DIRECT", config.DEVICE_NAME_CH2), bg="#b02f2f", fg="white").pack(pady=5)
        tk.Button(btn_frame, text="Hybrid\n(No receivemidi)", font=config.big_font, width=30, height=2,
                  command=lambda: switch_and_close("HYBRID", config.DEVICE_NAME_CH2), bg="#28578f", fg="white").pack(pady=5)


    def list_devices(self):
        # (Function content unchanged - Keep previous version)
        if self.list_devices_popup_window and self.list_devices_popup_window.winfo_exists():
            self.list_devices_popup_window.lift()
            return

        device_list = self.midi_manager.list_devices()
        if not device_list:
            self.show_toast("No MIDI devices found.", bg="red")
            return

        popup = tk.Toplevel(self.root)
        self.list_devices_popup_window = popup
        popup.title("Available MIDI Devices")
        popup.configure(bg=config.DARK_BG)

        win_width = 400
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2) + 100
        y = (screen_height // 2) - (win_height // 2) + 100
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")

        tk.Label(popup, text="Select a MIDI Device:", font=config.big_font, bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=10)

        def select_new_device(device_name):
            mode_type = "UNKNOWN"
            actual_device = device_name

            if device_name == config.DEVICE_NAME_CH2: mode_type = "USB_DIRECT"
            elif device_name == config.DEVICE_NAME_BT: mode_type = "BT"
            elif device_name == config.DEVICE_NAME_CH1:
                actual_device = config.DEVICE_NAME_CH2
                mode_type = "USB_DIRECT"

            if mode_type == "UNKNOWN": mode_type = "CUSTOM_NO_RX"

            # Save the manually selected device here
            config.save_config(device=actual_device)
            self._set_device_mode(mode_type, actual_device, should_relaunch=False)
            popup.destroy()

        for dev in device_list:
            is_disabled = dev == "Microsoft GS Wavetable Synth" or dev.startswith("MIDIOUT")
            btn = tk.Button(popup, text=dev, command=lambda d=dev: select_new_device(d),
                      bg=config.BUTTON_BG if not is_disabled else config.DISABLED_BG,
                      fg=config.DARK_FG if not is_disabled else "#999999",
                      state="normal" if not is_disabled else "disabled",
                      font=config.narrow_font_plain, width=40, pady=10)
            btn.pack(pady=5)


    def show_setlist_selection_popup(self):
        # (Function content unchanged - Keep previous version)
        if self.setlist_popup_window and self.setlist_popup_window.winfo_exists():
            self.setlist_popup_window.lift()
            return

        popup = tk.Toplevel(self.root)
        self.setlist_popup_window = popup
        popup.title("Select Setlist File")
        popup.configure(bg=config.DARK_BG)

        win_width = 600
        win_height = 600
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2) + 50
        y = (screen_height // 2) - (win_height // 2) + 50
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")

        tk.Label(popup, text="Choose a Setlist File:", font=("Comic Sans MS", 26), bg=config.DARK_BG,
                 fg=config.DARK_FG).pack(pady=20)
        files_frame = tk.Frame(popup, bg=config.DARK_BG)
        files_frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(files_frame, bg=config.DARK_BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = tk.Scrollbar(files_frame, orient="vertical", command=canvas.yview,
                                 bg=config.SCROLLBAR_COLOR, troughcolor=config.DARK_BG)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollable_frame = tk.Frame(canvas, bg=config.DARK_BG)
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _process_selection(selected_path):
            if selected_path.endswith(".txt"):
                temp_csv = os.path.join(config.SCRIPT_PATH, "MidiList_Set.csv")
                utils.create_ordered_setlist_csv(selected_path, config.CSV_FILE_DEFAULT_SOURCE, temp_csv)
                self.csv_file = temp_csv

                display_name = os.path.basename(selected_path).replace(".txt", "")
                try:
                    with open(selected_path, "r", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        if first_line: display_name = first_line
                except Exception: pass
                self.current_setlist_name = display_name
            else:
                shutil.copyfile(selected_path, config.CSV_FILE_DEFAULT)
                self.csv_file = config.CSV_FILE_DEFAULT
                self.current_setlist_name = "Default Songs"

            config.save_config(csv_file_used=self.csv_file,
                                current_setlist_display_name=self.current_setlist_name)

            if self.setlist_display_label.winfo_exists():
                self.setlist_display_label.config(text=f"Setlist: {self.current_setlist_name}")
            self._load_and_display_patches()
            self.show_toast(f"Setlist loaded: {self.current_setlist_name}")
            popup.destroy()

        tk.Button(scrollable_frame, text="Load Default Songs", font=("Arial", 13),
                  command=lambda: _process_selection(config.CSV_FILE_DEFAULT_SOURCE),
                  bg="#28578f", fg="white", width=65, pady=13).pack(pady=5, padx=10)

        if not os.path.exists(config.SETLIST_FOLDER): os.makedirs(config.SETLIST_FOLDER)
        setlist_files = [f for f in os.listdir(config.SETLIST_FOLDER) if f.endswith(".txt")]
        for sl_file in setlist_files:
            file_path = os.path.join(config.SETLIST_FOLDER, sl_file)
            first_line = sl_file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip() or sl_file
            except: pass

            tk.Button(scrollable_frame, text=first_line, font=("Arial", 13),
                      command=lambda path=file_path: _process_selection(path),
                      bg=config.BUTTON_BG, fg=config.DARK_FG, width=65, pady=13).pack(pady=5, padx=10)


    def _create_device_popup(self, title, message, ack_text, decline_text, is_failback):
        # (Function content unchanged - Keep previous version)
        if self.device_change_popup and self.device_change_popup.winfo_exists():
            return # Avoid multiple popups

        popup = tk.Toplevel(self.root)
        self.device_change_popup = popup # Store reference
        popup.title(title)
        popup.configure(bg=config.DARK_BG)

        win_width = 800
        win_height = 400
        popup.update_idletasks()
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width // 2) - (win_width // 2)
        y = (screen_height // 2) - (win_height // 2)
        popup.geometry(f"{win_width}x{win_height}+{x}+{y}")

        # Make it modal ONLY if the root window is visible
        if self.root.winfo_viewable():
            try: popup.grab_set()
            except tk.TclError: print("Grab_set failed in _create_device_popup")
            try: popup.transient(self.root)
            except tk.TclError: print("Transient failed in _create_device_popup")

        tk.Label(popup, text=title.replace("!", ""), font=("Arial", 24, "bold"),
                 bg=config.DARK_BG, fg=("red" if not is_failback else "#2a8f44")).pack(pady=20)
        tk.Label(popup, text=message, font=("Arial", 14), bg=config.DARK_BG, fg=config.DARK_FG).pack(pady=10)

        switch_choice = [None] # Use list to allow modification in nested functions

        def on_ack():
            switch_choice[0] = True
            if is_failback: self.midi_manager.set_user_declined_switch(False)
            if popup.winfo_exists(): popup.destroy()
            self.device_change_popup = None # Clear reference

        def on_decline():
            switch_choice[0] = False
            if is_failback: self.midi_manager.set_user_declined_switch(True)
            if popup.winfo_exists(): popup.destroy()
            self.device_change_popup = None # Clear reference

        # Ensure popup closes cleanly if user closes window
        popup.protocol("WM_DELETE_WINDOW", on_decline if decline_text else on_ack)

        btn_frame = tk.Frame(popup, bg=config.DARK_BG)
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text=ack_text, font=("Arial", 16), command=on_ack,
                  bg=("#b02f2f" if not is_failback else "#2a8f44"), fg="white").pack(side="left", padx=10)

        if decline_text:
            tk.Button(btn_frame, text=decline_text, font=("Arial", 16), command=on_decline,
                      bg=("#28578f" if is_failback else "#444444"), fg="white").pack(side="right", padx=10)

        # Use wait_window to block until popup is closed
        self.root.wait_window(popup)
        return switch_choice[0]


    def handle_monitor_event(self, event_type, data=None):
        try:
            if event_type == "TOAST":
                message = data.get("message", "No message")
                color = data.get("color", "#303030")
                self.show_toast(message, bg=color)

            elif event_type == "MIDI_ACTIVITY":
                status = data.get("status")
                if status == "SENDING": self.show_toast("SENDING", duration=250, bg=config.TOAST_YELLOW, fg="#000000")
                elif status == "RECEIVING": self.show_toast("RECEIVING", duration=250, bg=config.TOAST_YELLOW, fg="#000000")

            elif event_type == "GET_USB_LOCK_STATE":
                if hasattr(self, 'usb_lock_var') and self.usb_lock_var:
                    try: return self.usb_lock_var.get()
                    except tk.TclError: return False
                return False

            # --- !! NEW: Getter for CH1 Override !! ---
            elif event_type == "GET_CH1_OVERRIDE_STATE":
                if hasattr(self, 'ch1_override_var') and self.ch1_override_var:
                    try: return self.ch1_override_var.get()
                    except tk.TclError: return False
                return False
            # --- !! END NEW !! ---

            elif event_type == "USB_STATUS_UPDATE":
                if not data or not hasattr(self, 'mode_label') or not self.mode_label or not self.mode_label.winfo_exists(): return

                label_text = data["mode_label_text"]
                usb_present = data["usb_devices_present"]
                current_mode = data["current_mode"]
                ch1_override_on = data.get("ch1_override_active", False) # --- !! NEW !! ---

                checkbox_exists = hasattr(self, 'usb_lock_checkbox') and self.usb_lock_checkbox and self.usb_lock_checkbox.winfo_exists()
                override_checkbox_exists = hasattr(self, 'ch1_override_checkbox') and self.ch1_override_checkbox and self.ch1_override_checkbox.winfo_exists() # --- !! NEW !! ---

                if current_mode == "USB_DIRECT" or current_mode == "HYBRID":
                    if not usb_present:
                        self.mode_label.config(text=label_text, fg="red")
                        if checkbox_exists: self.usb_lock_checkbox.config(bg=config.USB_UNAVAILABLE_COLOR, activebackground=config.USB_UNAVAILABLE_ACTIVE_COLOR)
                    else:
                        self.mode_label.config(text=label_text, fg=config.USB_AVAILABLE_COLOR)
                        if checkbox_exists: self.usb_lock_checkbox.config(bg=config.USB_AVAILABLE_COLOR, activebackground=config.USB_AVAILABLE_ACTIVE_COLOR)
                elif current_mode == "BT":
                    if usb_present:
                        self.mode_label.config(text=f"{label_text} (USB AVAILABLE)", fg=config.USB_AVAILABLE_COLOR)
                        if checkbox_exists: self.usb_lock_checkbox.config(bg=config.USB_AVAILABLE_COLOR, activebackground=config.USB_AVAILABLE_ACTIVE_COLOR)
                    else:
                        self.mode_label.config(text=label_text, fg=config.DARK_FG)
                        if checkbox_exists: self.usb_lock_checkbox.config(bg=config.DARK_BG, activebackground=config.DARK_BG)

                # --- !! NEW: Update CH1 Override checkbox color/state !! ---
                # Call the helper function which now handles enable/disable too
                self._update_override_checkbox_state()
                # --- !! END NEW !! ---

            elif event_type == "TRIGGER_FAILOVER":
                self.show_toast("USB Disconnected! Failing over to Bluetooth...", bg="red", duration=4000)
                self._set_device_mode("BT", config.DEVICE_NAME_BT, should_relaunch=True)

            elif event_type == "TRIGGER_FAILBACK_POPUP":
                message = f"Both {config.DEVICE_NAME_CH2} and {config.DEVICE_NAME_CH1}\nhave reconnected via USB. Do you want to switch back to USB Direct mode?"
                choice = self._create_device_popup("USB Devices Reconnected!", message,
                                                   "Acknowledge & Switch to USB Direct", "No, stay on Bluetooth", True)

                # --- !! Ensure this logic is correct !! ---
                if choice is True: # Explicitly check for True (handles None if popup closed unexpectedly)
                    print("User chose to failback to USB_DIRECT. Relaunching...") # Debug print
                    self._set_device_mode("USB_DIRECT", config.DEVICE_NAME_CH2, should_relaunch=True)
                else:
                    print("User declined failback or closed popup.") # Debug print
                # --- !! End Check !! ---

        except Exception as e:
            print(f"---!! FATAL ERROR in handle_monitor_event !!---")
            print(f"Event: {event_type}, Data: {data}")
            traceback.print_exc()
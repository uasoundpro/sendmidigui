import subprocess
import os
import time
import threading
import config
import traceback # Import traceback

class MidiManager:
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback
        self.midi_device = config.DEFAULT_DEVICE
        self.mode_type = "BT"
        self.debug_enabled = False # Initial state

        self._receivemidi_process = None
        self._receivemidi_stdout_thread = None
        self._receivemidi_stderr_thread = None

        self._qc_midi_target_device = config.QUAD_CORTEX_DEVICE

        self._usb_stable_start_time = None
        self._user_declined_usb_switch = False
        self._usb_disconnect_warning_shown = False
        self._root = None

    def set_root(self, root):
        self._root = root

    def set_mode(self, device, mode, debug_state):
        self.midi_device = device
        self.mode_type = mode
        self.debug_enabled = debug_state # Set initial debug state here
        print(f"MidiManager Mode Set: {mode} (Device: {device}, Debug: {debug_state})")

        self._qc_midi_target_device = config.QUAD_CORTEX_DEVICE

        if self.mode_type == "USB_DIRECT" or self.mode_type == "HYBRID":
            self._user_declined_usb_switch = False
            self._usb_disconnect_warning_shown = False

    def set_debug_state(self, enabled):
        """Allows the GUI to update the debug state dynamically."""
        self.debug_enabled = enabled
        print(f"MidiManager debug state set to: {enabled}")

    def send_midi(self, command_list):
        for command in command_list:
            target_device = self.midi_device
            if self.midi_device == config.USB_DIRECT_DEVICE or self.midi_device == config.HYBRID_DEVICE:
                if len(command) > 1 and command[0] == "ch":
                    channel_str = command[1]
                    if channel_str == "2":
                        target_device = self.midi_device
                    elif channel_str == "1":
                        target_device = self._qc_midi_target_device

            full_cmd = [config.SENDMIDI_PATH, "dev", target_device]
            full_cmd.extend([str(arg) for arg in command])

            if self.debug_enabled:
                print(f"[MIDI DEBUG] Executing: {' '.join(full_cmd)}")

            if self.debug_enabled:
                print("DEBUG: Sending MIDI_ACTIVITY signal (SENDING)")
            self.gui_callback("MIDI_ACTIVITY", {"status": "SENDING"})

            subprocess.run(full_cmd, creationflags=subprocess.CREATE_NO_WINDOW)


    def _read_receivemidi_output(self, pipe, stream_name):
        while self._receivemidi_process and self._receivemidi_process.poll() is None:
            line = pipe.readline()
            if line:
                if self.debug_enabled:
                    print("DEBUG: Sending MIDI_ACTIVITY signal (RECEIVING)")
                self.gui_callback("MIDI_ACTIVITY", {"status": "RECEIVING"})
                print(f"[receivemidi {stream_name}]: {line.strip()}")
            else:
                time.sleep(0.01)
        for line in pipe.readlines():
            if self.debug_enabled:
                print("DEBUG: Sending MIDI_ACTIVITY signal (RECEIVING - final read)")
            self.gui_callback("MIDI_ACTIVITY", {"status": "RECEIVING"})
            print(f"[receivemidi {stream_name}]: {line.strip()}")
        print(f"receivemidi {stream_name} reader thread finished.")


    def kill_receivemidi(self):
        if self._receivemidi_process and self._receivemidi_process.poll() is None:
            try:
                print("Attempting to terminate receivemidi process...")
                self._receivemidi_process.terminate()
                self._receivemidi_process.wait(timeout=2)
                print("receivemidi process terminated.")
            except Exception as e:
                print(f"Error terminating receivemidi process: {e}")

        self._receivemidi_process = None

        if self._receivemidi_stdout_thread and self._receivemidi_stdout_thread.is_alive():
            self._receivemidi_stdout_thread.join(timeout=1)
        if self._receivemidi_stderr_thread and self._receivemidi_stderr_thread.is_alive():
            self._receivemidi_stderr_thread.join(timeout=1)

        self._receivemidi_stdout_thread = None
        self._receivemidi_stderr_thread = None
        print("receivemidi cleanup complete.")

    def start_receivemidi(self):
        if self.mode_type != "USB_DIRECT":
            return

        self.kill_receivemidi()

        try:
            receivemidi_cmd = [
                config.RECEIVEMIDI_PATH,
                "dev", config.USB_DIRECT_DEVICE,
                "pass", config.QUAD_CORTEX_DEVICE
            ]
            print(f"Launching receivemidi: {' '.join(receivemidi_cmd)}")
            self._receivemidi_process = subprocess.Popen(receivemidi_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                        text=True, creationflags=subprocess.CREATE_NO_WINDOW)

            self._receivemidi_stdout_thread = threading.Thread(target=self._read_receivemidi_output,
                                                              args=(self._receivemidi_process.stdout, "stdout"))
            self._receivemidi_stderr_thread = threading.Thread(target=self._read_receivemidi_output,
                                                              args=(self._receivemidi_process.stderr, "stderr"))
            self._receivemidi_stdout_thread.daemon = True
            self._receivemidi_stderr_thread.daemon = True
            self._receivemidi_stdout_thread.start()
            self._receivemidi_stderr_thread.start()

            print(f"receivemidi process started with PID: {self._receivemidi_process.pid}")

        except FileNotFoundError:
            self.gui_callback("TOAST", {"message": f"Error: {config.RECEIVEMIDI_PATH} not found.", "color": "red"})
        except Exception as e:
            self.gui_callback("TOAST", {"message": f"Error launching receivemidi: {e}", "color": "red"})

    def list_devices(self):
        try:
            result = subprocess.run([config.SENDMIDI_PATH, "list"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip().splitlines()
        except Exception as e:
            print(f"Error listing devices: {e}")
            self.gui_callback("TOAST", {"message": f"Error listing devices: {e}", "color": "red"})
            return []

    def start_monitoring(self):
        if not self._root:
            print("Error: Root window not set in MidiManager. Cannot start monitor.")
            return

        print("Starting device monitor...")
        if self._root and self._root.winfo_exists():
            self._root.after(0, self._monitor_midi_device)

    def _monitor_midi_device(self):
        if not self._root or not self._root.winfo_exists():
            print("Monitor: Root window destroyed, stopping monitor.")
            return
        try:
            devices = self.list_devices()

            morningstar_present = config.USB_DIRECT_DEVICE in devices or config.HYBRID_DEVICE in devices
            quad_cortex_present = config.QUAD_CORTEX_DEVICE in devices
            usb_devices_present = morningstar_present and quad_cortex_present

            # --- !! NEW: Get CH1 override state from GUI !! ---
            ch1_override_active = False
            if self._root and self._root.winfo_exists():
                ch1_override_active = self.gui_callback("GET_CH1_OVERRIDE_STATE")
            # --- !! END NEW !! ---

            mode_label_text = f"Current Mode: {self.mode_type}"
            if self.mode_type == "HYBRID":
                # --- !! MODIFIED: Added ch1_override_active check !! ---
                if ch1_override_active or not quad_cortex_present:
                    # REROUTE QC messages (Ch 1) to MC8 (Hybrid Device)
                    self._qc_midi_target_device = config.HYBRID_DEVICE
                    # Update label text based on *why* it's rerouted
                    if ch1_override_active:
                        mode_label_text = f"Current Mode: {self.mode_type} (QC OVERRIDE to MC8)"
                    else:
                        mode_label_text = f"Current Mode: {self.mode_type} (QC REROUTED to MC8)"
                # --- !! END MODIFICATION !! ---
                else:
                    # Use QC (Ch 1) directly if present and not overridden
                    self._qc_midi_target_device = config.QUAD_CORTEX_DEVICE
                    mode_label_text = f"Current Mode: {self.mode_type} (QC DIRECT)"
            else:
                # All other modes, QC target is direct
                self._qc_midi_target_device = config.QUAD_CORTEX_DEVICE

            # --- !! MODIFIED: Pass override state back !! ---
            status_data = {
                "mode_label_text": mode_label_text,
                "usb_devices_present": usb_devices_present,
                "current_mode": self.mode_type,
                "ch1_override_active": ch1_override_active # Pass state to GUI
            }
            # --- !! END MODIFICATION !! ---
            if self._root and self._root.winfo_exists():
                 self._root.after(0, lambda: self.gui_callback("USB_STATUS_UPDATE", status_data))

            usb_lock_active = False
            if self._root and self._root.winfo_exists():
                 usb_lock_active = self.gui_callback("GET_USB_LOCK_STATE")

            # --- Failover Logic ---
            trigger_failover = False
            if self.mode_type == "USB_DIRECT":
                if not usb_devices_present: trigger_failover = True
            elif self.mode_type == "HYBRID":
                if not morningstar_present: trigger_failover = True # Hybrid only cares about MC8

            if trigger_failover:
                if usb_lock_active:
                    if not self._usb_disconnect_warning_shown:
                         if self._root and self._root.winfo_exists():
                            msg = "USB Device(s) disconnected! Switch to BT prevented by lock." \
                                  if self.mode_type == "USB_DIRECT" else \
                                  f"{config.HYBRID_DEVICE} disconnected! Switch to BT prevented by lock."
                            self._root.after(0, lambda m=msg: self.gui_callback("TOAST", {"message": m, "color": "red"}))
                         self._usb_disconnect_warning_shown = True
                else:
                    self._user_declined_usb_switch = False
                    self._usb_disconnect_warning_shown = False
                    self.kill_receivemidi()
                    if self._root and self._root.winfo_exists():
                        self._root.after(0, lambda: self.gui_callback("TRIGGER_FAILOVER"))
                    return
            else:
                 self._usb_disconnect_warning_shown = False
            # --- End Failover Logic ---


            # --- Failback Logic (BT Mode check) ---
            if self.mode_type == "BT":
                if usb_devices_present: # Only check for failback if *both* are back
                    if self._usb_stable_start_time is None:
                        self._usb_stable_start_time = time.time()
                        if self._root and self._root.winfo_exists():
                             self._root.after(0, lambda: self.gui_callback("TOAST", {"message": "USB devices detected. Checking for stability...", "color": "#303030"}))
                    elif (time.time() - self._usb_stable_start_time) >= 10:
                        self._usb_stable_start_time = None

                        if usb_lock_active or self._user_declined_usb_switch:
                            if self._root and self._root.winfo_exists():
                                 self._root.after(0, lambda: self.gui_callback("TOAST", {"message": "USB devices available, but switch declined/locked.", "color": "#303030"}))
                        else:
                            if self._root and self._root.winfo_exists():
                                self._root.after(0, lambda: self.gui_callback("TRIGGER_FAILBACK_POPUP"))
                            return # Stop monitoring as relaunch *might* be pending
                else:
                    self._usb_stable_start_time = None
                    self._user_declined_usb_switch = False
            # --- End Failback Logic ---

        except Exception as e:
            print(f"Device check failed: {e}")
            traceback.print_exc()
            if self._root and self._root.winfo_exists():
                 self._root.after(0, lambda: self.gui_callback("TOAST", {"message": f"Device check failed: {e}", "color": "red"}))

        if self._root and self._root.winfo_exists():
            self._root.after(5000, self._monitor_midi_device)

    def set_user_declined_switch(self, value):
        self._user_declined_usb_switch = value
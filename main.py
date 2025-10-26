import sys
import os
import time
import traceback

# --- !! FIX: Set Working Directory !! ---
# Get the directory where this script, main.py, is located
try:
    SCRIPT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    # Change the current working directory to that directory
    os.chdir(SCRIPT_DIRECTORY)
except Exception as e:
    # If this fails, we can't do anything.
    print(f"FATAL: Could not change working directory. Error: {e}")
    input("Press ENTER to exit.")
    sys.exit()
# --- !! END FIX !! ---


# --- !! DEBUGGER v3 !! ---
LOG_FILE_PATH = os.path.join(SCRIPT_DIRECTORY, "debug_log.txt")

# Clear the log file on each new run
if os.path.exists(LOG_FILE_PATH):
    os.remove(LOG_FILE_PATH)

def write_log(message):
    """Appends a message to the log file with a timestamp."""
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            f.write(f"[{timestamp}] [main.py] {message}\n")
    except Exception as e:
        print(f"FATAL: Could not write to log file: {e}")
        print(message)

# --- SCRIPT EXECUTION STARTS NOW ---
write_log("--- SCRIPT LAUNCHED ---")
write_log(f"Python Executable: {sys.executable}")
write_log(f"Python Version: {sys.version}")
write_log(f"Script Path: {os.path.abspath(__file__)}")
write_log(f"NEW: Working directory has been FORCED to: {os.getcwd()}") # Verification


try:
    write_log("Attempting to import 'tkinter' as 'tk'...")
    import tkinter as tk
    write_log("SUCCESS: Imported 'tkinter'.")

    write_log("Attempting to import 'config'...")
    import config
    write_log("SUCCESS: Imported 'config'.")

    write_log("Attempting to import 'gui.app'...")
    from gui import app
    write_log("SUCCESS: Imported 'gui.app'.")

    write_log("Attempting to import 'gui.popups'...")
    from gui import popups
    write_log("SUCCESS: Imported 'gui.popups'.")

    write_log("All initial imports seem successful.")

    def main():
        write_log("--- main() FUNCTION STARTED ---")

        # 1. Load config
        write_log("main(): 1. Loading config...")
        conf = config.load_config()
        write_log(f"main(): Config loaded. 'relaunch_on_monitor_fail' is: {conf.get('relaunch_on_monitor_fail')}")

        # 2. Set debug state
        write_log("main(): 2. Setting debug state in environment...")
        debug_state = conf.get("debug_enabled", False)
        os.environ["MIDI_DEBUG_ENABLED"] = str(debug_state)
        write_log(f"main(): MIDI_DEBUG_ENABLED set to: {debug_state}")

        # 3. Create root window
        write_log("main(): 3. Creating main tk.Tk() root window...")
        root = tk.Tk()
        write_log("main(): Root window created.")
        write_log("main(): Hiding root window for popups...")
        root.withdraw()
        write_log("main(): Root window hidden.")

        # 4. Show setlist chooser
        write_log("main(): 4. Calling popups.show_setlist_chooser()... (Script will pause here)")
        popups.show_setlist_chooser(root)
        write_log("main(): popups.show_setlist_chooser() FINISHED.")

        # 4b. Show device chooser
        write_log("main(): 4b. Calling popups.show_device_chooser()... (Script will pause here)")
        popups.show_device_chooser(root)
        write_log("main(): popups.show_device_chooser() FINISHED.")

        # 5. Un-hide root
        write_log("main(): 5. De-iconifying (showing) root window...")
        root.deiconify()
        write_log("main(): Root window is now visible.")

        # 6. Create main app
        write_log("main(): 6. Initializing gui.app.MidiSenderApp()...")
        main_app = app.MidiSenderApp(root)
        write_log("main(): MidiSenderApp initialized successfully.")

        # 7. Run main loop
        write_log("main(): 7. Starting root.mainloop()... (Application is now running)")
        root.mainloop()
        write_log("main(): root.mainloop() has finished. (Application was closed)")
        write_log("--- SCRIPT FINISHED NORMALLY ---")

    # This is the main entry point
    if __name__ == "__main__":
        write_log("Script is being run as __main__.")
        write_log("Calling main()...")
        main()

except Exception as e:
    # --- !! THIS IS THE CRASH HANDLER !! ---
    write_log("--- SCRIPT CRASHED! ---")
    write_log("An unhandled exception occurred. See traceback below.")
    write_log("\n" + "="*50 + "\n")
    
    # Log the full traceback to the file
    error_trace = traceback.format_exc()
    write_log(error_trace)
    
    write_log("\n" + "="*50 + "\n")
    write_log("--- END OF TRACEBACK ---")
    
    # Also try to print to console and pause, just in case
    print("--- SCRIPT CRASHED! ---")
    print(f"Error details have been written to debug_log.txt")
    traceback.print_exc()
    input("Press ENTER to close this window...")
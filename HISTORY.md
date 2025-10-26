# Revisions & Changes

This document outlines the key functional and structural changes made to the `SendMidiGui` application.

## VERSION 2.0.x
DATE: 2025-10-26

This version represents a major architectural overhaul, refactoring the original monolithic script into a modular, class-based application for improved maintainability, readability, and stability.

---

## I. Major Refactoring and Code Structure

These changes fundamentally alter how the application is organized and managed.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **Modular Codebase** | Split the single `SendMidiGui.py` file into multiple, dedicated files (`main.py`, `config.py`, `utils.py`, `midi_manager.py`) and a `gui` package (`gui/app.py`, `gui/popups.py`). | Dramatically improved **readability**, **maintainability**, and **testability**. Makes it easier to locate and modify specific parts of the application without affecting others. ✨ |
| **Class-Based Architecture** | Introduced `MidiManager` class to encapsulate all MIDI device interaction, process management (sendmidi/receivemidi), and monitoring logic. Introduced `MidiSenderApp` class to manage the main GUI state and lifecycle. | Replaced heavy reliance on **global variables** with instance attributes, leading to better state management and reduced potential for conflicts. Clearer separation of backend logic and frontend presentation. 🏗️ |
| **Separation of Concerns** | Isolated configuration constants and paths (`config.py`), non-GUI helper functions (`utils.py`), MIDI backend logic (`midi_manager.py`), startup GUI prompts (`gui/popups.py`), and the main application window (`gui/app.py`). | Enhances code organization, making the project easier to understand, debug, and extend. |
| **Refined Startup Process** | Centralized application entry point in `main.py`. Moved initial setlist and device selection into popups managed by `gui/popups.py`, which run before the main `MidiSenderApp` GUI is fully initialized and shown. | Provides a cleaner, more controlled application launch sequence. Handles relaunch logic (e.g., after monitor fail) more explicitly. 🚀 |

---

## II. GUI and User Experience

Improvements focused on visual feedback and interaction stability.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **MIDI Activity Toasts** | Added short-duration (250ms), yellow toast notifications in the **top-right corner** indicating "SENDING" or "RECEIVING" MIDI data activity. | Provides immediate, non-intrusive visual feedback when MIDI operations occur. 🚦 |
| **Thread-Safe GUI Updates** | Modified the `show_toast` function to ensure all GUI updates are safely executed on the main Tkinter thread, even when triggered from background threads (MIDI sending/monitoring). | Ensures GUI stability during MIDI operations. 👍 |
| **Corrected Toast Placement & Visibility** | Adjusted toast message placement logic to ensure visibility in the intended top-right location above other elements. | Improves the usability of the MIDI activity feedback. ✅ |

---

## VERSION 1.1.x
DATE: 2025-10-25

## I. USB Lock and Monitoring Reliability

These changes directly address the core issue of continuous monitoring and user control over automatic switching.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **USB Failover Lock** | Added a global state (`usb_lock_active`) and a new **checkbox** in the main GUI to **activate** or **deactivate** the lock. | Allows the user to prevent the automatic failover (USB to BT) and failback (BT to USB) prompts from appearing, keeping the session uninterrupted while still **monitoring** the USB devices. |
| **Continuous Monitoring Fix** | Restructured the `monitor_midi_device` logic to ensure the `root.after(5000, monitor_midi_device)` call executes **every time** at the end of the function, unless a full application restart is triggered. | Guarantees that the application never stops monitoring, regardless of the lock state or device presence. |
| **Dynamic Lock Checkbox** | The lock **checkbox** now changes color based on the `usb_lock_active` state and the current **presence of the required USB devices** (`Morningstar MC8 Pro` and `Quad Cortex MIDI Control`). | Provides instant visual feedback on USB device status and lock state. |

## II. Connection Mode Enhancements

The flexibility and persistence of device modes were significantly improved.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **Hybrid USB Mode** | Introduced a new connection constant (`HYBRID_DEVICE`) and mode option during initial launch and within the new mode selection popup. | Implements **dynamic routing** for Channel 1 MIDI commands (Quad Cortex). If the `Quad Cortex MIDI Control` device is present, commands are sent to it directly. If it is **not** present, Channel 1 commands are automatically **rerouted to the Morningstar MC8 Pro** (`HYBRID_DEVICE`), allowing for failover without losing functionality. |
| **Manual Mode Switching** | Added a **"Switch Mode"** button and popup to the main GUI. | Allows the user to manually switch between Bluetooth, USB Direct, and Hybrid USB modes **without restarting the application**. |

## III. Quality of Life and Stability

Minor, but important, additions for a better user experience.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **Declined Failback Tracking** | Added a flag (`user_declined_usb_switch`) to track when a user declines the automatic failback to USB. | Prevents the failback prompt from continuously popping up once a user has chosen to remain on Bluetooth for the current session. |
| **Improved Config Saving** | The `usb_lock_active` state is now saved to `config.json` **immediately when the lock checkbox is toggled** by the user (via the checkbox's `command`). | The USB Lock state is reliably persistent across application restarts. |

---

## VERSION 1.0
Date: 2025-06-15

ORIGINAL RELEASE

---

END
# SendMidiGui - MIDI Patch Sender

**Current Version:** 2.0 (Released 2025-10-26)
**Previous Stable:** 1.1.x (Released 2025-10-25)

This is a dynamic Python-based graphical user interface (GUI) designed for musicians to quickly send MIDI Program Change (PC) and Control Change (CC) messages to connected MIDI devices, with a focus on seamless switching between **Bluetooth** (WIDI/loopMIDI) and **USB** (Morningstar MC8/Quad Cortex) connections.

---

## ✨ What's New in Version 2.0 ✨

This version is a significant **architectural overhaul** aimed at improving stability, maintainability, and user experience.

* **Modular Codebase:** The application has been refactored from a single script into multiple modules (`main.py`, `config.py`, `utils.py`, `midi_manager.py`, `gui/app.py`, `gui/popups.py`). This makes the code easier to understand, maintain, and extend. 🏗️
* **Class-Based Structure:** Core logic is now managed by classes (`MidiManager`, `MidiSenderApp`), improving state management and reducing reliance on global variables.
* **MIDI Activity Indicator:** A small, temporary yellow **toast message** now appears in the top-right corner indicating "SENDING" or "RECEIVING" MIDI data for quick visual feedback. 🚦
* **Improved Startup:** A cleaner startup sequence with dedicated popups for setlist and device selection *before* the main window appears.
* **Enhanced Stability:** Numerous underlying fixes to address Tkinter quirks, threading issues, and potential crashes during startup, shutdown, and mode switching. 👍

*(For a detailed breakdown of specific feature changes, see `HISTORY.md`)*

---

## Key Features (Including Previous Versions)

* **Dynamic Patch Loading:** Loads MIDI patches from a central `MidiList-DEFAULT.csv` or a specific setlist file.
* **Connection Mode Selection:** Prompt at launch to select **Bluetooth**, **USB Direct**, or **Hybrid USB** mode.
* **Manual Mode Switching:** Switch between modes (BT, USB Direct, Hybrid) during runtime without restarting the application using the "Switch Mode" button.
* **Automatic Failover (USB to BT):** If a USB device disconnects while in a USB-based mode (and the lock is off), the application prompts and automatically relaunches in the stable **Bluetooth** mode.
* **Automatic Failback (BT to USB):** If stable USB connection is re-detected while in **Bluetooth** mode (and the lock is off), the application prompts to switch back to **USB Direct** mode.
* **USB Failover/Failback Lock:** A lock checkbox in the main GUI to **disable** the automatic failover/failback prompts, allowing continuous USB monitoring without interrupting the current session. The lock state is saved in `config.json`.
* **Hybrid Mode Routing:** In Hybrid mode, MIDI Channel 1 commands are automatically rerouted to the Morningstar MC8 if the Quad Cortex MIDI Control port is unavailable.
* **Setlist Management:** Load predefined setlist files (`.txt`) from the `Setlist` folder to quickly reorder and filter patches. Switch setlists via the "Choose Setlist" button.
* **Debug Logging Toggle:** A checkbox in the main GUI allows enabling/disabling detailed MIDI command logging to the console for troubleshooting.

---

## 🛠️ Setup and Requirements

### Dependencies

1.  **Python 3:** The script requires a Python 3 installation.
2.  **sendmidi and receivemidi:** The external command-line tools `sendmidi.exe` and `receivemidi.exe` are required. Place them in their respective subfolders (`sendmidi/` and `receivemidi/`).
    * Find these tools here: [SendMIDI](https://github.com/gbevin/SendMIDI) and [ReceiveMIDI](https://github.com/gbevin/ReceiveMIDI).
3.  **Required MIDI Ports (Examples):**
    * `loopMIDI Port` (or equivalent Bluetooth virtual port) for **Bluetooth (Default)** mode.
    * `Morningstar MC8 Pro` for **USB Direct** and **Hybrid USB** modes.
    * `Quad Cortex MIDI Control` for proper MIDI routing in USB-based modes.

### Recommended File Structure

Place all files in a dedicated folder, ensuring the following structure:

SendMidiGui_Project/ ├── sendmidi/ │ └── sendmidi.exe ├── receivemidi/ │ └── receivemidi.exe ├── Setlist/ │ └── YourSetlist.txt │ ├── gui/ │ ├── init.py <-- (Empty file) │ ├── app.py │ └── popups.py │ ├── main.py <-- Run this file to start the application ├── config.py ├── utils.py ├── midi_manager.py ├── MidiList-DEFAULT.csv <-- Master list of all available patches ├── sendmidi.ico <-- (Optional) Window icon ├── config.json <-- (Auto-generated) Stores last used settings ├── HISTORY.md └── README.md <-- This file
*(`MidiList.csv` is auto-generated based on the chosen setlist or default)*

---

## ⚙️ Configuration

### 1. MIDI Commands (`MidiList-DEFAULT.csv`)

The core functionality relies on this CSV file. Each row defines a patch button.

| Column          | Description                                               | Example Value    |
| :-------------- | :-------------------------------------------------------- | :--------------- |
| **Patch Label** | Name displayed on the button.                             | `DRIVE (JCM800)` |
| **PC Ch1 (QC)** | Program Change number for MIDI Channel 1 (Quad Cortex).   | `3`              |
| **PC Ch2 (MC8)**| Program Change number for MIDI Channel 2 (Morningstar MC8). | `5`              |
| **CC Ch1** | Optional: CC Channel.                                     | `1`              |
| **CC Num** | Optional: CC Number.                                      | `47`             |
| **CC Val** | Optional: CC Value.                                       | `1`              |
| *(repeat)* | *Additional CC commands (Ch, Num, Val)* | ...              |

### 2. Setlist Files (`Setlist/*.txt`)

Create plain text files (`.txt`) in the `Setlist` folder.

1.  The **first line** is used as the display name for the setlist.
2.  Subsequent lines are the **exact patch labels** (case-insensitive match) from `MidiList-DEFAULT.csv`, in the desired order. Patches not found will be marked.

### 3. Application Settings (`config.json`)

This file is automatically generated and updated. It stores:
* Last used MIDI device/mode.
* Path to the last used CSV file (`MidiList.csv` or a temporary setlist CSV).
* The display name of the current setlist.
* The state of the USB Lock checkbox.
* The state of the Debug Logging checkbox.

---

## 🏃 Usage

1.  **Run the script:** Execute `main.py` (e.g., `python main.py` or double-click if associated).
2.  **Load Setlist:** A prompt will appear asking to load a Setlist or the Default songs.
3.  **Select Mode:** Choose your preferred connection mode (**Bluetooth**, **USB Direct**, or **Hybrid**).
4.  **Main GUI:** The main application window will appear (typically positioned on the right side of your primary screen).
5.  **Click to Send:** Click a patch button to send the corresponding MIDI commands. A quick yellow "SENDING" toast will appear top-right. If using `receivemidi`, a "RECEIVING" toast appears on activity.
6.  **USB Lock:** Click the "Lock USB/Autoswitch" checkbox to enable/disable automatic failover/failback prompts. Its color indicates USB device status (Green=Connected, Red=Disconnected [in USB modes], Default=Disconnected [in BT mode]).
7.  **Debug Toggle:** Click the "Debug" checkbox to enable/disable printing detailed MIDI commands to the console/terminal where you ran the script.
8.  **Switch Modes/Setlists:** Use the buttons ("Switch Mode", "Choose Setlist") to change configuration during runtime.

The mode display at the top-left of the GUI shows the currently active MIDI mode and routing status (in Hybrid mode).
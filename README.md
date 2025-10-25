# 🚀 MIDI Patch Sender GUI (Original Version)

VERSION: 1.0
DATE:    2025-06-15

This is the initial version of the Python-based graphical user interface (GUI) designed to send MIDI Program Change (PC) and Control Change (CC) messages, with automated switching between **Bluetooth** and **USB Direct** connections.

---

## ✨ Key Features

* **Core MIDI Control:** Loads MIDI patches from a central `MidiList.csv` or a specific setlist file and displays them as clickable buttons.
* **Dual Connection Modes:** Supports two primary modes:
    * **Bluetooth (Default):** Sends MIDI to `loopMIDI Port`.
    * **USB Direct:** Sends MIDI to `Morningstar MC8 Pro` (with specialized routing for Quad Cortex via Channel 1).
* **Automatic Failover (USB to BT):** If the USB device disconnects while in **USB Direct** mode, the application prompts the user and automatically relaunches in the stable **Bluetooth** mode.
* **Automatic Failback (BT to USB):** If a stable USB connection is detected while in **Bluetooth** mode, the application prompts the user to switch back to the **USB Direct** mode.
* **Setlist Management:** Prompts at launch to load predefined setlist files (`.txt`) from the `Setlist` folder to reorder and filter patches.

---

## 🛠️ Setup and Requirements

### Dependencies

1.  **Python 3:** The script requires a Python 3 installation.
2.  **sendmidi:** The external command-line tool `sendmidi.exe` is required to communicate with MIDI ports.

### Required MIDI Ports

The script monitors for and sends to the following devices:

* `loopMIDI Port` (or equivalent Bluetooth virtual port) for **Bluetooth (Default)** mode.
* `Morningstar MC8 Pro` for **USB Direct** mode.
* `Quad Cortex MIDI Control` (Monitored for stability and used for Channel 1 routing).

### Recommended File Structure

Place all files in a dedicated folder:

/Midi-Sender-App/
├── SendMidiGui.py        <-- The main script
├── MidiList-DEFAULT.csv  <-- Master list of all available patches
├── sendmidi.exe          <-- The external MIDI sender tool
├── sendmidi.ico          <-- (Optional) Window icon
├── config.json           <-- (Auto-generated) Stores last used settings
├── Setlist/              <-- Folder for custom setlist files
│   └── Practice-Set.txt
└── MidiList.csv          <-- (Auto-generated) The currently active CSV

---

## ⚙️ Configuration

### 1. MIDI Commands (`MidiList-DEFAULT.csv`)

Each row in the CSV defines a patch button.

| Column | Description | Example Value |
| :--- | :--- | :--- |
| **Patch Label** | Name displayed on the button. | `DRIVE (JCM800)` |
| **PC Ch1 (QC)** | Program Change number for MIDI Channel 1 (Quad Cortex). | `3` |
| **PC Ch2 (MC8)** | Program Change number for MIDI Channel 2 (Morningstar MC8). | `5` |
| **CC Ch1** | Optional: CC Channel. | `1` |
| **CC Num** | Optional: CC Number. | `47` |
| **CC Val** | Optional: CC Value. | `1` |

* Additional CC commands can be appended in sets of three (Ch, Num, Val).

### 2. Setlist Files (`Setlist/*.txt`)

Create a plain text file (`.txt`) in the `Setlist` folder.

1.  The **first line** is used as the display name for the setlist.
2.  Subsequent lines are the **exact patch labels** (case-insensitive match) you want from `MidiList-DEFAULT.csv`, in the desired order.

---

## 🏃 Usage

1.  **Run the script:** Double-click `SendMidiGui.py`.
2.  **Load Setlist:** A prompt will appear asking to load a Setlist or the Default songs.
3.  **Select Mode:** Choose between **Bluetooth (Default)** or **USB Direct**.
4.  **Main GUI:** The application window will launch.
5.  **Click to Send:** Click a patch button to send the corresponding MIDI commands.
6.  **Automatic Mode Switching:** The application constantly monitors the USB connection. If a device connects or disconnects, an automatic prompt will appear on your screen, offering to switch connection modes or confirming the automatic failover.
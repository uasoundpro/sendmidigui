# 🚀 MIDI Patch Sender GUI

REVISION: 1.1.x
DATE:     2025-10-25

This is a dynamic Python-based graphical user interface (GUI) designed for musicians to quickly send MIDI Program Change (PC) and Control Change (CC) messages to connected MIDI devices, with a focus on seamless switching between **Bluetooth** (WIDI/loopMIDI) and **USB** (Morningstar MC8/Quad Cortex) connections.

---

## ✨ Key Features

* **Dynamic Patch Loading:** Loads MIDI patches from a central `MidiList.csv` or a specific setlist file.
* **Connection Mode Selection:** Prompt at launch to select **Bluetooth**, **USB Direct**, or **Hybrid USB** mode.
* **Automatic Failover (USB to BT):** If a USB device disconnects while in a USB-based mode, the application prompts and automatically relaunches in the stable **Bluetooth** mode.
* **Automatic Failback (BT to USB):** If stable USB connection is re-detected while in **Bluetooth** mode, the application prompts to switch back to the last preferred USB mode.
* **USB Failover Lock:** A lock button in the main GUI to **disable** the automatic failover/failback prompts, allowing continuous USB monitoring without interrupting the current session.
* **Manual CH1 Reroute Override (Hybrid Mode):** A checkbox to manually force MIDI Channel 1 messages to reroute to the Channel 2 device, even when the primary Channel 1 device is detected.
* **Setlist Management:** Load predefined setlist files (`.txt`) from the `Setlist` folder to quickly reorder and filter patches.

---

## 🛠️ Setup and Requirements

### Dependencies

1.  **Python 3:** The script requires a Python 3 installation.
2.  **sendmidi and receivemidi:** The external command-line tools `sendmidi.exe` and "receivemidi.exe" are required to communicate with MIDI ports. You can find this FANTASTIC pair of programs here, none of this would be functionally possible without it: https://github.com/gbevin/SendMIDI and https://github.com/gbevin/ReceiveMIDI - simply add the executables to the folder where the main Python script lives.
3.  **Required MIDI Ports:**
    * `loopMIDI Port` (or equivalent Bluetooth virtual port) for **Bluetooth (Default)** mode.
    * `Morningstar MC8 Pro` for **USB Direct** and **Hybrid USB** modes.
    * `Quad Cortex MIDI Control` for proper MIDI routing in USB-based modes.

### Recommended File Structure

Place all files in a dedicated folder, ensuring the following structure:

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

The core functionality relies on the CSV file. Each row defines a patch button.

| Column          | Description                                                    | Example Value    |
| :-------------- | :------------------------------------------------------------- | :--------------- |
| **Patch Label** | Name displayed on the button.                                  | `DRIVE (JCM800)` |
| **PC Ch1 (QC)** | Program Change number for MIDI Channel 1 (Quad Cortex).        | `3`              |
| **PC Ch2 (MC8)**| Program Change number for MIDI Channel 2 (Morningstar MC8).    | `5`              |
| **CC Ch1** | Optional: CC Channel.                                          | `1`              |
| **CC Num** | Optional: CC Number.                                           | `47`             |
| **CC Val** | Optional: CC Value.                                            | `1`              |

* Additional CC commands can be appended in sets of three (Ch, Num, Val).

### 2. Setlist Files (`Setlist/*.txt`)

Create a plain text file (`.txt`) in the `Setlist` folder.

1.  The **first line** is used as the display name for the setlist.
2.  Subsequent lines are the **exact patch labels** (case-insensitive match) you want from `MidiList-DEFAULT.csv`, in the desired order.

---

## 🏃 Usage

1.  **Run the script:** Double-click `SendMidiGui.py`.
2.  **Load Setlist:** A prompt will appear asking to load a Setlist or the Default songs.
3.  **Select Mode:** Choose your preferred connection mode (**Bluetooth**, **USB Direct**, or **Hybrid**).
4.  **Main GUI:** The main application window will appear on the side of your screen.
5.  **Click to Send:** Click a patch button to send the corresponding MIDI commands.
6.  **USB Failover Lock:** Click the **Lock USB/Autoswitch** checkbox to **disable** the automatic failover/failback prompts. The monitoring loop continues running regardless of the lock state.
7.  **Force CH1 Reroute (Hybrid Only):** Click the **Force CH1 Reroute (Hybrid)** checkbox to manually force Channel 1 messages to the Channel 2 device. This checkbox is only active in Hybrid mode.

The mode display at the top of the GUI shows the currently active MIDI port, and the checkbox colors dynamically indicate USB device presence and override status.

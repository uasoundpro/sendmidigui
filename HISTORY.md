# 🔄 History of Revisions & Changes

This document outlines the key functional and structural changes made to the `SendMidiGui.py` script, primarily focusing on the evolution of the MIDI connection management and control features.

## VERSION 1.1
DATE: 2025-10-25

## 🔒 I. USB Lock and Monitoring Reliability

These changes directly address the core issue of continuous monitoring and user control over automatic switching.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **USB Failover Lock** | Added a global state (`usb_lock_active`) and a new button in the main GUI to **activate** or **deactivate** the lock. | Allows the user to prevent the automatic failover (USB to BT) and failback (BT to USB) prompts from appearing, keeping the session uninterrupted while still **monitoring** the USB devices. |
| **Continuous Monitoring Fix** | Restructured the `monitor_midi_device` logic to ensure the `root.after(5000, monitor_midi_device)` call executes **every time**, even if failover/failback conditions are met but the **USB Lock is active**. | Guarantees that the application never stops monitoring, regardless of the lock state or device presence. |
| **Dynamic Lock Button** | The lock button now changes color based on the `usb_lock_active` state and the current **presence of the required USB devices** (`Morningstar MC8 Pro` and `Quad Cortex MIDI Control`). | Provides instant visual feedback on USB device status and lock state. |

## 🔌 II. Connection Mode Enhancements

The flexibility and persistence of device modes were significantly improved.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **Hybrid USB Mode** | Introduced a new connection constant (`HYBRID_DEVICE`) and mode option during initial launch and within the new mode selection popup. | Offers a third connection option that sends **all MIDI commands to the Morningstar MC8 Pro** device, simplifying routing when specialized Quad Cortex Channel 1 routing is not desired. |
| **Persistent Last USB Mode** | Added logic to save the last selected USB-based mode (`last_usb_device`) in `config.json`. | Ensures that when the system fails back from Bluetooth to USB, it intelligently switches to the user's last preferred USB mode (either **USB Direct** or **Hybrid USB**). |
| **Manual Mode Switching** | Added a **"Switch Mode"** button and popup to the main GUI. | Allows the user to manually switch between Bluetooth, USB Direct, and Hybrid USB modes **without restarting the application**. |

## 💡 III. Quality of Life and Stability

Minor, but important, additions for a better user experience.

| Feature | Change Description | Impact |
| :--- | :--- | :--- |
| **Declined Failback Tracking** | Added a flag (`user_declined_usb_switch`) to track when a user declines the automatic failback to USB. | Prevents the failback prompt from continuously popping up once a user has chosen to remain on Bluetooth for the current session. |
| **Improved Config Saving** | Ensured that the `usb_lock_active` state is saved to `config.json` immediately before the application closes or re-launches. | The USB Lock state is reliably persistent across application restarts. |

---

## VERSION 1.0
Date: 2025-06-15

ORIGINAL RELEASE

---

END
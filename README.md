# ha_emerald_electricity_advisor ⚡

![Home Assistant](https://img.shields.io/badge/Home_Assistant-Custom_Component-blue?logo=home-assistant)

This is a custom Home Assistant integration to locally track real-time power consumption, long-term energy accumulation, and battery levels from the Emerald Electricity Advisor via Bluetooth Low Energy (BLE).

**Created by copilot and debugged by Gemini.**

<image src="/docs/Screenshot_20260517-135600.png" /> <image src="/docs/Screenshot_20260517-142433.png" /> <image src="/docs/Screenshot_20260517-142458.png" /> <image src="/docs/Screenshot_20260517-142515.png" />

## Installation 

## ⚠️ Critical Prerequisite: Mobile App Contention
The Emerald Electricity Advisor hardware only supports **one active Bluetooth connection at a time**. 

Before setting up this integration, you **must** sever the connection to your mobile devices:
1. Close the official Emerald EMS app on your phone/tablet.
2. Go to your phone/tablet's main OS Settings and completely disable Bluetooth permissions for the Emerald app. 
3. Go outside and press the physical button on the Advisor to wake it up and flush any ghost connections from its memory.

If you skip this step, Home Assistant will fail to connect.

---

## 🛠️ Step 1: The 1-Time SSH Setup (Pairing & Trusting)

Because Home Assistant's underlying Python Bluetooth library (`bleak`) does not support programmatic PIN entry, you **must** pair the device directly to your host Linux operating system (BlueZ) one time using an SSH terminal. **You must do this before installing the integration.**

### Step-by-Step Instructions

**1. Wake the device**
Go outside and press the button on the front of the Emerald Advisor so it broadcasts brightly.

**2. Open your SSH terminal**
SSH into your Home Assistant host machine and launch the Bluetooth utility:
```bash
bluetoothctl
```

**3. Enable the pairing agent**
Turn on the agent so Linux knows to route the PIN prompt to your keyboard:
```bash
agent on
default-agent
```

**4. Find your Advisor's MAC Address**
```bash
scan on
```
*Watch the text scroll until you see your device's MAC address (e.g., `30:1B:97:69:FF:88`). Once you see it, stop the scanner:*
```bash
scan off
```

**5. Initiate the Pair**
```bash
pair <YOUR_MAC_ADDRESS>
```
*The terminal will pause and ask you for the passkey. Type your 6-digit Emerald passkey and hit `Enter`.*

**6. The Critical Final Step (Trusting)**
Once the terminal says "Pairing successful", you must tell Linux to remember it forever so it automatically applies the encryption keys on future reboots:
```bash
trust <YOUR_MAC_ADDRESS>
```

**7. Release the Radio Slot**
Disconnect the terminal session so Home Assistant can claim the active Bluetooth channel:
```bash
disconnect <YOUR_MAC_ADDRESS>
```

**8. Exit**
```bash
exit
```

---

## 📦 Step 2: Installation

### HACS (Recommended)
1. Open HACS in Home Assistant.
2. Go to **Integrations** -> click the three dots in the top right -> **Custom repositories**.
3. Add the URL of this repository and select **Integration** as the category.
4. Click **Install**.
5. Restart Home Assistant.

### Manual Installation
1. Download the `custom_components/emerald_electricity_advisor` directory from this repository.
2. Copy it into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.

---

## ⚙️ Step 3: UI Setup

⚠️ For the smoothest setup, ensure you've connected and trusted the device prior to setting up the integration within home assistant.

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** and search for **Emerald Electricity Advisor**.
3. Enter your MAC address, Passkey, and Pulses per kWh when prompted.
4. Click Submit.




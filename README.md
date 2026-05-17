# ha_emerald_electricity_advisor
This is a custom HA integration for Emerald Electricity Advisor. Created by copilot and debigged by Gemini . Alpha version 0.01 USE WITH CAUTION


To use this integration, you have to manually pair the device using the OS. I did this in the terminal using the following steps

## The 1-Time SSH Setup

Wake the device: Go outside and press the button on the Emerald Advisor so it broadcasts brightly.
Open your SSH terminal into Home Assistant and type:

bluetoothctl

Turn on the pairing agent so Linux knows to route the PIN prompt to your keyboard:

agent on
default-agent

Find the Advisor:

scan on

(Watch the text scroll until you see your device's MAC address. Once you see it, stop the spam by typing:)

scan off

Initiate the Pair:

pair <<mac address>>

The terminal will pause and ask you for the passkey. Type <<your passkey>> and hit Enter.

The Critical Final Step (Trusting):

Once it says "Pairing successful", you must tell Linux to remember it forever so it automatically applies the keys on future reboots. Type:

trust <<mac address>>

Disconnect the slot:

disconnect <<mac address>>

Exit the utility:

exit

# Files shit



- `main.py`: Script to run the GUI
- `config_dialog.py`: Popup window when you start the GUI to choose your servo configuration (start from default or load from config; the `eye-setup.json` was the one used for tech fest if you wanna continue using it)
- `esp-code-2.txt`: Arduino code that runs on the ESP32 to control the servos (already  uploaded)

## Core 
- `state_manager.py`: Keeps track of all servo settings and handles changes to update the GUI
- `event_system.py`: handles events between different parts of the GUI when things change; i.e changing name of min max ranges or sliding controls etc...
- `validation.py`: Checks if user inputs are valid before doing anything with them
- `facial_tracking_v2_blink.py`: Tracks faces with the camera and moves the eye servos to follow them with blinking (daniels vers; `facial_tracking.py` is older version)

## Hardware

- `esp_communication.py`: Sends serial commands and monitors CPU usage. The two serial commands are:
    - **SP:servo_index:pulse_width** sends pulse width signal to assigned pin from GUI
    - **NUM_SERVOS:number** intialises number of active servos (this is not really important)
     
- `servo_config.py`: Stores the default dictionary and configuration of the components and how many servos in each component. When you configure individual servos it updates this dictionary and saves and loads in the same format


## GUI Components

- `main_window.py`: Creates the main window and everything...
- `servo_controls.py`: Creates the slider controls for each servo and handles updating the servo configurations
- `command_interface.py`: The terminal where you can enter commands to move servo or record sequences etc...click the help button in the gui to see commands and how to use them
- `sequence_system.py`: Records sequences of all servos; for now I have set the max duration for a sequence to be 120 seconds, but you can easily change it in `validation.py` from the variable `MAX_SEQUENCE_DURATION`
- `eye_display.py`: Shows camera feed and manages camera switching for the robot eyes




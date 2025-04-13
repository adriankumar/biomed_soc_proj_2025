import tkinter as tk
from tkinter import ttk
from serial_connection import SerialConnection
from single_controls import SingleControls
from sequence_recorder import SequenceRecording
from config_setup import run_config_setup

class ServoControlApp:
    def __init__(self, root, config):
        self.root = root
        self.num_servos = config["num_servos"] #store num servos
        
        #main window
        self.root.title("Servo Control System")
        self.root.geometry("1000x700")

        self.sequence_dictionary = {} #sequence dictionary to be passed between files for modification
        self._create_main_ui() #create layout
    
    #-----------------------------------------------------------------------
    #create main ui
    #-----------------------------------------------------------------------
    def _create_main_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        #create console log
        self._create_console_log(main_frame)
        
        #serial connection section
        self.serial_connection = SerialConnection(
            main_frame,
            send_callback=self.log_message
        )
        self.serial_connection.frame.pack(fill="x", pady=5)
        
        #for splitting controls and sequence recording - may need to modify in future to a different window because displaying all 30 vertically can only be seen by wider screens....
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        #servo slider controls
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        #may need to modify in future to a different window because displaying all 30 vertically can only be seen by wider screens....
        self.single_controls = SingleControls( 
            left_frame,
            self.num_servos, #might make dynamic where we refresh the display everytime the user enters a servo num in serial connection area so display updates to those servos but may need to clear all recorded sequences for house keeping
            send_command_callback=self.send_serial_command
        )
        self.single_controls.frame.pack(fill="both", expand=True)
        
        #sequence recording controls
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.sequence_recording = SequenceRecording(
            right_frame,
            self.num_servos,
            get_servo_angles_callback=self.get_current_servo_angles,
            send_command_callback=self.send_serial_command
        )
        self.sequence_recording.frame.pack(fill="both", expand=True)
        
        if self.serial_connection.is_connected: #need to remove this from create main ui and move to serial connnection
            self.send_serial_command(f"NUM_SERVOS:{self.num_servos}")
    
    #need to fix this display
    def _create_console_log(self, parent):
        console_frame = ttk.LabelFrame(parent, text="Console Log")
        console_frame.pack(fill="x", side="bottom", pady=5)
        
        self.console = tk.Text(console_frame, height=6, width=50, state="disabled")
        self.console.pack(fill="x", padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.console, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        
        self.console.config(yscrollcommand=scrollbar.set)
    
#-----------------------------------------------------------------------
#utility methods: log, send_serial, get_current_servo_angles
#-----------------------------------------------------------------------
    def log_message(self, message): #add message to console log to record actions or debug statements via gui
        self.console.config(state="normal")
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")
    
    def send_serial_command(self, command): #send the serial commands (angles, sequences, playback, servos, etc)
        if not self.serial_connection.is_connected:
            self.log_message("Error: Not connected to serial port") #connect to serial port first
            return False
            
        #command is sent using serial connection's function which returns a boolean if it was successful or not
        result = self.serial_connection.send_command(command)
        
        if not result:
            self.log_message(f"Error sending command: {command}")
            
        return result
    
    def get_current_servo_angles(self):
        servo_positions = []
        
        for i in range(self.num_servos):
            angle = self.single_controls.servo_angles[i].get()
            
            servo_positions.append({
                "id": i,
                "name": f"Servo {i}",
                "position": angle
            })
            
        return servo_positions

#-----------------------------------------------------------------------
# start config and gui set up if config applied
#-----------------------------------------------------------------------
if __name__ == "__main__":
    config = run_config_setup() #run config (how many servos to initialise)
    
    if config["config_applied"]: #open gui control after num servos is specified
        root = tk.Tk()
        app = ServoControlApp(root, config) #pass config to get num of servos
        root.mainloop()
    else:
        print("Configuration cancelled. Exiting application")
import tkinter as tk
from tkinter import ttk

#import our modules
from serial_connection import SerialConnection
from single_controls import SingleControls
from sequence_recorder import SequenceRecording
from config_setup import run_config_setup

class ServoControlApp:
    def __init__(self, root, config):
        #store configuration
        self.root = root
        self.num_servos = config["num_servos"]
        self.global_sf = config["global_sf"]
        
        #setup the main window
        self.root.title("Servo Control System")
        self.root.geometry("1000x700")
        
        #sequence dictionary for data persistence
        self.sequence_dictionary = {}
        
        #create main layout
        self._create_main_ui()
    
    #-----------------------------------------------------------------------
    #main ui creation
    #-----------------------------------------------------------------------
    def _create_main_ui(self):
        #create main content
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
        
        #content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        #servo controls section (left side)
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.single_controls = SingleControls(
            left_frame,
            self.num_servos,
            send_command_callback=self.send_serial_command,
            global_sf=self.global_sf
        )
        self.single_controls.frame.pack(fill="both", expand=True)
        
        #sequence controls section (right side)
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.sequence_recording = SequenceRecording(
            right_frame,
            self.num_servos,
            get_servo_angles_callback=self.get_current_servo_angles,
            send_command_callback=self.send_serial_command
        )
        self.sequence_recording.frame.pack(fill="both", expand=True)
          
        #send initial settings to hardware
        #only if connection is established
        if self.serial_connection.is_connected:
            #send number of servos
            self.send_serial_command(f"NUM_SERVOS:{self.num_servos-1}")
            
            #send global smoothing factor
            self.send_serial_command(f"GSF:{self.global_sf}")
    
    def _create_console_log(self, parent):
        console_frame = ttk.LabelFrame(parent, text="Console Log")
        console_frame.pack(fill="x", side="bottom", pady=5)
        
        self.console = tk.Text(console_frame, height=6, width=50, state="disabled")
        self.console.pack(fill="x", padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.console, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        
        self.console.config(yscrollcommand=scrollbar.set)
    
    #-----------------------------------------------------------------------
    #utility methods
    #-----------------------------------------------------------------------
    def log_message(self, message):
        #add message to console log
        self.console.config(state="normal")
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")
    
    def send_serial_command(self, command):
        #check connection
        if not self.serial_connection.is_connected:
            self.log_message("Error: Not connected to serial port")
            return False
            
        #send command
        result = self.serial_connection.send_command(command)
        
        if not result:
            self.log_message(f"Error sending command: {command}")
            
        return result
    
    def get_current_servo_angles(self):
        #collect all servo angles
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
#application entry point
#-----------------------------------------------------------------------
if __name__ == "__main__":
    #run configuration setup first
    config = run_config_setup()
    
    #only proceed if configuration was applied
    if config["config_applied"]:
        #create main application
        root = tk.Tk()
        app = ServoControlApp(root, config)
        root.mainloop()
    else:
        #user cancelled configuration, exit without creating main window
        print("Configuration cancelled. Exiting application.")
        #no need for explicit exit, program will end naturally
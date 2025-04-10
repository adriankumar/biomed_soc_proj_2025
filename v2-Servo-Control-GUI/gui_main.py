import tkinter as tk
from tkinter import ttk

# Import our modules
from serial_connection import SerialConnection
from single_controls import SingleControls
from sequence_recorder import SequenceRecording
from config_setup import run_config_setup

class ServoControlApp:
    def __init__(self, root, config):
        # Store configuration
        self.root = root
        self.num_servos = config["num_servos"]
        
        # Setup the main window
        self.root.title("Servo Control System")
        self.root.geometry("1000x700")
        
        # Sequence dictionary for data persistence
        self.sequence_dictionary = {}
        
        # Create main layout
        self._create_main_ui()
    
    # -----------------------------------------------------------------------
    # Main UI creation
    # -----------------------------------------------------------------------
    def _create_main_ui(self):
        # Create main content
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Create console log
        self._create_console_log(main_frame)
        
        # Serial connection section
        self.serial_connection = SerialConnection(
            main_frame,
            send_callback=self.log_message
        )
        self.serial_connection.frame.pack(fill="x", pady=5)
        
        # Content area
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        # Servo controls section (left side)
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.single_controls = SingleControls(
            left_frame,
            self.num_servos,
            send_command_callback=self.send_serial_command
        )
        self.single_controls.frame.pack(fill="both", expand=True)
        
        # Sequence controls section (right side)
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        self.sequence_recording = SequenceRecording(
            right_frame,
            self.num_servos,
            get_servo_angles_callback=self.get_current_servo_angles,
            send_command_callback=self.send_serial_command
        )
        self.sequence_recording.frame.pack(fill="both", expand=True)
          
        # Send initial settings to hardware
        # Only if connection is established
        if self.serial_connection.is_connected:
            # Send number of servos
            self.send_serial_command(f"NUM_SERVOS:{self.num_servos}")
    
    def _create_console_log(self, parent):
        console_frame = ttk.LabelFrame(parent, text="Console Log")
        console_frame.pack(fill="x", side="bottom", pady=5)
        
        self.console = tk.Text(console_frame, height=6, width=50, state="disabled")
        self.console.pack(fill="x", padx=5, pady=5)
        
        scrollbar = ttk.Scrollbar(self.console, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        
        self.console.config(yscrollcommand=scrollbar.set)
    
    # -----------------------------------------------------------------------
    # Utility methods
    # -----------------------------------------------------------------------
    def log_message(self, message):
        # Add message to console log
        self.console.config(state="normal")
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")
    
    def send_serial_command(self, command):
        # Check connection
        if not self.serial_connection.is_connected:
            self.log_message("Error: Not connected to serial port")
            return False
            
        # Send command
        result = self.serial_connection.send_command(command)
        
        if not result:
            self.log_message(f"Error sending command: {command}")
            
        return result
    
    def get_current_servo_angles(self):
        # Collect all servo angles
        servo_positions = []
        
        for i in range(self.num_servos):
            angle = self.single_controls.servo_angles[i].get()
            
            servo_positions.append({
                "id": i,
                "name": f"Servo {i}",
                "position": angle
            })
            
        return servo_positions

# -----------------------------------------------------------------------
# Application entry point
# -----------------------------------------------------------------------
if __name__ == "__main__":
    # Run configuration setup first
    config = run_config_setup()
    
    # Only proceed if configuration was applied
    if config["config_applied"]:
        # Create main application
        root = tk.Tk()
        app = ServoControlApp(root, config)
        root.mainloop()
    else:
        # User cancelled configuration, exit without creating main window
        print("Configuration cancelled. Exiting application.")
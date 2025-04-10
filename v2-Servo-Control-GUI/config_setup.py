import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json


class ConfigSetup:
    # Default settings
    DEFAULT_NUM_SERVOS = 1
    
    def __init__(self):
        # App settings variables
        self.num_servos = self.DEFAULT_NUM_SERVOS
        
        # Result flag
        self.config_applied = False
        
        # Create root window
        self.root = tk.Tk()
        self.root.title("Servo Control Configuration")
        self.root.geometry("400x250")  # Reduced height as we removed GSF control
        
        # Create config UI
        self._create_config_ui()
        
        # Run the dialog
        self.root.mainloop()
    
    # -----------------------------------------------------------------------
    # UI creation
    # -----------------------------------------------------------------------
    def _create_config_ui(self):
        # Create dialog content
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Number of servos
        num_servos_frame = ttk.Frame(frame)
        num_servos_frame.pack(fill="x", pady=10)
        
        ttk.Label(num_servos_frame, text="Number of Servos:").pack(side="left")
        
        self.num_servos_var = tk.IntVar(value=self.DEFAULT_NUM_SERVOS)
        num_servos_spinbox = ttk.Spinbox(
            num_servos_frame,
            from_=1,
            to=30,
            textvariable=self.num_servos_var,
            width=5
        )
        num_servos_spinbox.pack(side="left", padx=10)
        
        # Config file options
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill="x", pady=10)
        
        file_buttons_frame = ttk.Frame(file_frame)
        file_buttons_frame.pack(fill="x", pady=5)
        
        ttk.Button(
            file_buttons_frame,
            text="Load Configuration",
            command=self._load_config_dialog
        ).pack(side="left", padx=5)
        
        ttk.Button(
            file_buttons_frame,
            text="Save Configuration",
            command=self._save_config_dialog
        ).pack(side="left", padx=5)
        
        # Display current config file
        self.config_file_path_var = tk.StringVar(value="No configuration file loaded")
        ttk.Label(file_frame, textvariable=self.config_file_path_var, wraplength=350).pack(fill="x", pady=5)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill="x", pady=20)
        
        ttk.Button(
            button_frame,
            text="Apply",
            command=self._apply_config
        ).pack(side="right", padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel_config
        ).pack(side="right", padx=5)
    
    # -----------------------------------------------------------------------
    # Configuration file operations
    # -----------------------------------------------------------------------
    def _load_config_dialog(self):
        # Open file dialog to select configuration file
        file_path = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  # User cancelled
            
        self._load_config(file_path)
    
    def _load_config(self, file_path):
        # Load configuration from specified file
        try:
            with open(file_path, "r") as file:
                config = json.load(file)
                
                if "num_servos" in config:
                    self.num_servos_var.set(config["num_servos"])
                    
            # Update display
            self.config_file_path_var.set(f"Loaded: {file_path}")
            messagebox.showinfo("Success", f"Configuration loaded from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading configuration: {str(e)}")
    
    def _save_config_dialog(self):
        # Open file dialog to select save location
        file_path = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  # User cancelled
            
        self._save_config(file_path)
    
    def _save_config(self, file_path):
        # Save configuration to specified file
        try:
            config = {
                "num_servos": self.num_servos_var.get()
            }
            
            with open(file_path, "w") as file:
                json.dump(config, file, indent=2)
                
            # Update display
            self.config_file_path_var.set(f"Saved: {file_path}")
            messagebox.showinfo("Success", f"Configuration saved to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error saving configuration: {str(e)}")
    
    # -----------------------------------------------------------------------
    # Button operations
    # -----------------------------------------------------------------------
    def _apply_config(self):
        # Validate inputs
        try:
            num_servos = self.num_servos_var.get()
            if not 1 <= num_servos <= 30:
                raise ValueError("Number of servos must be between 1 and 30")
                
            # Set values
            self.num_servos = num_servos
            
            # Set flag and close dialog
            self.config_applied = True
            self.root.destroy()
                
        except ValueError as e:
            messagebox.showerror("Configuration Error", str(e))
    
    def _cancel_config(self):
        # Close dialog without applying
        self.config_applied = False
        self.root.destroy()
        
    # -----------------------------------------------------------------------
    # Public methods
    # -----------------------------------------------------------------------
    def get_config(self):
        # Return configuration values
        return {
            "config_applied": self.config_applied,
            "num_servos": self.num_servos
        }

# -----------------------------------------------------------------------
# Function to run config setup and return results
# -----------------------------------------------------------------------
def run_config_setup():
    config_setup = ConfigSetup()
    return config_setup.get_config()

# Test standalone
# if __name__ == "__main__":
#     config = run_config_setup()
#     print(config)
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys

class ConfigSetup:
    #default settings
    DEFAULT_NUM_SERVOS = 3
    DEFAULT_GLOBAL_SF = 0.0
    
    def __init__(self):
        #app settings variables
        self.num_servos = self.DEFAULT_NUM_SERVOS
        self.global_sf = self.DEFAULT_GLOBAL_SF
        
        #result flag
        self.config_applied = False
        
        #create root window
        self.root = tk.Tk()
        self.root.title("Servo Control Configuration")
        self.root.geometry("400x300")
        
        #create config UI
        self._create_config_ui()
        
        #run the dialog
        self.root.mainloop()
    
    #-----------------------------------------------------------------------
    #ui creation
    #-----------------------------------------------------------------------
    def _create_config_ui(self):
        #create dialog content
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        
        #number of servos
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
        
        #global smoothing factor
        smoothing_frame = ttk.Frame(frame)
        smoothing_frame.pack(fill="x", pady=10)
        
        ttk.Label(smoothing_frame, text="Global Smoothing Factor:").pack(side="left")
        
        self.global_sf_var = tk.DoubleVar(value=self.DEFAULT_GLOBAL_SF)
        global_sf_spinbox = ttk.Spinbox(
            smoothing_frame,
            from_=0.0,
            to=1.0,
            increment=0.1,
            textvariable=self.global_sf_var,
            width=5
        )
        global_sf_spinbox.pack(side="left", padx=10)
        
        #config file options
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
        
        #display current config file
        self.config_file_path_var = tk.StringVar(value="No configuration file loaded")
        ttk.Label(file_frame, textvariable=self.config_file_path_var, wraplength=350).pack(fill="x", pady=5)
        
        #buttons
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
    
    #-----------------------------------------------------------------------
    #configuration file operations
    #-----------------------------------------------------------------------
    def _load_config_dialog(self):
        #open file dialog to select configuration file
        file_path = filedialog.askopenfilename(
            title="Load Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  #user cancelled
            
        self._load_config(file_path)
    
    def _load_config(self, file_path):
        #load configuration from specified file
        try:
            with open(file_path, "r") as file:
                config = json.load(file)
                
                if "num_servos" in config:
                    self.num_servos_var.set(config["num_servos"])
                    
                if "global_sf" in config:
                    self.global_sf_var.set(config["global_sf"])
                    
            #update display
            self.config_file_path_var.set(f"Loaded: {file_path}")
            messagebox.showinfo("Success", f"Configuration loaded from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading configuration: {str(e)}")
    
    def _save_config_dialog(self):
        #open file dialog to select save location
        file_path = filedialog.asksaveasfilename(
            title="Save Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return  #user cancelled
            
        self._save_config(file_path)
    
    def _save_config(self, file_path):
        #save configuration to specified file
        try:
            config = {
                "num_servos": self.num_servos_var.get(),
                "global_sf": self.global_sf_var.get()
            }
            
            with open(file_path, "w") as file:
                json.dump(config, file, indent=2)
                
            #update display
            self.config_file_path_var.set(f"Saved: {file_path}")
            messagebox.showinfo("Success", f"Configuration saved to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error saving configuration: {str(e)}")
    
    #-----------------------------------------------------------------------
    #button operations
    #-----------------------------------------------------------------------
    def _apply_config(self):
        #validate inputs
        try:
            num_servos = self.num_servos_var.get()
            if not 1 <= num_servos <= 30:
                raise ValueError("Number of servos must be between 1 and 30")
                
            global_sf = self.global_sf_var.get()
            if not 0.0 <= global_sf <= 1.0:
                raise ValueError("Global smoothing factor must be between 0.0 and 1.0")
                
            #set values
            self.num_servos = num_servos
            self.global_sf = global_sf
            
            #set flag and close dialog
            self.config_applied = True
            self.root.destroy()
                
        except ValueError as e:
            messagebox.showerror("Configuration Error", str(e))
    
    def _cancel_config(self):
        #close dialog without applying
        self.config_applied = False
        self.root.destroy()
        
    #-----------------------------------------------------------------------
    #public methods
    #-----------------------------------------------------------------------
    def get_config(self):
        #return configuration values
        return {
            "config_applied": self.config_applied,
            "num_servos": self.num_servos,
            "global_sf": self.global_sf
        }

#-----------------------------------------------------------------------
#function to run config setup and return results
#-----------------------------------------------------------------------
def run_config_setup():
    config_setup = ConfigSetup()
    return config_setup.get_config()

#test standalone
if __name__ == "__main__":
    config = run_config_setup()
    print(config)
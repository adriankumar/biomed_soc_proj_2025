import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json


class ConfigSetup:
    DEFAULT_NUM_SERVOS = 5
    
    def __init__(self):
        self.num_servos = self.DEFAULT_NUM_SERVOS #will be modified in _apply_config()
        
        #result flag to call main gui after num servos is specified
        self.config_applied = False
        
        self.root = tk.Tk()
        self.root.title("Servo Control Configuration")
        self.root.geometry("400x250") 
        
        #create and start
        self._create_config_ui()
        self.root.mainloop()
    
    #-----------------------------------------------------------------------
    #ui creation and setup
    #-----------------------------------------------------------------------
    def _create_config_ui(self):
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)
        
        num_servos_frame = ttk.Frame(frame)
        num_servos_frame.pack(fill="x", pady=10)
        
        ttk.Label(num_servos_frame, text="Number of Servos:").pack(side="left")
        
        #textbox for num servo input
        self.num_servos_var = tk.IntVar(value=self.DEFAULT_NUM_SERVOS)
        num_servos_spinbox = ttk.Spinbox(
            num_servos_frame,
            from_=1,
            to=30,
            textvariable=self.num_servos_var,
            width=5
        )
        num_servos_spinbox.pack(side="left", padx=10) #incrementor
        
        #apply/cancel buttons
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
    #button operations
    #-----------------------------------------------------------------------
    def _apply_config(self):
        try:
            num_servos = self.num_servos_var.get()
            if not 1 <= num_servos <= 30:
                raise ValueError("Number of servos must be between 1 and 30") #make max servos 30
                
            self.num_servos = num_servos
            
            self.config_applied = True
            self.root.destroy() #close after applying
                
        except ValueError as e:
            messagebox.showerror("Configuration Error", str(e))
    
    def _cancel_config(self):
        self.config_applied = False
        self.root.destroy()
        
    #-----------------------------------------------------------------------
    #get attributes
    #-----------------------------------------------------------------------
    def get_config(self):
        # Return configuration values
        return {
            "config_applied": self.config_applied,
            "num_servos": self.num_servos
        }

#-----------------------------------------------------------------------
#function to run everything
#-----------------------------------------------------------------------
def run_config_setup():
    config_setup = ConfigSetup()
    return config_setup.get_config()

# Test standalone
# if __name__ == "__main__":
#     config = run_config_setup()
#     print(config)
#configuration dialog for servo control system

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from hardware.servo_config import DEFAULT_COMPONENT_CONFIGS, PWM_FREQUENCY

class ConfigDialog:
    #configuration setup dialog
    def __init__(self):
        self.config_data = None
        self.choice_made = False
        
        #create modal dialog
        self.dialog = tk.Tk()
        self.dialog.title("servo configuration setup")
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        
        #center window
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (200 // 2)
        self.dialog.geometry(f"400x200+{x}+{y}")
        
        self._create_dialog()
        
        #make modal
        self.dialog.transient()
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    #create dialog interface
    def _create_dialog(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        #title
        title_label = ttk.Label(main_frame, text="servo control system", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        #description
        desc_label = ttk.Label(main_frame, 
                              text="choose how to configure servo settings:")
        desc_label.pack(pady=(0, 20))
        
        #button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(expand=True)
        
        #load custom config button
        load_button = ttk.Button(button_frame, text="load custom config",
                                command=self._load_custom_config,
                                width=20)
        load_button.pack(pady=5)
        
        #use default config button
        default_button = ttk.Button(button_frame, text="use default config",
                                   command=self._use_default_config,
                                   width=20)
        default_button.pack(pady=5)
        
        #info label
        info_label = ttk.Label(main_frame, 
                              text="load custom config: use saved configuration file\n" +
                                   "use default config: start with default values",
                              font=("Arial", 8),
                              foreground="gray")
        info_label.pack(pady=(20, 0))
    
    #load custom configuration from file
    def _load_custom_config(self):
        file_path = filedialog.askopenfilename(
            title="select servo configuration file",
            filetypes=[("json files", "*.json"), ("all files", "*.*")],
            defaultextension=".json"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as file:
                    self.config_data = json.load(file)
                
                #basic validation
                if not isinstance(self.config_data, dict):
                    raise ValueError("invalid configuration format")
                
                if "components" not in self.config_data:
                    raise ValueError("missing components section")
                
                #add pwm frequency if missing (for older configs)
                if "pwm_frequency" not in self.config_data:
                    self.config_data["pwm_frequency"] = PWM_FREQUENCY
                
                #mark as custom config
                self.config_data["_custom_config"] = True
                
                self.choice_made = True
                self.dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("config error", 
                                   f"failed to load configuration:\n{str(e)}")
    
    #use default configuration
    def _use_default_config(self):
        self.config_data = {
            "pwm_frequency": PWM_FREQUENCY,
            "components": DEFAULT_COMPONENT_CONFIGS.copy()
        }
        self.choice_made = True
        self.dialog.destroy()
    
    #handle dialog cancel
    def _on_cancel(self):
        self.choice_made = True
        self.config_data = {
            "pwm_frequency": PWM_FREQUENCY,
            "components": DEFAULT_COMPONENT_CONFIGS.copy()
        }
        self.dialog.destroy()
    
    #show dialog and return configuration
    def show_dialog(self):
        self.dialog.mainloop()
        
        if self.choice_made and self.config_data:
            return self.config_data
        else:
            #fallback to default
            return {
                "pwm_frequency": PWM_FREQUENCY,
                "components": DEFAULT_COMPONENT_CONFIGS.copy()
            }
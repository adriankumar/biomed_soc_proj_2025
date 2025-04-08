import tkinter as tk
from tkinter import ttk, messagebox

class MasterControl:
    def __init__(self, parent, send_command_callback=None, global_sf=0.5):
        #master control frame
        self.frame = ttk.LabelFrame(parent, text="Master Control")
        
        #callback for sending commands to serial
        self.send_command = send_command_callback
        
        #master angle value
        self.master_angle = tk.IntVar(value=90)
        
        #global smoothing factor
        self.global_smoothing = tk.DoubleVar(value=global_sf)
        
        #create the ui components
        self._create_ui()
        
    #-----------------------------------------------------------------------
    #ui creation
    #-----------------------------------------------------------------------
    def _create_ui(self):
        #slider layout
        slider_frame = ttk.Frame(self.frame)
        slider_frame.pack(fill="x", padx=10, pady=5)
        
        #master slider (horizontal, 0-180)
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=180,
            orient="horizontal",
            variable=self.master_angle,
            command=self._on_slider_changed
        )
        self.slider.pack(fill="x", pady=5)
        
        #min/max labels
        min_max_frame = ttk.Frame(slider_frame)
        min_max_frame.pack(fill="x")
        ttk.Label(min_max_frame, text="0°").pack(side="left")
        ttk.Label(min_max_frame, text="180°").pack(side="right")
        
        #value display and manual input
        value_frame = ttk.Frame(self.frame)
        value_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(value_frame, text="Angle:").pack(side="left")
        
        #text field for direct angle input
        self.angle_entry = ttk.Entry(value_frame, width=5, textvariable=self.master_angle)
        self.angle_entry.pack(side="left", padx=5)
        self.angle_entry.bind("<Return>", self._on_angle_entry)
        self.angle_entry.bind("<FocusOut>", self._on_angle_entry)
        
        #increment/decrement buttons
        ttk.Button(value_frame, text="-", width=2, 
                  command=self._decrement_angle).pack(side="left")
        ttk.Button(value_frame, text="+", width=2,
                  command=self._increment_angle).pack(side="left")
        
        #global smoothing factor
        smoothing_frame = ttk.Frame(self.frame)
        smoothing_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(smoothing_frame, text="Global Smoothing Factor:").pack(side="left")
        
        self.smoothing_entry = ttk.Entry(smoothing_frame, width=5, textvariable=self.global_smoothing)
        self.smoothing_entry.pack(side="left", padx=5)
        self.smoothing_entry.bind("<Return>", self._on_smoothing_entry)
        self.smoothing_entry.bind("<FocusOut>", self._on_smoothing_entry)
        
        #add update button for smoothing factor
        self.update_sf_button = ttk.Button(smoothing_frame, text="Update", 
                                        command=self._update_smoothing)
        self.update_sf_button.pack(side="left", padx=5)
    
    #-----------------------------------------------------------------------
    #event handlers
    #-----------------------------------------------------------------------
    def _on_slider_changed(self, event=None):
        #update the text field to match slider
        #send master angle command
        angle = self.master_angle.get()
        if self.send_command:
            self.send_command(f"MA:{angle}")

    def _on_angle_entry(self, event=None):
        #validate the entered value
        try:
            #try to convert to float first, then to int to handle both formats
            entry_value = self.angle_entry.get().strip()
            if not entry_value:
                #handle empty string case
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, str(int(self.master_angle.get())))
                return
                
            angle = int(float(entry_value))
            if 0 <= angle <= 180:
                self.master_angle.set(angle)
                self._on_slider_changed()
            else:
                raise ValueError("Angle must be between 0 and 180")
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e))
            #safely retrieve and set the current value
            try:
                current = int(self.master_angle.get())
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, str(current))
            except:
                #in case of any error, set to a safe default
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, "90")
    
    def _increment_angle(self):
        current = self.master_angle.get()
        if current < 180:
            self.master_angle.set(current + 1)
            self._on_slider_changed()
    
    def _decrement_angle(self):
        current = self.master_angle.get()
        if current > 0:
            self.master_angle.set(current - 1)
            self._on_slider_changed()
    
    def _on_smoothing_entry(self, event=None):
        #validate the entered value
        try:
            factor = float(self.smoothing_entry.get())
            if 0.0 <= factor <= 1.0:
                self.global_smoothing.set(factor)
                if self.send_command:
                    self.send_command(f"GSF:{factor}")
            else:
                raise ValueError("Smoothing factor must be between 0.0 and 1.0")
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e))
            self.smoothing_entry.delete(0, tk.END)
            self.smoothing_entry.insert(0, self.global_smoothing.get())
    
    def _update_smoothing(self):
        #get current value from entry
        try:
            factor = float(self.smoothing_entry.get())
            
            #validate range
            if 0.0 <= factor <= 1.0:
                #update internal value
                self.global_smoothing.set(factor)
                
                #send command to update hardware
                if self.send_command:
                    self.send_command(f"GSF:{factor}")
                    messagebox.showinfo("Updated", f"Smoothing factor set to {factor}")
            else:
                raise ValueError("Smoothing factor must be between 0.0 and 1.0")
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e))
            self.smoothing_entry.delete(0, tk.END)
            self.smoothing_entry.insert(0, str(self.global_smoothing.get()))
    #-----------------------------------------------------------------------
    #public methods
    #-----------------------------------------------------------------------
    def set_angle(self, angle):
        #external method to set the angle
        if 0 <= angle <= 180:
            self.master_angle.set(angle)
            #don't send command when set externally
import tkinter as tk
from tkinter import ttk, messagebox
import time

class MasterControl:
    def __init__(self, parent, send_command_callback=None, num_servos=5):
        self.frame = ttk.LabelFrame(parent, text="Master Control")
        
        self.send_command = send_command_callback #_handle_master_command (MA:{angle}) from single controls.py
        
        self.num_servos = num_servos
        self.master_angle = tk.IntVar(value=90) #set default position to 90

        self._create_ui()
        
#-----------------------------------------------------------------------
#create ui
#-----------------------------------------------------------------------
    def _create_ui(self):

        slider_frame = ttk.Frame(self.frame)
        slider_frame.pack(fill="x", padx=10, pady=5)
        
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=180,
            orient="horizontal", #horizontal display, underneath individual controls 
            variable=self.master_angle,
            command=self._on_slider_changed
        )
        self.slider.pack(fill="x", pady=5)
        
        #min/max labels
        min_max_frame = ttk.Frame(slider_frame)
        min_max_frame.pack(fill="x")
        ttk.Label(min_max_frame, text="0°").pack(side="left")
        ttk.Label(min_max_frame, text="180°").pack(side="right")
        
        #frame for angle display and manual input
        value_frame = ttk.Frame(self.frame)
        value_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(value_frame, text="Angle:").pack(side="left")
        
        #text field entry for manual input
        self.angle_entry = ttk.Entry(value_frame, width=5, textvariable=self.master_angle)
        self.angle_entry.pack(side="left", padx=5)
        self.angle_entry.bind("<Return>", self._on_angle_entry)
        self.angle_entry.bind("<FocusOut>", self._on_angle_entry)
        
        #increment/decrement buttons instead of typing angles if you want to move 1 by 1.. then spam click this lol
        ttk.Button(value_frame, text="-", width=2, 
                  command=self._decrement_angle).pack(side="left")
        ttk.Button(value_frame, text="+", width=2,
                  command=self._increment_angle).pack(side="left")
    
    #-----------------------------------------------------------------------
    #event handlers
    #-----------------------------------------------------------------------
    def _on_slider_changed(self, event=None): #when slider changes, get the current angle it is on and send the command
        # angle = self.master_angle.get()
        current_time = time.time()
        if not hasattr(self, '_last_command_time') or (current_time - self._last_command_time) > 0.05:
            angle = self.master_angle.get()

            if self.send_command:
                result = self.send_command(f"MA:{angle}")
                if result:
                    self._last_command_time = current_time

    def _on_angle_entry(self, event=None): #when user enters angle from text entry field
        try:
            entry_value = self.angle_entry.get().strip()
            if not entry_value: #handle empty string case
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, str(int(self.master_angle.get())))
                return

            #else display it as integer (even if decimal is the input)    
            angle = int(float(entry_value))
            if 0 <= angle <= 180: #ensure entered angle is between 0 and 180
                self.master_angle.set(angle)
                self._on_slider_changed()

            else:
                raise ValueError("Angle must be between 0 and 180")
            
        except ValueError as e:
            messagebox.showwarning("Invalid Input", str(e))
            
            #handle value errors
            try:
                current = int(self.master_angle.get())
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, str(current))
            except:
                #reset
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, "90")
    
    def _increment_angle(self): #incrementor button, increases current angle by 1
        current = self.master_angle.get()
        if current < 180:
            self.master_angle.set(current + 1)
            self._on_slider_changed()
    
    def _decrement_angle(self): #decrementor button, decreases current angle by 1
        current = self.master_angle.get()
        if current > 0:
            self.master_angle.set(current - 1)
            self._on_slider_changed()
    
#-----------------------------------------------------------------------
#optional method incase we want to set the angle without sending command to serial; not currently used
#-----------------------------------------------------------------------
    # def set_angle(self, angle):
    #     if 0 <= angle <= 180:
    #         self.master_angle.set(angle)

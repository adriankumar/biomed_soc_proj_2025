import tkinter as tk
from tkinter import ttk, messagebox

class MasterControl:
    def __init__(self, parent, send_command_callback=None, num_servos=5):
        # Master control frame
        self.frame = ttk.LabelFrame(parent, text="Master Control")
        
        # Callback for sending commands to serial
        self.send_command = send_command_callback
        
        self.num_servos = num_servos

        # Master angle value
        self.master_angle = tk.IntVar(value=90)
        
        # Create the UI components
        self._create_ui()
        
    # -----------------------------------------------------------------------
    # UI creation
    # -----------------------------------------------------------------------
    def _create_ui(self):
        # Slider layout
        slider_frame = ttk.Frame(self.frame)
        slider_frame.pack(fill="x", padx=10, pady=5)
        
        # Master slider (horizontal, 0-180)
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=180,
            orient="horizontal",
            variable=self.master_angle,
            command=self._on_slider_changed
        )
        self.slider.pack(fill="x", pady=5)
        
        # Min/max labels
        min_max_frame = ttk.Frame(slider_frame)
        min_max_frame.pack(fill="x")
        ttk.Label(min_max_frame, text="0°").pack(side="left")
        ttk.Label(min_max_frame, text="180°").pack(side="right")
        
        # Value display and manual input
        value_frame = ttk.Frame(self.frame)
        value_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(value_frame, text="Angle:").pack(side="left")
        
        # Text field for direct angle input
        self.angle_entry = ttk.Entry(value_frame, width=5, textvariable=self.master_angle)
        self.angle_entry.pack(side="left", padx=5)
        self.angle_entry.bind("<Return>", self._on_angle_entry)
        self.angle_entry.bind("<FocusOut>", self._on_angle_entry)
        
        # Increment/decrement buttons
        ttk.Button(value_frame, text="-", width=2, 
                  command=self._decrement_angle).pack(side="left")
        ttk.Button(value_frame, text="+", width=2,
                  command=self._increment_angle).pack(side="left")
        
        # Update settings button
        update_frame = ttk.Frame(self.frame)
        update_frame.pack(fill="x", padx=10, pady=5)
        
        self.update_button = ttk.Button(update_frame, text="Update NUM_SERVOS", 
                                       command=self._update_settings)
        self.update_button.pack(side="left", padx=5)
    
    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------
    def _on_slider_changed(self, event=None):
        # Update the text field to match slider
        # Send master angle command
        angle = self.master_angle.get()
        if self.send_command:
            self.send_command(f"MA:{angle}")

    def _on_angle_entry(self, event=None):
        # Validate the entered value
        try:
            # Try to convert to float first, then to int to handle both formats
            entry_value = self.angle_entry.get().strip()
            if not entry_value:
                # Handle empty string case
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
            # Safely retrieve and set the current value
            try:
                current = int(self.master_angle.get())
                self.angle_entry.delete(0, tk.END)
                self.angle_entry.insert(0, str(current))
            except:
                # In case of any error, set to a safe default
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
    
    def _update_settings(self):
        # Send NUM_SERVOS command
        if self.send_command:
            self.send_command(f"NUM_SERVOS:{self.num_servos}")
            messagebox.showinfo("Updated", f"Settings sent: NUM_SERVOS={self.num_servos}")
    
    # -----------------------------------------------------------------------
    # Public methods
    # -----------------------------------------------------------------------
    def set_angle(self, angle):
        # External method to set the angle
        if 0 <= angle <= 180:
            self.master_angle.set(angle)
            # Don't send command when set externally
import tkinter as tk
from tkinter import ttk, messagebox
from master_control import MasterControl

class SingleControls:
    def __init__(self, parent, num_servos, send_command_callback=None, global_sf=0.5): #need to handle better when individual sf variables come
        #create main frame
        self.frame = ttk.LabelFrame(parent, text="Servo Controls")
        
        #store parameters
        self.num_servos = num_servos
        self.send_command = send_command_callback
        
        #servo control variables
        self.servo_controls = []
        self.servo_angles = []
        
        #create individual controls frame
        self.individual_frame = ttk.LabelFrame(self.frame, text="Individual Servo Controls")
        self.individual_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        #create scrollable frame for many servo controls
        self._create_scrollable_frame()
        
        #initialise individual servo controls
        self._create_individual_controls()
        
        #create master control section at bottom
        self.master_control = MasterControl(
            self.frame, 
            send_command_callback=self._handle_master_command,
            global_sf=global_sf,
            num_servos=self.num_servos
        )
        self.master_control.frame.pack(fill="x", padx=10, pady=5)
    
    #-----------------------------------------------------------------------
    #ui setup methods
    #-----------------------------------------------------------------------
    def _create_scrollable_frame(self):
        #create canvas with scrollbar for many servo controls
        canvas_frame = ttk.Frame(self.individual_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")
        
        self.canvas.configure(xscrollcommand=scrollbar.set)
        
        #create frame inside canvas
        self.controls_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self.controls_frame, 
            anchor="nw"
        )
        
        #update scroll region when controls change size
        self.controls_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
    
    def _on_frame_configure(self, event):
        #update scroll region when controls frame changes
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):
        #update window size when canvas changes
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _create_individual_controls(self):
        #create individual servo controls
        for i in range(self.num_servos):
            servo_angle = tk.IntVar(value=90)
            self.servo_angles.append(servo_angle)
            
            control = self._create_servo_control(i, servo_angle)
            self.servo_controls.append(control)
            
            #place in grid
            control["frame"].pack(side="left", fill="y", padx=5, pady=5)
    
    def _create_servo_control(self, servo_id, angle_var):
        #create frame for this servo
        frame = ttk.LabelFrame(self.controls_frame, text=f"Servo {servo_id}")
        
        #vertical slider (0-180)
        slider = ttk.Scale(
            frame,
            from_=0,
            to=180,
            orient="vertical",
            length=200,
            variable=angle_var,
            command=lambda v, s=servo_id: self._on_slider_changed(s)
        )
        slider.pack(padx=10, pady=5)
        
        #min/max labels
        ttk.Label(frame, text="180°").pack(pady=2)
        ttk.Label(frame, text="0°").pack(pady=2)
        
        #value display with increment/decrement
        value_frame = ttk.Frame(frame)
        value_frame.pack(pady=5)
        
        angle_entry = ttk.Entry(value_frame, width=5, textvariable=angle_var)
        angle_entry.pack(side="left")
        angle_entry.bind("<Return>", lambda e, s=servo_id: self._on_angle_entry(s))
        angle_entry.bind("<FocusOut>", lambda e, s=servo_id: self._on_angle_entry(s))
        
        ttk.Button(value_frame, text="-", width=2,
                  command=lambda s=servo_id: self._decrement_angle(s)).pack(side="left")
                  
        ttk.Button(value_frame, text="+", width=2,
                  command=lambda s=servo_id: self._increment_angle(s)).pack(side="left")
        
        return {
            "frame": frame,
            "slider": slider,
            "entry": angle_entry,
            "angle_var": angle_var
        }
    
#-----------------------------------------------------------------------
#event handlers
#-----------------------------------------------------------------------
    def _on_slider_changed(self, servo_id):
        #slider position changed - send command
        angle = self.servo_angles[servo_id].get()
        
        if self.send_command:
            self.send_command(f"SA:{servo_id}:{angle}")
    
    def _on_angle_entry(self, servo_id, event=None):
            #validate entry and update
            control = self.servo_controls[servo_id]
            
            try:
                #try to convert to float first, then to int to handle both formats
                entry_value = control["entry"].get().strip()
                if not entry_value:
                    #handle empty string case
                    control["entry"].delete(0, tk.END)
                    control["entry"].insert(0, str(int(control["angle_var"].get())))
                    return
                    
                angle = int(float(entry_value))
                
                if 0 <= angle <= 180:
                    control["angle_var"].set(angle)
                    self._on_slider_changed(servo_id)
                else:
                    raise ValueError("Angle must be between 0 and 180")
                    
            except ValueError as e:
                messagebox.showwarning("Invalid Input", str(e))
                #safely retrieve and set the current value
                try:
                    current = int(control["angle_var"].get())
                    control["entry"].delete(0, tk.END)
                    control["entry"].insert(0, str(current))
                except:
                    #in case of any error, set to a safe default
                    control["entry"].delete(0, tk.END)
                    control["entry"].insert(0, "90")
    
    def _increment_angle(self, servo_id):
        control = self.servo_controls[servo_id]
        current = control["angle_var"].get()
        
        if current < 180:
            control["angle_var"].set(current + 1)
            self._on_slider_changed(servo_id)
    
    def _decrement_angle(self, servo_id):
        control = self.servo_controls[servo_id]
        current = control["angle_var"].get()
        
        if current > 0:
            control["angle_var"].set(current - 1)
            self._on_slider_changed(servo_id)
    
    def _handle_master_command(self, command):
        #process commands from master control
        if command.startswith("MA:"):
            #master angle command
            try:
                angle = int(command.split(":")[1])
                
                #update all individual sliders without sending individual commands
                for i in range(self.num_servos):
                    self.servo_angles[i].set(angle)
                
                #pass command to external handler
                if self.send_command:
                    self.send_command(command)
                    
            except (ValueError, IndexError):
                pass
                
        elif self.send_command:
            #pass through any other commands (like GSF)
            self.send_command(command)
    
#-----------------------------------------------------------------------
#public methods
#-----------------------------------------------------------------------
    def set_servo_angle(self, servo_id, angle):
        #set angle externally without triggering commands
        if 0 <= servo_id < self.num_servos and 0 <= angle <= 180:
            self.servo_angles[servo_id].set(angle)
import tkinter as tk
from tkinter import ttk, messagebox
from master_control import MasterControl

class SingleControls:
    def __init__(self, parent, num_servos, send_command_callback=None):
        self.frame = ttk.LabelFrame(parent, text="Servo Controls")
        
        self.num_servos = num_servos
        self.send_command = send_command_callback #send serial command from gui_main -> serial connection
        
        self.servo_controls = []
        self.servo_angles = []
        
        #frame display
        self.individual_frame = ttk.LabelFrame(self.frame, text="Individual Servo Controls")
        self.individual_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        #horizontal scroll bar for individual servo controls, might need to change individual controls however to display in grid of 5 x 6 (where max servos is 30); unless specific servo controls (i.e for hands, fingers, head, etc) are established then refactor display
        self._create_scrollable_frame()
        
        #create the controls
        self._create_individual_controls()
        
        #create the master control at the bottom of the individual controls
        self.master_control = MasterControl(
            self.frame, 
            send_command_callback=self._handle_master_command,
            num_servos=self.num_servos
        )
        self.master_control.frame.pack(fill="x", padx=10, pady=5)
    
#-----------------------------------------------------------------------
#ui creation methods
#-----------------------------------------------------------------------
    def _create_scrollable_frame(self):
        canvas_frame = ttk.Frame(self.individual_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        
        self.canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")
        
        self.canvas.configure(xscrollcommand=scrollbar.set)
        
        self.controls_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), 
            window=self.controls_frame, 
            anchor="nw"
        )
        
        #update scroll region when controls change size
        self.controls_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
    
    #need to implement fixed grid size of 5 x 6 for max 30 servos, then any n servos < 30 will fill in those fixed spaces in order, cos this scroll bar doesnt work lol
    def _on_frame_configure(self, event): #update scroll region when controls frame changes
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def _on_canvas_configure(self, event):#update window size when canvas changes
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _create_individual_controls(self): #create controls
        for i in range(self.num_servos):
            servo_angle = tk.IntVar(value=90)
            self.servo_angles.append(servo_angle)
            
            control = self._create_servo_control(i, servo_angle) #create individual control
            self.servo_controls.append(control)
            
            #edit this for 5 x 6 grid space if max is 30
            control["frame"].pack(side="left", fill="y", padx=5, pady=5)
    
    #slider and text entry field for n specified servos
    def _create_servo_control(self, servo_id, angle_var):
        frame = ttk.LabelFrame(self.controls_frame, text=f"Servo {servo_id}")
        
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
        
        ttk.Label(frame, text="180°").pack(pady=2)
        ttk.Label(frame, text="0°").pack(pady=2)
        
        #incrementors/decrementors same as the master control one; could potentially make this modular by making this its own function call
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
        
        #return components to build
        return {
            "frame": frame,
            "slider": slider,
            "entry": angle_entry,
            "angle_var": angle_var
        }
    
# -----------------------------------------------------------------------
# event handlers
# -----------------------------------------------------------------------
    def _on_slider_changed(self, servo_id): #send individual command when individual servo angle is moved
        angle = self.servo_angles[servo_id].get()
        
        if self.send_command:
            self.send_command(f"SA:{servo_id}:{angle}")
    
    def _on_angle_entry(self, servo_id, event=None): #exact samne as master control just diff argument and serial command.. could also potentially make them both into a reusable function to reduce code
            control = self.servo_controls[servo_id]
            
            try:
                entry_value = control["entry"].get().strip()
                if not entry_value:
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

                try:
                    current = int(control["angle_var"].get())
                    control["entry"].delete(0, tk.END)
                    control["entry"].insert(0, str(current))

                except:
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
    
    def _handle_master_command(self, command): #handle master command to initialise master control callback
        if command.startswith("MA:"):
            try:
                angle = int(command.split(":")[1])
                
                for i in range(self.num_servos): #update all individual servos
                    self.servo_angles[i].set(angle)
                
                if self.send_command:
                    self.send_command(command)
                    
            except (ValueError, IndexError):
                pass
    
# -----------------------------------------------------------------------
# similar concept to the master control public method~ to set angle without sending serial command; currently not used
# -----------------------------------------------------------------------
    # def set_servo_angle(self, servo_id, angle):
    #     if 0 <= servo_id < self.num_servos and 0 <= angle <= 180:
    #         self.servo_angles[servo_id].set(angle)
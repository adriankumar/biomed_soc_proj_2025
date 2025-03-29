import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

#GUI creation and customisation
class ServoView:
    def __init__(self, root):
        self.root = root
        self.root.title("Servo Control System")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        #set custom fonts
        self.title_font = tkfont.Font(family="Arial", size=12, weight="bold")
        self.label_font = tkfont.Font(family="Arial", size=10, weight="bold")
        
        #apply theme to ttk widgets
        self.style = ttk.Style()
        self.style.configure("Title.TLabelframe.Label", font=self.title_font)
        self.style.configure("Bold.TButton", font=self.label_font)
        
        #main window frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill="both", expand=True)
        
        #serial connection frame components
        self.port_var = tk.StringVar() #storing COMX name 
        self.port_combo = None
        self.connect_button = None
        self.status_label = None
        
        #servo control mode set to master (all) by default
        self.view_mode = tk.StringVar(value="master")
        
        #servo control values 
        self.master_value = tk.IntVar(value=90)
        self.master_value_label = None
        
        #sequence control components
        self.delay_var = tk.IntVar(value=500)
        self.record_button = None
        self.play_button = None
        self.stop_button = None
        self.clear_button = None
        self.step_tree = None
        
        #console components
        self.console = None
        
        #create the GUI structure
        self.create_connection_frame()
        self.create_content_frame()
        self.create_console_frame()
    
    #creating the serial connection status layout
    def create_connection_frame(self):
        connection_frame = ttk.LabelFrame(self.main_frame, text="Serial Connection")
        connection_frame.pack(fill="x", pady=5)
        
        #port selection
        ttk.Label(connection_frame, text="Port:", font=self.label_font).grid(row=0, column=0, padx=5, pady=5)
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        
        #connect/disconnect button; functionalities and text change in this one button
        self.connect_button = ttk.Button(connection_frame, text="Connect", style="Bold.TButton")
        self.connect_button.grid(row=0, column=2, padx=5, pady=5)
        
        #refresh ports button
        refresh_button = ttk.Button(connection_frame, text="Refresh Ports", style="Bold.TButton")
        refresh_button.grid(row=0, column=3, padx=5, pady=5)
        
        #display connection status
        ttk.Label(connection_frame, text="Status:", font=self.label_font).grid(row=1, column=0, padx=5, pady=5)
        self.status_label = ttk.Label(connection_frame, text="Disconnected", foreground="red", font=self.label_font)
        self.status_label.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        
        #store information for controller file to handle
        self.connection_components = {
            "port_combo": self.port_combo,
            "connect_button": self.connect_button,
            "refresh_button": refresh_button,
            "status_label": self.status_label
        }
    
    #create horizontal layout with servo controls on left and sequence on right
    def create_content_frame(self):
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        #create left frame for servo controls
        self.servo_section_frame = ttk.Frame(content_frame)
        self.servo_section_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        #create view toggle frame
        self.create_view_toggle_frame()
        
        #create servo control frame
        self.servo_control_frame = ttk.Frame(self.servo_section_frame)
        self.servo_control_frame.pack(fill="both", expand=True, pady=5)
        
        #create right frame for sequence
        self.sequence_section_frame = ttk.Frame(content_frame)
        self.sequence_section_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        #create sequence frame
        self.create_sequence_frame()
    
    #creating a toggle view for servo control (master/individual)
    def create_view_toggle_frame(self):
        view_frame = ttk.LabelFrame(self.servo_section_frame, text="Control Mode", style="Title.TLabelframe")
        view_frame.pack(fill="x", pady=5)
        
        #master control as radio button
        master_radio = ttk.Radiobutton(
            view_frame, 
            text="Master Control (All Servos)", 
            variable=self.view_mode, 
            value="master"
        )
        master_radio.pack(side="left", padx=10, pady=5)
        
        #individual control as radio button
        individual_radio = ttk.Radiobutton(
            view_frame, 
            text="Individual Controls", 
            variable=self.view_mode, 
            value="individual"
        )
        individual_radio.pack(side="left", padx=10, pady=5)
        
        #store data for controller access
        self.view_toggle_components = {
            "master_radio": master_radio,
            "individual_radio": individual_radio
        }
    
    #common function to create servo controls - used by both master and individual modes
    def create_servo_control_widget(self, parent, servo_id, name, value_var, is_master=False):
        #create frame for the servo control
        servo_frame = ttk.LabelFrame(parent, text=name)
        
        #position display
        value_label = ttk.Label(
            servo_frame, 
            text=f"Position: {value_var.get()} degrees",
            font=self.label_font
        )
        value_label.grid(row=0, column=0, columnspan=2, pady=5)
        
        #slider tool
        slider = ttk.Scale(
            servo_frame,
            from_=0,
            to=180,
            orient="horizontal",
            variable=value_var
        )
        slider.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        #min max labels
        labels_frame = ttk.Frame(servo_frame)
        labels_frame.grid(row=2, column=0, sticky="ew")
        ttk.Label(labels_frame, text="0°").pack(side="left")
        ttk.Label(labels_frame, text="180°").pack(side="right")
        
        #add automatic update message for master only
        if is_master:
            ttk.Label(servo_frame, text="Updates are sent automatically", 
                     font=("Arial", 9)).grid(row=3, column=0, pady=5)
        
        #preset buttons frame
        button_frame = ttk.Frame(servo_frame)
        button_frame.grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        
        #preset angle buttons
        preset_buttons = []
        for i, angle in enumerate([0, 45, 90, 135, 180]):
            button = ttk.Button(button_frame, text=f"{angle}°", width=4, style="Bold.TButton")
            button.grid(row=0, column=i, padx=2)
            preset_buttons.append((button, angle))
        
        #return control components
        return {
            "id": servo_id,
            "name": name,
            "value": value_var,
            "frame": servo_frame,
            "label": value_label,
            "slider": slider,
            "preset_buttons": preset_buttons
        }
    
    #display of the master control when selected
    def create_master_control_frame(self, servos):
        #clear existing frame
        for widget in self.servo_control_frame.winfo_children():
            widget.destroy()
        
        master_frame = ttk.LabelFrame(
            self.servo_control_frame, 
            text="Master Servo Control", 
            style="Title.TLabelframe"
        )
        master_frame.pack(fill="both", expand=True, pady=5)
        
        #create master control using common function
        control = self.create_servo_control_widget(
            master_frame, 
            "master", 
            "All Servos", 
            self.master_value, 
            is_master=True
        )
        
        control["frame"].pack(fill="both", expand=True, padx=10, pady=10)
        self.master_value_label = control["label"]
        
        return {
            "slider": control["slider"],
            "label": control["label"],
            "preset_buttons": control["preset_buttons"]
        }
    
    #display of individual servo controls
    def create_individual_controls_frame(self, servos):
        #clear existing frame
        for widget in self.servo_control_frame.winfo_children():
            widget.destroy()
        
        individual_frame = ttk.LabelFrame(
            self.servo_control_frame, 
            text="Individual Servo Controls", 
            style="Title.TLabelframe"
        )
        individual_frame.pack(fill="both", expand=True, pady=5)
        
        #create a scrollable canvas for the servo controls
        canvas_frame = ttk.Frame(individual_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        #add scrollbar
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical")
        canvas = tk.Canvas(canvas_frame, yscrollcommand=scrollbar.set)
        scrollbar.config(command=canvas.yview)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        #create a frame inside the canvas
        servo_container = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=servo_container, anchor="nw")
        
        #set up canvas configuration
        def update_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())
        
        servo_container.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=canvas.winfo_width()))
        
        #create controls for each servo using common function
        servo_controls = []
        for servo in servos:
            control = self.create_servo_control_widget(
                servo_container, 
                servo["id"], 
                servo["name"], 
                servo["value"]
            )
            control["frame"].pack(fill="x", pady=5, padx=5)
            servo_controls.append(control)
        
        return servo_controls
    
    #display for sequence playback controls
    def create_sequence_frame(self):
        sequence_frame = ttk.LabelFrame(
            self.sequence_section_frame, 
            text="Sequence Recording", 
            style="Title.TLabelframe"
        )
        sequence_frame.pack(fill="both", expand=True, pady=5)
        
        #controls frame
        controls_frame = ttk.Frame(sequence_frame)
        controls_frame.pack(fill="x", padx=5, pady=5)
        
        #delay input, inside sequence playback frame
        delay_frame = ttk.Frame(controls_frame)
        delay_frame.pack(fill="x", padx=5, pady=5)
        
        #display delay counter
        ttk.Label(delay_frame, text="Step Delay (ms):", font=self.label_font).pack(side="left", padx=5)
        delay_spinbox = ttk.Spinbox(
            delay_frame, 
            from_=50, 
            to=5000, 
            increment=50, 
            textvariable=self.delay_var, 
            width=5
        )
        delay_spinbox.pack(side="left", padx=5)
        
        #buttons
        buttons_frame = ttk.Frame(controls_frame)
        buttons_frame.pack(fill="x", padx=5, pady=5)
        
        self.record_button = ttk.Button(buttons_frame, text="Record Step", style="Bold.TButton")
        self.record_button.pack(side="left", padx=5)
        
        self.play_button = ttk.Button(buttons_frame, text="Play Sequence", state="disabled", style="Bold.TButton")
        self.play_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(buttons_frame, text="Stop", state="disabled", style="Bold.TButton")
        self.stop_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(buttons_frame, text="Clear Sequence", state="disabled", style="Bold.TButton")
        self.clear_button.pack(side="left", padx=5)
        
        #save/load buttons
        file_frame = ttk.Frame(controls_frame)
        file_frame.pack(fill="x", padx=5, pady=5)
        
        save_button = ttk.Button(file_frame, text="Save Sequence", style="Bold.TButton")
        save_button.pack(side="left", padx=5)
        
        load_button = ttk.Button(file_frame, text="Load Sequence", style="Bold.TButton")
        load_button.pack(side="left", padx=5)
        
        #sequence display (state, servos:angle, delay)
        display_frame = ttk.LabelFrame(sequence_frame, text="Recorded Steps", style="Title.TLabelframe")
        display_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        #scroll bar for sequence display
        scrollbar = ttk.Scrollbar(display_frame)
        scrollbar.pack(side="right", fill="y")
        
        #packing into tree view object
        columns = ("Step", "Servos", "Delay (ms)")
        self.step_tree = ttk.Treeview(
            display_frame, 
            columns=columns, 
            show="headings", 
            selectmode="browse",
            yscrollcommand=scrollbar.set
        )
        
        #headings
        self.step_tree.heading("Step", text="Step")
        self.step_tree.heading("Servos", text="Servos")
        self.step_tree.heading("Delay (ms)", text="Delay (ms)")
        
        #column widths
        self.step_tree.column("Step", width=50, anchor="center")
        self.step_tree.column("Servos", width=350, anchor="w")
        self.step_tree.column("Delay (ms)", width=100, anchor="center")
        
        self.step_tree.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.step_tree.yview)
        
        #button to remove selected step
        remove_step_button = ttk.Button(display_frame, text="Remove Selected Step", style="Bold.TButton")
        remove_step_button.pack(side="left", padx=5, pady=5)
        
        #store for control file to handle
        self.sequence_components = {
            "record_button": self.record_button,
            "play_button": self.play_button,
            "stop_button": self.stop_button,
            "clear_button": self.clear_button,
            "save_button": save_button,
            "load_button": load_button,
            "remove_button": remove_step_button,
            "step_tree": self.step_tree,
            "delay_spinbox": delay_spinbox
        }
    
    #display console log
    def create_console_frame(self):
        console_frame = ttk.LabelFrame(self.main_frame, text="Console", style="Title.TLabelframe")
        console_frame.pack(fill="x", pady=5)
        
        #text widget to display log message
        self.console = tk.Text(console_frame, height=6, width=50, state="disabled")
        self.console.pack(fill="x", padx=5, pady=5)
        
        #scrollbar for inside log message
        scrollbar = ttk.Scrollbar(self.console, command=self.console.yview)
        scrollbar.pack(side="right", fill="y")
        self.console.config(yscrollcommand=scrollbar.set)
    
    #updating sequence display with modified sequence
    def update_sequence_display(self, sequence):
        #clear treeview
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
        
        #loop again to add text in same format over new sequence list
        for i, step in enumerate(sequence, 1):
            servo_text = ", ".join([f"{s['name']}: {s['position']}°" for s in step["servos"]])
            self.step_tree.insert("", "end", values=(i, servo_text, step["delay"]))
    
    #highlight the currently selected sequence step to remove
    def highlight_step(self, index):
        #clear previous selection
        self.step_tree.selection_remove(self.step_tree.selection())
        
        #select current step/sequence
        items = self.step_tree.get_children()
        if 0 <= index < len(items):
            self.step_tree.selection_set(items[index])
            self.step_tree.see(items[index])
    
    #add log messages to console
    def log_message(self, message):
        self.console.config(state="normal")
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state="disabled")
    
    #update connection status view
    def update_connection_status(self, status, is_connected):
        self.status_label.config(
            text=status,
            foreground="green" if is_connected else "red"
        )
        self.connect_button.config(
            text="Disconnect" if is_connected else "Connect"
        )
    
    #controlling playback buttons depending on if there is a current sequence or not
    def update_playback_controls(self, is_playing, has_sequence):
        """Update playback control buttons state"""
        self.play_button.config(state="disabled" if is_playing else ("normal" if has_sequence else "disabled"))
        self.record_button.config(state="disabled" if is_playing else "normal")
        self.clear_button.config(state="disabled" if is_playing else ("normal" if has_sequence else "disabled"))
        self.stop_button.config(state="normal" if is_playing else "disabled")
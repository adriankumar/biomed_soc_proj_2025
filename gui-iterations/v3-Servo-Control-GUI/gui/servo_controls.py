#servo control widgets and management with reliable gui updates

import tkinter as tk
from tkinter import ttk, messagebox
import time
from hardware.servo_config import COMPONENT_GROUPS
from core.validation import validate_pulse_width, validate_servo_index, SLIDER_THROTTLE_MS
from core.event_system import subscribe_component, subscribe, Events

class ServoControlWidget:
    #individual servo control widget
    def __init__(self, parent, component_name, state, send_command_callback):
        self.component_name = component_name
        self.state = state
        self.send_command = send_command_callback
        self.last_command_time = 0
        
        #get component configuration
        self.config = state.get_component_config(component_name)
        
        #create widget frame
        self.frame = ttk.LabelFrame(parent, text=component_name)
        
        #gui variables
        self.pulse_width_var = tk.IntVar(value=self.config["current_position"])
        self.pulse_min_var = tk.IntVar(value=self.config["pulse_min"])
        self.pulse_max_var = tk.IntVar(value=self.config["pulse_max"])
        self.default_position_var = tk.IntVar(value=self.config["default_position"])
        self.index_var = tk.IntVar(value=self.config["index"])
        
        self._create_widget()
        
        #subscribe to component-specific events
        subscribe_component(component_name, [
            Events.COMPONENT_POSITION_CHANGED,
            Events.COMPONENT_RANGE_CHANGED,
            Events.COMPONENT_SETTING_CHANGED
        ], self._on_component_event)
        
        #subscribe to index swap events for all components
        subscribe([Events.COMPONENT_INDEX_SWAPPED], self._on_index_swap)
    
    #create individual servo control widget
    def _create_widget(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(padx=5, pady=5)
        
        #slider section
        slider_frame = ttk.Frame(main_frame)
        slider_frame.pack(side="left", padx=5)
        
        self.max_label = ttk.Label(slider_frame, text=str(self.config["pulse_max"]))
        self.max_label.pack()
        
        self.slider = ttk.Scale(
            slider_frame, 
            from_=self.config["pulse_max"], 
            to=self.config["pulse_min"], 
            orient="vertical", 
            length=150, 
            variable=self.pulse_width_var, 
            command=self._on_slider_changed
        )
        self.slider.pack()
        
        self.min_label = ttk.Label(slider_frame, text=str(self.config["pulse_min"]))
        self.min_label.pack()
        
        #controls section
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(side="left", padx=10)
        
        #current pulse width
        ttk.Label(controls_frame, text="current:").pack()
        self.current_entry = ttk.Entry(controls_frame, width=6, textvariable=self.pulse_width_var)
        self.current_entry.pack(pady=2)
        self.current_entry.bind("<Return>", self._on_current_entry)
        self.current_entry.bind("<FocusOut>", self._on_current_entry)
        
        #pulse range configuration
        ttk.Label(controls_frame, text="min:").pack(pady=(10, 0))
        self.min_entry = ttk.Entry(controls_frame, width=6, textvariable=self.pulse_min_var)
        self.min_entry.pack(pady=2)
        self.min_entry.bind("<Return>", self._on_range_entry)
        self.min_entry.bind("<FocusOut>", self._on_range_entry)
        
        ttk.Label(controls_frame, text="max:").pack()
        self.max_entry = ttk.Entry(controls_frame, width=6, textvariable=self.pulse_max_var)
        self.max_entry.pack(pady=2)
        self.max_entry.bind("<Return>", self._on_range_entry)
        self.max_entry.bind("<FocusOut>", self._on_range_entry)
        
        #default position
        ttk.Label(controls_frame, text="default:").pack(pady=(10, 0))
        self.default_entry = ttk.Entry(controls_frame, width=6, textvariable=self.default_position_var)
        self.default_entry.pack(pady=2)
        self.default_entry.bind("<Return>", self._on_default_entry)
        self.default_entry.bind("<FocusOut>", self._on_default_entry)
        
        #index
        ttk.Label(controls_frame, text="index:").pack(pady=(10, 0))
        self.index_entry = ttk.Entry(controls_frame, width=6, textvariable=self.index_var)
        self.index_entry.pack(pady=2)
        self.index_entry.bind("<Return>", self._on_index_entry)
        self.index_entry.bind("<FocusOut>", self._on_index_entry)
    
    #handle slider changes with throttling
    def _on_slider_changed(self, value):
        current_time = time.time()
        if (current_time - self.last_command_time) * 1000 > SLIDER_THROTTLE_MS:
            pulse_width = int(float(value))
            self.pulse_width_var.set(pulse_width)
            self._send_servo_command(pulse_width)
            self.last_command_time = current_time
    
    #handle current pulse width entry
    def _on_current_entry(self, event=None):
        result = validate_pulse_width(self.current_entry.get())
        
        if not result.is_valid:
            if self.current_entry.get().strip():
                messagebox.showwarning("invalid input", result.error_message)
            self._reset_current_entry()
            return
        
        pulse_width = result.value
        
        #check component range
        config = self.config
        if not (config["pulse_min"] <= pulse_width <= config["pulse_max"]):
            messagebox.showwarning("out of range", 
                f"pulse width must be between {config['pulse_min']} and {config['pulse_max']}")
            self._reset_current_entry()
            return
        
        self.pulse_width_var.set(pulse_width)
        self._send_servo_command(pulse_width)
    
    #handle pulse range entry changes
    def _on_range_entry(self, event=None):
        try:
            pulse_min = self.pulse_min_var.get()
            pulse_max = self.pulse_max_var.get()
            
            if pulse_min >= pulse_max:
                messagebox.showwarning("invalid range", "minimum must be less than maximum")
                self._reset_range_entries()
                return
            
            if self.state.update_component_pulse_range(self.component_name, pulse_min, pulse_max):
                self._update_slider_range()
            else:
                self._reset_range_entries()
                
        except (tk.TclError, ValueError):
            self._reset_range_entries()
    
    #handle default position entry
    def _on_default_entry(self, event=None):
        result = validate_pulse_width(self.default_entry.get())
        
        if not result.is_valid:
            if self.default_entry.get().strip():
                messagebox.showwarning("invalid input", result.error_message)
            self._reset_default_entry()
            return
        
        default_pos = result.value
        config = self.config
        
        if not (config["pulse_min"] <= default_pos <= config["pulse_max"]):
            messagebox.showwarning("out of range", 
                f"default position must be between {config['pulse_min']} and {config['pulse_max']}")
            self._reset_default_entry()
            return
        
        self.state.update_component_setting(self.component_name, "default_position", default_pos)
    
    #handle index entry changes
    def _on_index_entry(self, event=None):
        result = validate_servo_index(self.index_entry.get())
        
        if not result.is_valid:
            if self.index_entry.get().strip():
                messagebox.showwarning("invalid index", result.error_message)
            self._reset_index_entry()
            return
        
        new_index = result.value
        current_index = self.config["index"]
        
        if current_index == new_index:
            return
        
        #find component with target index for swapping
        target_component = None
        for comp_name, comp_config in self.state.servo_configurations.items():
            if comp_config["index"] == new_index:
                target_component = comp_name
                break
        
        if target_component:
            self.state.swap_component_indices(self.component_name, target_component)
        else:
            self.state.update_component_setting(self.component_name, "index", new_index)
    
    #send servo command to esp
    def _send_servo_command(self, pulse_width):
        servo_index = self.config["index"]
        if self.send_command and self.send_command(f"SP:{servo_index}:{pulse_width}"):
            self.state.update_servo_position(self.component_name, pulse_width)
    
    #reset servo to default position
    def reset_to_default(self):
        default_pos = self.config["default_position"]
        self.pulse_width_var.set(default_pos)
        self._send_servo_command(default_pos)
    
    #update slider range
    def _update_slider_range(self):
        self.slider.configure(from_=self.config["pulse_max"], to=self.config["pulse_min"])
        self.min_label.config(text=str(self.config["pulse_min"]))
        self.max_label.config(text=str(self.config["pulse_max"]))
        
        #ensure current position is within new range
        current = self.pulse_width_var.get()
        if not (self.config["pulse_min"] <= current <= self.config["pulse_max"]):
            self.pulse_width_var.set(self.config["current_position"])
    
    #force refresh of all display values
    def _refresh_all_displays(self):
        #force update all gui variables from current state
        self.pulse_width_var.set(self.config["current_position"])
        self.pulse_min_var.set(self.config["pulse_min"])
        self.pulse_max_var.set(self.config["pulse_max"])
        self.default_position_var.set(self.config["default_position"])
        self.index_var.set(self.config["index"])
        
        #update slider range
        self._update_slider_range()
        
        #force widget to update display
        self.frame.update_idletasks()
    
    #reset entry fields to current values
    def _reset_current_entry(self):
        self.current_entry.delete(0, tk.END)
        self.current_entry.insert(0, str(self.config["current_position"]))
    
    def _reset_range_entries(self):
        self.pulse_min_var.set(self.config["pulse_min"])
        self.pulse_max_var.set(self.config["pulse_max"])
    
    def _reset_default_entry(self):
        self.default_position_var.set(self.config["default_position"])
    
    def _reset_index_entry(self):
        self.index_var.set(self.config["index"])
    
    #handle component-specific events
    def _on_component_event(self, event_type, *args, **kwargs):
        if event_type == Events.COMPONENT_POSITION_CHANGED:
            component_name, pulse_width = args
            self.pulse_width_var.set(pulse_width)
            
        elif event_type == Events.COMPONENT_RANGE_CHANGED:
            self.pulse_min_var.set(self.config["pulse_min"])
            self.pulse_max_var.set(self.config["pulse_max"])
            self.default_position_var.set(self.config["default_position"])
            self._update_slider_range()
            
        elif event_type == Events.COMPONENT_SETTING_CHANGED:
            component_name, setting, value = args
            if setting == "index":
                self.index_var.set(value)
                #force immediate display refresh
                self.frame.update_idletasks()
            elif setting == "default_position":
                self.default_position_var.set(value)
    
    #handle index swap events
    def _on_index_swap(self, event_type, *args, **kwargs):
        component1, component2 = args
        if component1 == self.component_name or component2 == self.component_name:
            #force immediate refresh of index display
            self.index_var.set(self.config["index"])
            self.frame.update_idletasks()
            
            #schedule a delayed refresh to ensure display is correct
            self.frame.after(50, self._refresh_all_displays)


class ServoControlsManager:
    #manages grouped servo control widgets
    def __init__(self, parent, state, send_command_callback):
        self.frame = ttk.LabelFrame(parent, text="servo controls")
        self.state = state
        self.send_command = send_command_callback
        
        self.servo_widgets = {}
        self.selected_component_group = tk.StringVar()
        self.component_groups = COMPONENT_GROUPS
        
        self._create_controls()
        
        #subscribe to events that affect all widgets
        subscribe([Events.ALL_SERVOS_RESET, Events.COMPONENT_INDEX_SWAPPED], self._on_global_event)
    
    #create main control interface
    def _create_controls(self):
        header_frame = ttk.Frame(self.frame)
        header_frame.pack(fill="x", padx=10, pady=5)
        
        #component group selection
        selection_frame = ttk.Frame(header_frame)
        selection_frame.pack(anchor="w")
        
        ttk.Label(selection_frame, text="select component group:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        
        #radio buttons in compact grid
        radio_frame = ttk.Frame(selection_frame)
        radio_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))
        
        group_names = list(self.component_groups.keys())
        self.selected_component_group.set(group_names[0])
        
        for i, group in enumerate(group_names):
            display_name = group.replace("_", " ")
            row = i // 4
            col = i % 4
            ttk.Radiobutton(
                radio_frame, 
                text=display_name,
                variable=self.selected_component_group, 
                value=group,
                command=self._on_group_changed
            ).grid(row=row, column=col, sticky="w", padx=(0, 15), pady=2)
        
        #action buttons
        action_frame = ttk.Frame(selection_frame)
        action_frame.grid(row=2, column=0, sticky="w", pady=(10, 0))
        
        ttk.Button(action_frame, text="reset all to defaults",
                  command=self._reset_all_servos).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(action_frame, text="save servo config",
                  command=self._save_servo_config).grid(row=0, column=1)
        
        #controls container
        self.controls_container = ttk.Frame(self.frame)
        self.controls_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        self._create_group_widgets()
    
    #handle component group selection change
    def _on_group_changed(self):
        #clear existing widgets
        for widget in self.controls_container.winfo_children():
            widget.destroy()
        
        #clear widget references
        selected_group = self.selected_component_group.get()
        if selected_group in self.component_groups:
            for component_name in self.component_groups[selected_group]:
                if component_name in self.servo_widgets:
                    del self.servo_widgets[component_name]
        
        self._create_group_widgets()
    
    #create widgets for selected component group
    def _create_group_widgets(self):
        selected_group = self.selected_component_group.get()
        if selected_group in self.component_groups:
            component_names = self.component_groups[selected_group]
            
            for component_name in component_names:
                widget = ServoControlWidget(
                    self.controls_container, 
                    component_name, 
                    self.state, 
                    self.send_command
                )
                widget.frame.pack(side="left", fill="y", padx=5, pady=5)
                self.servo_widgets[component_name] = widget
    
    #handle global events that affect multiple widgets
    def _on_global_event(self, event_type, *args, **kwargs):
        if event_type == Events.ALL_SERVOS_RESET:
            #update all visible widgets
            self._refresh_visible_widgets()
            
        elif event_type == Events.COMPONENT_INDEX_SWAPPED:
            #force refresh all visible widgets for index swaps
            self._refresh_visible_widgets()
    
    #refresh all currently visible widgets
    def _refresh_visible_widgets(self):
        selected_group = self.selected_component_group.get()
        if selected_group in self.component_groups:
            for component_name in self.component_groups[selected_group]:
                if component_name in self.servo_widgets:
                    widget = self.servo_widgets[component_name]
                    widget._refresh_all_displays()
    
    #reset all servos to defaults
    def _reset_all_servos(self):
        reset_commands = self.state.reset_all_servos_to_defaults()
        
        for servo_index, pulse_width in reset_commands:
            if self.send_command:
                self.send_command(f"SP:{servo_index}:{pulse_width}")
        
        #refresh visible widgets
        self._refresh_visible_widgets()
    
    #save servo configuration
    def _save_servo_config(self):
        self.state.save_config_to_file()
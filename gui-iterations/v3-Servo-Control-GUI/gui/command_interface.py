import tkinter as tk
from tkinter import ttk, scrolledtext
from core.validation import COMMAND_HISTORY_LIMIT

#simplified command templates for terminal interface
COMMAND_TEMPLATES = {
    #connection commands
    "connect": {
        "pattern": "connect",
        "description": "connect to serial port",
        "example": "connect"
    },
    "disconnect": {
        "pattern": "disconnect", 
        "description": "disconnect from serial port",
        "example": "disconnect"
    },
    
    #component movement commands
    "move": {
        "pattern": "move {component} to {value}",
        "description": "move component to specified pulse width",
        "example": "move eye_horizontal to 400"
    },
    "move_all": {
        "pattern": "move all to {value}",
        "description": "move all components to pulse width (clamped to individual ranges)",
        "example": "move all to 375"
    },
    
    #component configuration commands
    "set_min": {
        "pattern": "set {component} min {value}",
        "description": "set minimum pulse width for component",
        "example": "set eye_horizontal min 150"
    },
    "set_max": {
        "pattern": "set {component} max {value}",
        "description": "set maximum pulse width for component", 
        "example": "set eye_horizontal max 600"
    },
    "set_default": {
        "pattern": "set {component} default {value}",
        "description": "set default position for component",
        "example": "set eye_horizontal default 375"
    },
    
    #system configuration commands
    "save_config": {
        "pattern": "save config",
        "description": "save current servo configuration to file",
        "example": "save config"
    },
    "reset_all": {
        "pattern": "reset all",
        "description": "reset all servos to default positions",
        "example": "reset all"
    },
    
    #sequence commands
    "record": {
        "pattern": "record {delay}",
        "description": "record current positions with delay to next step",
        "example": "record 1.5"
    },
    "play_sequence": {
        "pattern": "play sequence",
        "description": "start sequence playback",
        "example": "play sequence"
    },
    "clear_sequence": {
        "pattern": "clear sequence",
        "description": "clear all recorded steps",
        "example": "clear sequence"
    },
    "save_sequence": {
        "pattern": "save sequence",
        "description": "save current sequence to file",
        "example": "save sequence"
    },
    "load_sequence": {
        "pattern": "load sequence", 
        "description": "load sequence from file",
        "example": "load sequence"
    },
    
    #utility commands
    "help": {
        "pattern": "help",
        "description": "display available commands",
        "example": "help"
    },
    "status": {
        "pattern": "status",
        "description": "show system status information",
        "example": "status"
    }
}

class CommandTerminal:
    #command terminal interface for servo control
    def __init__(self, parent, state, serial_connection, sequence_manager, content_switcher, log_callback):
        self.frame = ttk.LabelFrame(parent, text="command terminal")
        self.state = state
        self.serial_connection = serial_connection
        self.sequence_manager = sequence_manager
        self.content_switcher = content_switcher
        self.log_callback = log_callback
        
        #command processing state
        self.command_history = []
        self.history_index = -1
        self.autocomplete_cache = []
        
        #gui variables
        self.command_var = tk.StringVar()
        self.command_entry = None
        
        self._create_ui()
        self._build_autocomplete_cache()
    
    #create command terminal interface
    def _create_ui(self):
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill="x", padx=5, pady=5)
        
        #command prompt
        ttk.Label(input_frame, text=">").pack(side="left", padx=(0, 5))
        
        #command input
        self.command_entry = ttk.Entry(input_frame, textvariable=self.command_var, font=("Consolas", 10))
        self.command_entry.pack(side="left", fill="x", expand=True)
        
        #bind events
        self.command_entry.bind("<Return>", self._on_command_entered)
        self.command_entry.bind("<Up>", self._on_history_up)
        self.command_entry.bind("<Down>", self._on_history_down)
        self.command_entry.bind("<Tab>", self._on_tab_autocomplete)
        
        #help button
        ttk.Button(input_frame, text="help", command=self._show_help).pack(side="right", padx=(5, 0))
        
        self.log_callback("command terminal ready - type 'help' for available commands")
    
    #handle command entry submission
    def _on_command_entered(self, event=None):
        command_text = self.command_var.get().strip().lower()
        
        if not command_text:
            return
        
        #add to history if not duplicate
        if not self.command_history or self.command_history[-1] != command_text:
            self.command_history.append(command_text)
            if len(self.command_history) > COMMAND_HISTORY_LIMIT:
                self.command_history.pop(0)
        
        self.history_index = -1
        self.command_var.set("")
        
        #echo command
        self.log_callback(f"> {command_text}")
        
        #process command
        self._process_command(command_text)
    
    #handle up arrow for command history
    def _on_history_up(self, event):
        if not self.command_history:
            return "break"
        
        if self.history_index == -1:
            self.history_index = len(self.command_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        
        self.command_var.set(self.command_history[self.history_index])
        self.command_entry.selection_range(0, tk.END)
        return "break"
    
    #handle down arrow for command history
    def _on_history_down(self, event):
        if not self.command_history or self.history_index == -1:
            return "break"
        
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.command_var.set(self.command_history[self.history_index])
        else:
            self.history_index = -1
            self.command_var.set("")
        
        self.command_entry.selection_range(0, tk.END)
        return "break"
    
    #handle tab autocomplete
    def _on_tab_autocomplete(self, event):
        current_text = self.command_var.get().lower()
        
        if len(current_text) < 1:
            return "break"
        
        #find matching options
        matches = [option for option in self.autocomplete_cache if option.startswith(current_text)]
        
        if matches:
            if len(matches) == 1:
                self.command_var.set(matches[0])
                self.command_entry.icursor(tk.END)
            else:
                #show options
                self.log_callback(f"options: {', '.join(matches[:5])}")
                if len(matches) > 5:
                    self.log_callback(f"... and {len(matches) - 5} more")
        
        return "break"
    
    #build autocomplete cache with current component names
    def _build_autocomplete_cache(self):
        self.autocomplete_cache = []
        
        #add basic command patterns
        for cmd_info in COMMAND_TEMPLATES.values():
            pattern = cmd_info["pattern"].lower()
            #add base commands without variables
            if "{" not in pattern:
                self.autocomplete_cache.append(pattern)
        
        #add component-specific patterns with current component names
        for component_name in self.state.servo_configurations.keys():
            self.autocomplete_cache.extend([
                f"move {component_name} to ",
                f"set {component_name} min ",
                f"set {component_name} max ",
                f"set {component_name} default "
            ])
        
        #add move all pattern
        self.autocomplete_cache.append("move all to ")
    
    #process entered command using simplified parsing
    def _process_command(self, command_text):
        try:
            parsed = self._parse_command(command_text)
            
            if not parsed:
                self.log_callback("unknown command - type 'help' for available commands")
                return
            
            command_type, args = parsed
            self._execute_command(command_type, args)
            
        except Exception as e:
            self.log_callback(f"command error: {str(e)}")
    
    #simplified command parsing with pattern matching
    def _parse_command(self, command_text):
        #exact matches first
        exact_commands = ["connect", "disconnect", "save config", "reset all", "play sequence", 
                         "clear sequence", "save sequence", "load sequence", "help", "status"]
        
        if command_text in exact_commands:
            return command_text.replace(" ", "_"), {}
        
        #pattern matches with simplified logic
        if command_text.startswith("move ") and " to " in command_text:
            if command_text.startswith("move all to "):
                value = command_text.replace("move all to ", "").strip()
                return "move_all", {"value": value}
            else:
                parts = command_text.split(" to ")
                if len(parts) == 2:
                    component = parts[0].replace("move ", "").strip()
                    value = parts[1].strip()
                    return "move", {"component": component, "value": value}
        
        elif command_text.startswith("set ") and not command_text.startswith("set all"):
            #handle set component property commands
            if " min " in command_text:
                parts = command_text.split(" min ")
                if len(parts) == 2:
                    component = parts[0].replace("set ", "").strip()
                    value = parts[1].strip()
                    return "set_property", {"component": component, "property": "min", "value": value}
            elif " max " in command_text:
                parts = command_text.split(" max ")
                if len(parts) == 2:
                    component = parts[0].replace("set ", "").strip()
                    value = parts[1].strip()
                    return "set_property", {"component": component, "property": "max", "value": value}
            elif " default " in command_text:
                parts = command_text.split(" default ")
                if len(parts) == 2:
                    component = parts[0].replace("set ", "").strip()
                    value = parts[1].strip()
                    return "set_property", {"component": component, "property": "default", "value": value}
        
        elif command_text.startswith("record "):
            value = command_text.replace("record ", "").strip()
            return "record", {"delay": value}
        
        return None
    
    #execute parsed command using generic handlers
    def _execute_command(self, command_type, args):
        if command_type == "connect":
            self._cmd_connect()
        elif command_type == "disconnect":
            self._cmd_disconnect()
        elif command_type == "move":
            self._execute_component_move(args.get("component"), args.get("value"))
        elif command_type == "move_all":
            self._cmd_move_all(args.get("value"))
        elif command_type == "set_property":
            self._execute_component_property(args.get("component"), args.get("property"), args.get("value"))
        elif command_type == "save_config":
            self._cmd_save_config()
        elif command_type == "reset_all":
            self._cmd_reset_all()
        elif command_type == "record":
            self._cmd_record(args.get("delay"))
        elif command_type == "play_sequence":
            self._cmd_play_sequence()
        elif command_type == "clear_sequence":
            self._cmd_clear_sequence()
        elif command_type == "save_sequence":
            self._cmd_save_sequence()
        elif command_type == "load_sequence":
            self._cmd_load_sequence()
        elif command_type == "help":
            self._cmd_help()
        elif command_type == "status":
            self._cmd_status()
        else:
            self.log_callback(f"unimplemented command: {command_type}")
    
    #generic component movement handler
    def _execute_component_move(self, component_name, value_str):
        if not component_name or not value_str:
            self.log_callback("invalid move command - use: move <component> to <value>")
            return
        
        if component_name not in self.state.servo_configurations:
            self.log_callback(f"component '{component_name}' not found")
            return
        
        try:
            pulse_width = int(float(value_str))
            config = self.state.servo_configurations[component_name]
            
            if not (config["pulse_min"] <= pulse_width <= config["pulse_max"]):
                self.log_callback(f"pulse width {pulse_width} outside range [{config['pulse_min']}, {config['pulse_max']}] for {component_name}")
                return
            
            if self.state.update_servo_position(component_name, pulse_width):
                if self.serial_connection.is_connected:
                    servo_index = config["index"]
                    if self.serial_connection.send_command(f"SP:{servo_index}:{pulse_width}"):
                        self.log_callback(f"moved {component_name} to {pulse_width}")
                    else:
                        self.log_callback(f"failed to send move command for {component_name}")
                else:
                    self.log_callback(f"moved {component_name} to {pulse_width} (not connected)")
            else:
                self.log_callback(f"failed to update position for {component_name}")
                
        except ValueError:
            self.log_callback(f"invalid pulse width value: {value_str}")
    
    #generic component property setter
    def _execute_component_property(self, component_name, property_name, value_str):
        if not component_name or not property_name or not value_str:
            self.log_callback("invalid set command")
            return
        
        if component_name not in self.state.servo_configurations:
            self.log_callback(f"component '{component_name}' not found")
            return
        
        try:
            value = int(float(value_str))
            config = self.state.servo_configurations[component_name]
            
            if property_name == "min":
                if value < config["pulse_max"]:
                    if self.state.update_component_pulse_range(component_name, value, config["pulse_max"]):
                        self.log_callback(f"updated minimum pulse width for {component_name} to {value}")
                    else:
                        self.log_callback(f"failed to update minimum pulse width for {component_name}")
                else:
                    self.log_callback(f"minimum value {value} must be less than maximum {config['pulse_max']}")
                    
            elif property_name == "max":
                if value > config["pulse_min"]:
                    if self.state.update_component_pulse_range(component_name, config["pulse_min"], value):
                        self.log_callback(f"updated maximum pulse width for {component_name} to {value}")
                    else:
                        self.log_callback(f"failed to update maximum pulse width for {component_name}")
                else:
                    self.log_callback(f"maximum value {value} must be greater than minimum {config['pulse_min']}")
                    
            elif property_name == "default":
                if config["pulse_min"] <= value <= config["pulse_max"]:
                    if self.state.update_component_setting(component_name, "default_position", value):
                        self.log_callback(f"set default position for {component_name} to {value}")
                    else:
                        self.log_callback(f"failed to set default position for {component_name}")
                else:
                    self.log_callback(f"default position {value} outside range [{config['pulse_min']}, {config['pulse_max']}] for {component_name}")
                    
        except ValueError:
            self.log_callback(f"invalid {property_name} value: {value_str}")
    
    #move all components with range clamping
    def _cmd_move_all(self, value_str):
        if not value_str:
            self.log_callback("pulse width value required for move all")
            return
        
        try:
            target_pulse = int(float(value_str))
            success_count = 0
            command_count = 0
            total_components = len(self.state.servo_configurations)
            clamped_components = 0
            
            for component_name, config in self.state.servo_configurations.items():
                #clamp pulse width to component's valid range
                clamped_pulse = max(config["pulse_min"], min(config["pulse_max"], target_pulse))
                
                if clamped_pulse != target_pulse:
                    clamped_components += 1
                
                if self.state.update_servo_position(component_name, clamped_pulse):
                    success_count += 1
                    
                    if self.serial_connection.is_connected:
                        servo_index = config["index"]
                        if self.serial_connection.send_command(f"SP:{servo_index}:{clamped_pulse}"):
                            command_count += 1
            
            if self.serial_connection.is_connected:
                self.log_callback(f"moved {success_count}/{total_components} components (sent {command_count} commands)")
            else:
                self.log_callback(f"moved {success_count}/{total_components} components (not connected)")
            
            if clamped_components > 0:
                self.log_callback(f"note: {clamped_components} components were clamped to their valid ranges")
                
        except ValueError:
            self.log_callback(f"invalid pulse width value: {value_str}")
    
    #connection commands
    def _cmd_connect(self):
        if self.serial_connection.is_connected:
            self.log_callback("already connected to serial port")
        else:
            success = self.serial_connection.connect()
            if success:
                self.log_callback("connected to serial port successfully")
            else:
                self.log_callback("failed to connect to serial port")
    
    def _cmd_disconnect(self):
        if not self.serial_connection.is_connected:
            self.log_callback("not connected to serial port")
        else:
            success = self.serial_connection.disconnect()
            if success:
                self.log_callback("disconnected from serial port")
            else:
                self.log_callback("failed to disconnect from serial port")
    
    #system commands
    def _cmd_save_config(self):
        success = self.state.save_config_to_file()
        if success:
            self.log_callback("servo configuration saved successfully")
        else:
            self.log_callback("failed to save servo configuration")
    
    def _cmd_reset_all(self):
        reset_commands = self.state.reset_all_servos_to_defaults()
        
        if self.serial_connection.is_connected:
            success_count = 0
            for servo_index, pulse_width in reset_commands:
                if self.serial_connection.send_command(f"SP:{servo_index}:{pulse_width}"):
                    success_count += 1
            
            self.log_callback(f"reset {success_count}/{len(reset_commands)} servos to default positions")
        else:
            self.log_callback(f"reset {len(reset_commands)} servos to default positions (not connected)")
    
    #sequence commands
    def _cmd_record(self, delay_str):
        if not delay_str:
            self.log_callback("delay value required for recording")
            return
        
        try:
            delay = float(delay_str)
            success, message = self.sequence_manager.record_keyframe(delay)
            
            if success:
                self.log_callback(f"recorded step {self.sequence_manager.get_keyframe_count()} with {delay}s delay")
            else:
                self.log_callback(f"recording failed: {message}")
                
        except ValueError:
            self.log_callback(f"invalid delay value: {delay_str}")
    
    def _cmd_play_sequence(self):
        if not self.sequence_manager.has_keyframes():
            self.log_callback("no sequence to play")
            return
        
        if not self.serial_connection.is_connected:
            self.log_callback("serial connection required for sequence playback")
            return
        
        if self.content_switcher.is_sequence_recording_active():
            sequence_widget = self.content_switcher.get_sequence_recorder_widget()
            if sequence_widget:
                sequence_widget._play_sequence()
                self.log_callback("sequence playback started")
            else:
                self.log_callback("sequence recording widget not available")
        else:
            self.log_callback("switch to sequence recording tool to use playback")
    
    def _cmd_clear_sequence(self):
        if not self.sequence_manager.has_keyframes():
            self.log_callback("no sequence to clear")
            return
        
        success, message = self.sequence_manager.clear_sequence()
        if success:
            self.log_callback("sequence cleared")
        else:
            self.log_callback(f"failed to clear sequence: {message}")
    
    def _cmd_save_sequence(self):
        if not self.sequence_manager.has_keyframes():
            self.log_callback("no sequence to save")
            return
        
        success, message = self.sequence_manager.save_sequence()
        if success:
            self.log_callback("sequence saved successfully")
        else:
            self.log_callback(f"sequence save failed: {message}")
    
    def _cmd_load_sequence(self):
        success, message = self.sequence_manager.load_sequence()
        if success:
            self.log_callback("sequence loaded successfully")
        else:
            self.log_callback(f"sequence load failed: {message}")
    
    #utility commands
    def _cmd_help(self):
        self.log_callback("=== available commands ===")
        
        categories = {
            "connection": ["connect", "disconnect"],
            "movement": ["move", "move_all"],
            "configuration": ["set_min", "set_max", "set_default", "save_config", "reset_all"],
            "sequence": ["record", "play_sequence", "clear_sequence", "save_sequence", "load_sequence"],
            "utility": ["help", "status"]
        }
        
        for category, commands in categories.items():
            self.log_callback(f"\n{category.upper()}:")
            for cmd_key in commands:
                if cmd_key in COMMAND_TEMPLATES:
                    cmd_info = COMMAND_TEMPLATES[cmd_key]
                    self.log_callback(f"  {cmd_info['example']} - {cmd_info['description']}")
        
        self.log_callback("\nuse tab for autocomplete, up/down arrows for command history")
    
    def _cmd_status(self):
        self.log_callback("=== system status ===")
        self.log_callback(f"serial connection: {'connected' if self.serial_connection.is_connected else 'disconnected'}")
        self.log_callback(f"configured components: {len(self.state.servo_configurations)}")
        self.log_callback(f"sequence keyframes: {self.sequence_manager.get_keyframe_count()}")
        
        if self.sequence_manager.has_keyframes():
            duration = self.sequence_manager.get_total_duration()
            self.log_callback(f"sequence duration: {duration:.1f}s")
        
        current_tool = self.content_switcher.get_selected_content()
        self.log_callback(f"current tool: {current_tool}")
    
    #show detailed help window
    def _show_help(self):
        help_window = tk.Toplevel(self.frame)
        help_window.title("command terminal help")
        help_window.geometry("600x500")
        help_window.resizable(True, True)
        
        help_text = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, padx=10, pady=10)
        help_text.pack(fill="both", expand=True)
        
        help_content = "SERVO CONTROL COMMAND TERMINAL\n\n"
        
        categories = {
            "CONNECTION COMMANDS": ["connect", "disconnect"],
            "MOVEMENT COMMANDS": ["move", "move_all"],
            "CONFIGURATION COMMANDS": ["set_min", "set_max", "set_default", "save_config", "reset_all"],
            "SEQUENCE COMMANDS": ["record", "play_sequence", "clear_sequence", "save_sequence", "load_sequence"],
            "UTILITY COMMANDS": ["help", "status"]
        }
        
        for category, commands in categories.items():
            help_content += f"{category}:\n"
            for cmd_key in commands:
                if cmd_key in COMMAND_TEMPLATES:
                    cmd_info = COMMAND_TEMPLATES[cmd_key]
                    help_content += f"  {cmd_info['example']}\n    {cmd_info['description']}\n\n"
            help_content += "\n"
        
        help_content += "SHORTCUTS:\n"
        help_content += "  tab - autocomplete command\n"
        help_content += "  up/down arrows - navigate command history\n"
        help_content += "  enter - execute command\n\n"
        
        help_content += "NOTES:\n"
        help_content += "  commands are case-insensitive\n"
        help_content += "  component names must match configured components exactly\n"
        help_content += "  pulse width values are validated against component ranges\n"
        help_content += "  'move all' command clamps values to individual component ranges\n"
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
    
    #focus command entry
    def focus_command_entry(self):
        if self.command_entry:
            self.command_entry.focus_set()
    
    #update autocomplete cache when components change (call this when components are renamed)
    def update_autocomplete_cache(self):
        self._build_autocomplete_cache()


class ConsoleLogger:
    #console logging widget
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="console log")
        self.pending_messages = []
        self.console_ready = False
        
        self._create_console()
    
    #create console display
    def _create_console(self):
        self.console = scrolledtext.ScrolledText(
            self.frame, 
            height=8, 
            wrap=tk.WORD, 
            state=tk.DISABLED, 
            font=("Consolas", 9)
        )
        self.console.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.console_ready = True
        self._process_pending_messages()
    
    #log message to console
    def log_message(self, message):
        if self.console_ready:
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, f"{message}\n")
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        else:
            self.pending_messages.append(message)
    
    #process pending messages
    def _process_pending_messages(self):
        for message in self.pending_messages:
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, f"{message}\n")
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        self.pending_messages.clear()
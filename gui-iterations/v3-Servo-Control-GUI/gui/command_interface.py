#command terminal and console interface

import tkinter as tk
from tkinter import ttk, scrolledtext
import re
from core.validation import COMMAND_HISTORY_LIMIT

#command templates for terminal interface
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
        "example": "move head_1 to 1500"
    },
    
    #component configuration commands
    "set_min": {
        "pattern": "set {component} min {value}",
        "description": "set minimum pulse width for component",
        "example": "set head_1 min 150"
    },
    "set_max": {
        "pattern": "set {component} max {value}",
        "description": "set maximum pulse width for component", 
        "example": "set head_1 max 600"
    },
    "set_default": {
        "pattern": "set {component} default {value}",
        "description": "set default position for component",
        "example": "set head_1 default 375"
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
    
    #bulk configuration commands
    "set_all_min": {
        "pattern": "set all min {value}",
        "description": "set minimum pulse width for all components",
        "example": "set all min 150"
    },
    "set_all_max": {
        "pattern": "set all max {value}",
        "description": "set maximum pulse width for all components",
        "example": "set all max 600"
    },
    "set_all_default": {
        "pattern": "set all default {value}",
        "description": "set default position for all components",
        "example": "set all default 375"
    },
    "set_all_move": {
        "pattern": "set all move {value}",
        "description": "move all components to specified position",
        "example": "set all move 375"
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
        matches = []
        
        for option in self.autocomplete_cache:
            if option.startswith(current_text):
                matches.append(option)
        
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
    
    #build autocomplete cache
    def _build_autocomplete_cache(self):
        self.autocomplete_cache = []
        
        #add command patterns
        for cmd_info in COMMAND_TEMPLATES.values():
            self.autocomplete_cache.append(cmd_info["pattern"].lower())
        
        #add component-specific patterns
        for component_name in self.state.servo_configurations.keys():
            self.autocomplete_cache.extend([
                f"move {component_name} to ",
                f"set {component_name} min ",
                f"set {component_name} max ",
                f"set {component_name} default "
            ])
        
        #add bulk patterns
        self.autocomplete_cache.extend([
            "set all min ",
            "set all max ",
            "set all default ",
            "set all move "
        ])
    
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
    
    #simplified command parsing
    def _parse_command(self, command_text):
        #exact matches first
        for cmd_key, cmd_info in COMMAND_TEMPLATES.items():
            pattern = cmd_info["pattern"].lower()
            
            if command_text == pattern:
                return cmd_key, {}
        
        #pattern matches with variables
        for cmd_key, cmd_info in COMMAND_TEMPLATES.items():
            pattern = cmd_info["pattern"].lower()
            
            #simple pattern matching without regex
            if "{component}" in pattern and "{value}" in pattern:
                #move/set commands
                if pattern.startswith("move ") and " to " in command_text:
                    parts = command_text.split(" to ")
                    if len(parts) == 2:
                        component = parts[0].replace("move ", "").strip()
                        value = parts[1].strip()
                        return cmd_key, {"component": component, "value": value}
                
                elif pattern.startswith("set ") and not pattern.startswith("set all"):
                    #set component commands
                    if " min " in command_text:
                        parts = command_text.split(" min ")
                        if len(parts) == 2:
                            component = parts[0].replace("set ", "").strip()
                            value = parts[1].strip()
                            return cmd_key, {"component": component, "value": value}
                    elif " max " in command_text:
                        parts = command_text.split(" max ")
                        if len(parts) == 2:
                            component = parts[0].replace("set ", "").strip()
                            value = parts[1].strip()
                            return cmd_key, {"component": component, "value": value}
                    elif " default " in command_text:
                        parts = command_text.split(" default ")
                        if len(parts) == 2:
                            component = parts[0].replace("set ", "").strip()
                            value = parts[1].strip()
                            return cmd_key, {"component": component, "value": value}
            
            elif "{value}" in pattern:
                #single value commands
                if pattern.startswith("set all "):
                    if " min " in command_text:
                        value = command_text.replace("set all min ", "").strip()
                        return "set_all_min", {"value": value}
                    elif " max " in command_text:
                        value = command_text.replace("set all max ", "").strip()
                        return "set_all_max", {"value": value}
                    elif " default " in command_text:
                        value = command_text.replace("set all default ", "").strip()
                        return "set_all_default", {"value": value}
                    elif " move " in command_text:
                        value = command_text.replace("set all move ", "").strip()
                        return "set_all_move", {"value": value}
                
                elif pattern.startswith("record "):
                    value = command_text.replace("record ", "").strip()
                    return cmd_key, {"delay": value}
        
        return None
    
    #execute parsed command
    def _execute_command(self, command_type, args):
        if command_type == "connect":
            self._cmd_connect()
        elif command_type == "disconnect":
            self._cmd_disconnect()
        elif command_type == "move":
            self._cmd_move(args.get("component"), args.get("value"))
        elif command_type == "set_min":
            self._cmd_set_range(args.get("component"), args.get("value"), None)
        elif command_type == "set_max":
            self._cmd_set_range(args.get("component"), None, args.get("value"))
        elif command_type == "set_default":
            self._cmd_set_default(args.get("component"), args.get("value"))
        elif command_type == "set_all_min":
            self._cmd_set_all_config("min", args.get("value"))
        elif command_type == "set_all_max":
            self._cmd_set_all_config("max", args.get("value"))
        elif command_type == "set_all_default":
            self._cmd_set_all_config("default", args.get("value"))
        elif command_type == "set_all_move":
            self._cmd_set_all_move(args.get("value"))
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
    
    #command implementations
    def _cmd_connect(self):
        if self.state.is_connected:
            self.log_callback("already connected to serial port")
        else:
            success = self.serial_connection.connect()
            if success:
                self.log_callback("connected to serial port successfully")
            else:
                self.log_callback("failed to connect to serial port")
    
    def _cmd_disconnect(self):
        if not self.state.is_connected:
            self.log_callback("not connected to serial port")
        else:
            success = self.serial_connection.disconnect()
            if success:
                self.log_callback("disconnected from serial port")
            else:
                self.log_callback("failed to disconnect from serial port")
    
    def _cmd_move(self, component_name, value_str):
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
                if self.state.is_connected:
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
    
    def _cmd_set_range(self, component_name, min_val, max_val):
        if not component_name:
            self.log_callback("component name required")
            return
        
        if component_name not in self.state.servo_configurations:
            self.log_callback(f"component '{component_name}' not found")
            return
        
        config = self.state.servo_configurations[component_name]
        
        try:
            if min_val is not None:
                new_min = int(float(min_val))
                new_max = config["pulse_max"]
                action = "minimum"
            else:
                new_min = config["pulse_min"]
                new_max = int(float(max_val))
                action = "maximum"
            
            if self.state.update_component_pulse_range(component_name, new_min, new_max):
                self.log_callback(f"updated {action} pulse width for {component_name} to {new_min if min_val else new_max}")
            else:
                self.log_callback(f"failed to update {action} pulse width for {component_name}")
                
        except ValueError:
            self.log_callback(f"invalid pulse width value")
    
    def _cmd_set_default(self, component_name, value_str):
        if not component_name or not value_str:
            self.log_callback("invalid set default command")
            return
        
        if component_name not in self.state.servo_configurations:
            self.log_callback(f"component '{component_name}' not found")
            return
        
        try:
            default_pos = int(float(value_str))
            config = self.state.servo_configurations[component_name]
            
            if not (config["pulse_min"] <= default_pos <= config["pulse_max"]):
                self.log_callback(f"default position {default_pos} outside range [{config['pulse_min']}, {config['pulse_max']}] for {component_name}")
                return
            
            if self.state.update_component_setting(component_name, "default_position", default_pos):
                self.log_callback(f"set default position for {component_name} to {default_pos}")
            else:
                self.log_callback(f"failed to set default position for {component_name}")
                
        except ValueError:
            self.log_callback(f"invalid default position value: {value_str}")
    
    def _cmd_set_all_config(self, config_type, value_str):
        if not value_str:
            self.log_callback(f"value required for set all {config_type}")
            return
        
        try:
            value = int(float(value_str))
            success_count = 0
            total_components = len(self.state.servo_configurations)
            
            for component_name in self.state.servo_configurations.keys():
                config = self.state.servo_configurations[component_name]
                
                if config_type == "min":
                    if value < config["pulse_max"]:
                        if self.state.update_component_pulse_range(component_name, value, config["pulse_max"]):
                            success_count += 1
                elif config_type == "max":
                    if value > config["pulse_min"]:
                        if self.state.update_component_pulse_range(component_name, config["pulse_min"], value):
                            success_count += 1
                elif config_type == "default":
                    if config["pulse_min"] <= value <= config["pulse_max"]:
                        if self.state.update_component_setting(component_name, "default_position", value):
                            success_count += 1
            
            self.log_callback(f"updated {config_type} value to {value} for {success_count}/{total_components} components")
            
            if success_count < total_components:
                self.log_callback(f"warning: {total_components - success_count} components failed validation")
                
        except ValueError:
            self.log_callback(f"invalid {config_type} value: {value_str}")
    
    def _cmd_set_all_move(self, value_str):
        if not value_str:
            self.log_callback("pulse width value required for move all")
            return
        
        try:
            pulse_width = int(float(value_str))
            success_count = 0
            command_count = 0
            total_components = len(self.state.servo_configurations)
            
            for component_name, config in self.state.servo_configurations.items():
                if config["pulse_min"] <= pulse_width <= config["pulse_max"]:
                    if self.state.update_servo_position(component_name, pulse_width):
                        success_count += 1
                        
                        if self.state.is_connected:
                            servo_index = config["index"]
                            if self.serial_connection.send_command(f"SP:{servo_index}:{pulse_width}"):
                                command_count += 1
            
            if self.state.is_connected:
                self.log_callback(f"moved {success_count}/{total_components} components to {pulse_width} (sent {command_count} commands)")
            else:
                self.log_callback(f"moved {success_count}/{total_components} components to {pulse_width} (not connected)")
            
            if success_count < total_components:
                self.log_callback(f"warning: {total_components - success_count} components outside valid range")
                
        except ValueError:
            self.log_callback(f"invalid pulse width value: {value_str}")
    
    def _cmd_save_config(self):
        success = self.state.save_config_to_file()
        if success:
            self.log_callback("servo configuration saved successfully")
        else:
            self.log_callback("failed to save servo configuration")
    
    def _cmd_reset_all(self):
        reset_commands = self.state.reset_all_servos_to_defaults()
        
        if self.state.is_connected:
            success_count = 0
            for servo_index, pulse_width in reset_commands:
                if self.serial_connection.send_command(f"SP:{servo_index}:{pulse_width}"):
                    success_count += 1
            
            self.log_callback(f"reset {success_count}/{len(reset_commands)} servos to default positions")
        else:
            self.log_callback(f"reset {len(reset_commands)} servos to default positions (not connected)")
    
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
        
        if not self.state.is_connected:
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
    
    def _cmd_help(self):
        self.log_callback("=== available commands ===")
        
        categories = {
            "connection": ["connect", "disconnect"],
            "movement": ["move"],
            "configuration": ["set_min", "set_max", "set_default", "save_config", "reset_all"],
            "bulk_configuration": ["set_all_min", "set_all_max", "set_all_default", "set_all_move"],
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
        self.log_callback(f"serial connection: {'connected' if self.state.is_connected else 'disconnected'}")
        self.log_callback(f"configured components: {len(self.state.servo_configurations)}")
        self.log_callback(f"sequence keyframes: {self.sequence_manager.get_keyframe_count()}")
        
        if self.sequence_manager.has_keyframes():
            duration = self.sequence_manager.get_total_duration()
            self.log_callback(f"sequence duration: {duration:.1f}s")
        
        current_tool = self.content_switcher.get_selected_content()
        self.log_callback(f"current tool: {current_tool}")
    
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
            "MOVEMENT COMMANDS": ["move"],
            "CONFIGURATION COMMANDS": ["set_min", "set_max", "set_default", "save_config", "reset_all"],
            "BULK CONFIGURATION COMMANDS": ["set_all_min", "set_all_max", "set_all_default", "set_all_move"],
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
        help_content += "  component names must match configured components\n"
        help_content += "  pulse width values are validated against component ranges\n"
        help_content += "  bulk commands apply to all components for testing\n"
        
        help_text.insert(tk.END, help_content)
        help_text.config(state=tk.DISABLED)
    
    #focus command entry
    def focus_command_entry(self):
        if self.command_entry:
            self.command_entry.focus_set()
    
    #update autocomplete cache when components change
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
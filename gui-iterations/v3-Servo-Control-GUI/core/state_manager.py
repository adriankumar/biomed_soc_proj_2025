#centralised state management for servo control system with reliable event publishing

import json
from tkinter import filedialog, messagebox
from hardware.servo_config import DEFAULT_COMPONENT_CONFIGS, MAX_SERVOS, PWM_FREQUENCY
from core.validation import validate_pulse_range, validate_pulse_within_range
from core.event_system import publish, Events

class ServoState:
    #manages servo configurations and system state
    def __init__(self, config_data=None):
        #load configuration
        if config_data and "components" in config_data:
            self.servo_configurations = config_data["components"].copy()
        else:
            self.servo_configurations = DEFAULT_COMPONENT_CONFIGS.copy()
        
        #system state
        self.num_servos = MAX_SERVOS
        self.pwm_freq = PWM_FREQUENCY
        self.is_connected = False
        
        #sequence manager reference
        self.sequence_manager = None
    
    #set sequence manager reference
    def set_sequence_manager(self, sequence_manager):
        self.sequence_manager = sequence_manager
    
    #get component configuration
    def get_component_config(self, component_name):
        return self.servo_configurations.get(component_name, {})
    
    #update component setting with validation and events
    def update_component_setting(self, component_name, setting, value):
        if component_name not in self.servo_configurations:
            return False
        
        config = self.servo_configurations[component_name]
        if setting not in config:
            return False
        
        old_value = config[setting]
        if old_value == value:
            return True
        
        config[setting] = value
        
        #publish event immediately
        publish(Events.COMPONENT_SETTING_CHANGED, component_name, setting, value, component_name=component_name)
        
        return True
    
    #update component pulse range with validation and events
    def update_component_pulse_range(self, component_name, pulse_min, pulse_max):
        if component_name not in self.servo_configurations:
            return False
        
        range_result = validate_pulse_range(pulse_min, pulse_max)
        if not range_result.is_valid:
            return False
        
        config = self.servo_configurations[component_name]
        config["pulse_min"] = pulse_min
        config["pulse_max"] = pulse_max
        
        #ensure default and current positions are within new range
        if not (pulse_min <= config["default_position"] <= pulse_max):
            config["default_position"] = (pulse_min + pulse_max) // 2
        
        if not (pulse_min <= config["current_position"] <= pulse_max):
            config["current_position"] = config["default_position"]
        
        #publish event immediately
        publish(Events.COMPONENT_RANGE_CHANGED, component_name, component_name=component_name)
        
        return True
    
    #update servo position with validation and events
    def update_servo_position(self, component_name, pulse_width):
        if component_name not in self.servo_configurations:
            return False
        
        config = self.servo_configurations[component_name]
        range_result = validate_pulse_within_range(
            pulse_width, config["pulse_min"], config["pulse_max"], component_name
        )
        
        if not range_result.is_valid:
            return False
        
        config["current_position"] = pulse_width
        
        #publish event immediately
        publish(Events.COMPONENT_POSITION_CHANGED, component_name, pulse_width, component_name=component_name)
        
        return True
    
    #swap component indices with immediate event publishing
    def swap_component_indices(self, component1, component2):
        if component1 not in self.servo_configurations or component2 not in self.servo_configurations:
            return False
        
        config1 = self.servo_configurations[component1]
        config2 = self.servo_configurations[component2]
        
        #perform the swap
        config1["index"], config2["index"] = config2["index"], config1["index"]
        
        #publish event immediately for both components
        publish(Events.COMPONENT_INDEX_SWAPPED, component1, component2)
        
        #also publish individual setting changes for each component
        publish(Events.COMPONENT_SETTING_CHANGED, component1, "index", config1["index"], component_name=component1)
        publish(Events.COMPONENT_SETTING_CHANGED, component2, "index", config2["index"], component_name=component2)
        
        return True
    
    #reset all servos to default positions with events
    def reset_all_servos_to_defaults(self):
        reset_commands = []
        
        for component_name, config in self.servo_configurations.items():
            default_pos = config["default_position"]
            config["current_position"] = default_pos
            reset_commands.append((config["index"], default_pos))
        
        #publish global reset event
        publish(Events.ALL_SERVOS_RESET, reset_commands)
        
        #also publish individual position changes for each component
        for component_name, config in self.servo_configurations.items():
            publish(Events.COMPONENT_POSITION_CHANGED, component_name, config["current_position"], component_name=component_name)
        
        return reset_commands
    
    #set connection status with events
    def set_connection_status(self, connected):
        if connected != self.is_connected:
            self.is_connected = connected
            publish(Events.CONNECTION_CHANGED, connected)
    
    #get servo config by index
    def get_servo_config_by_index(self, servo_index):
        for component_name, config in self.servo_configurations.items():
            if config["index"] == servo_index:
                return component_name, config
        return None, None
    
    #get current positions as component dictionary
    def get_current_component_positions(self):
        positions = {}
        for component_name, config in self.servo_configurations.items():
            positions[component_name] = config["current_position"]
        return positions
    
    #save configuration to file
    def save_config_to_file(self):
        try:
            file_path = filedialog.asksaveasfilename(
                title="save servo configuration",
                defaultextension=".json",
                filetypes=[("json files", "*.json"), ("all files", "*.*")]
            )
            
            if file_path:
                config_data = {
                    "pwm_frequency": self.pwm_freq,
                    "components": {}
                }
                
                for component_name, config in self.servo_configurations.items():
                    config_data["components"][component_name] = {
                        "index": config["index"],
                        "pulse_min": config["pulse_min"],
                        "pulse_max": config["pulse_max"],
                        "default_position": config["default_position"],
                        "current_position": config["default_position"]
                    }
                
                with open(file_path, 'w') as file:
                    json.dump(config_data, file, indent=2)
                
                messagebox.showinfo("config saved", f"configuration saved successfully to:\n{file_path}")
                return True
                
        except Exception as e:
            messagebox.showerror("save error", f"failed to save configuration:\n{str(e)}")
            return False
    
    #cleanup resources
    def cleanup(self):
        self.sequence_manager = None
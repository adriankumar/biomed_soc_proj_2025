import json
import os
from tkinter import filedialog, messagebox
from hardware.servo_config import DEFAULT_COMPONENT_CONFIGS, MAX_SERVOS, PWM_FREQUENCY, COMPONENT_GROUPS
from core.validation import validate_pulse_range, validate_pulse_within_range
from core.event_system import publish, Events

class ServoState:
    #manages servo configurations and system state with component groups as order source
    def __init__(self, config_data=None):
        #component groups are the authoritative order source
        self.component_groups = {}
        for group_name, components in COMPONENT_GROUPS.items():
            self.component_groups[group_name] = components.copy()
        
        #servo configurations as pure lookup table (no order dependency)
        self.servo_configurations = DEFAULT_COMPONENT_CONFIGS.copy()
        
        #load config data if provided (creates entries for renamed components)
        if config_data:
            self._load_config_data(config_data)
        
        #system state
        self.num_servos = MAX_SERVOS
        self.pwm_freq = PWM_FREQUENCY
        self.is_connected = False

        #last sent pwm positions to hardware (hardware-truth)
        self.last_sent_positions = {}

        #realtime smoothing mode for live editors (sliders/keyframe drag)
        self.realtime_smoothing_enabled = True
        
        #sequence manager reference
        self.sequence_manager = None

        #initialise last sent positions from defaults
        for component_name, cfg in self.servo_configurations.items():
            self.last_sent_positions[component_name] = cfg.get("default_position", 375)

        #live persistence for custom configs
        self.live_persist_enabled = False
        self.live_config_path = None

        #enable live persistence and seed last sent from loaded config if provided
        if config_data and isinstance(config_data, dict):
            #seed last sent from saved config if available
            if "last_sent_positions" in config_data and isinstance(config_data["last_sent_positions"], dict):
                for name, value in config_data["last_sent_positions"].items():
                    if name in self.servo_configurations:
                        cfg = self.servo_configurations[name]
                        clamped = max(cfg["pulse_min"], min(cfg["pulse_max"], int(value)))
                        self.last_sent_positions[name] = clamped

            #enable live persistence only for loaded custom configs with path
            if config_data.get("_custom_config") and config_data.get("_config_file_path"):
                self.live_config_path = config_data.get("_config_file_path")
                self.live_persist_enabled = True

        #fast lookup maps for index/name resolution
        self.name_to_index = {}
        self.index_to_name = {}
        self._rebuild_index_maps()
    
    #load configuration data with component creation for renamed components
    def _load_config_data(self, config_data):
        #load component groups if saved (for proper order preservation)
        if "component_groups" in config_data:
            for group_name, components in config_data["component_groups"].items():
                if group_name in self.component_groups:
                    self.component_groups[group_name] = components.copy()
        
        #create servo configurations for all loaded components (including renamed ones)
        if "components" in config_data:
            for component_name, loaded_config in config_data["components"].items():
                if component_name in self.servo_configurations:
                    #existing component - overlay loaded values
                    self.servo_configurations[component_name].update(loaded_config)
                else:
                    #new/renamed component - create entry with default structure
                    default_config = {
                        "index": 0,
                        "pulse_min": 150,
                        "pulse_max": 600,
                        "default_position": 375,
                        "current_position": 375
                    }
                    #overlay loaded values onto default structure
                    default_config.update(loaded_config)
                    self.servo_configurations[component_name] = default_config

            #prune any components not present in loaded config to prevent stale defaults
            loaded_names = set(config_data["components"].keys())
            for name in list(self.servo_configurations.keys()):
                if name not in loaded_names:
                    self.servo_configurations.pop(name, None)
        
        #last sent positions are seeded in __init__ after initialisation

    #rebuild fast index/name maps from configurations
    def _rebuild_index_maps(self):
        self.name_to_index = {}
        self.index_to_name = {}
        for name, cfg in self.servo_configurations.items():
            idx = cfg.get("index")
            self.name_to_index[name] = idx
            #only keep first mapping for an index
            if idx not in self.index_to_name:
                self.index_to_name[idx] = name
    
    #set sequence manager reference
    def set_sequence_manager(self, sequence_manager):
        self.sequence_manager = sequence_manager

    #set live persistence for this session
    def set_live_persistence(self, file_path):
        self.live_config_path = file_path
        self.live_persist_enabled = bool(file_path)
    
    #get component configuration using name lookup
    def get_component_config(self, component_name):
        return self.servo_configurations.get(component_name, {})
    
    #get component group list in order
    def get_component_group(self, group_name):
        return self.component_groups.get(group_name, [])
    
    #get all component groups
    def get_all_component_groups(self):
        return self.component_groups.copy()
    
    #rename component with simplified approach using groups for order
    def rename_component(self, old_name, new_name):
        #validate new name
        new_name = new_name.strip()
        
        if not new_name:
            return False, "component name cannot be empty"
        
        if old_name == new_name:
            return True, "name unchanged"
        
        if new_name in self.servo_configurations:
            return False, f"component name '{new_name}' already exists"
        
        if old_name not in self.servo_configurations:
            return False, f"component '{old_name}' does not exist"
        
        #simple rename operation - groups preserve order, dict is just lookup
        try:
            #update servo configurations dictionary (pure lookup table)
            config_data = self.servo_configurations.pop(old_name)
            self.servo_configurations[new_name] = config_data
            
            #update component groups lists (order authority)
            for group_name, components in self.component_groups.items():
                if old_name in components:
                    index = components.index(old_name)
                    components[index] = new_name

            #migrate last sent position if available
            if old_name in self.last_sent_positions:
                self.last_sent_positions[new_name] = self.last_sent_positions.pop(old_name)

            #rebuild index maps to reflect rename
            self._rebuild_index_maps()
            
            #publish rename event for any listeners
            publish(Events.COMPONENT_SETTING_CHANGED, new_name, "name", new_name, component_name=new_name)

            #live persist rename changes
            if self.live_persist_enabled and self.live_config_path:
                self._live_persist_rename(old_name, new_name)

            return True, f"renamed '{old_name}' to '{new_name}'"
            
        except Exception as e:
            #simple rollback on any failure
            if new_name in self.servo_configurations:
                config_data = self.servo_configurations.pop(new_name)
                self.servo_configurations[old_name] = config_data
            
            for group_name, components in self.component_groups.items():
                if new_name in components:
                    index = components.index(new_name)
                    components[index] = old_name
            
            return False, f"rename failed: {str(e)}"

        
    
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

        #live persist supported settings
        if self.live_persist_enabled and self.live_config_path and setting in ("default_position", "index"):
            self._live_persist_component_setting(component_name, setting, value)

        #keep index/name maps in sync
        if setting == "index":
            self._rebuild_index_maps()

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

        #clamp last sent to new range and persist
        if component_name in self.last_sent_positions:
            self.last_sent_positions[component_name] = max(pulse_min, min(pulse_max, self.last_sent_positions[component_name]))
        if self.live_persist_enabled and self.live_config_path:
            self._live_persist_range(component_name, pulse_min, pulse_max)

        return True
    
    #update servo position immediately regardless of serial connection status
    def update_servo_position(self, component_name, pulse_width):
        if component_name not in self.servo_configurations:
            return False
        
        config = self.servo_configurations[component_name]
        
        #validate pulse width against component constraints
        range_result = validate_pulse_within_range(
            pulse_width, config["pulse_min"], config["pulse_max"], component_name
        )
        
        if not range_result.is_valid:
            return False
        
        #always update current position in state (decoupled from serial communication)
        config["current_position"] = pulse_width
        
        #publish position change event immediately for all listeners
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

        #live persist index swap
        if self.live_persist_enabled and self.live_config_path:
            self._live_persist_index(component1, config1["index"])
            self._live_persist_index(component2, config2["index"])

        #rebuild index maps after swap
        self._rebuild_index_maps()

        return True
    
    #reset all servos to default positions with events
    def reset_all_servos_to_defaults(self):
        reset_commands = []
        
        #use component groups order to ensure consistent reset order
        for group_name, components in self.component_groups.items():
            for component_name in components:
                if component_name in self.servo_configurations:
                    config = self.servo_configurations[component_name]
                    default_pos = config["default_position"]
                    config["current_position"] = default_pos
                    reset_commands.append((config["index"], default_pos))
        
        #publish global reset event
        publish(Events.ALL_SERVOS_RESET, reset_commands)
        
        #publish individual position changes using group order
        for group_name, components in self.component_groups.items():
            for component_name in components:
                if component_name in self.servo_configurations:
                    config = self.servo_configurations[component_name]
                    publish(Events.COMPONENT_POSITION_CHANGED, component_name, config["current_position"], component_name=component_name)
        
        return reset_commands
    
    #set connection status with events
    def set_connection_status(self, connected):
        if connected != self.is_connected:
            self.is_connected = connected
            publish(Events.CONNECTION_CHANGED, connected)

    #persist last sent pwm to loaded config immediately after successful serial send
    def update_last_sent(self, component_name, pulse_width):
        if component_name in self.servo_configurations:
            cfg = self.servo_configurations[component_name]
            clamped = max(cfg["pulse_min"], min(cfg["pulse_max"], int(pulse_width)))
            #update gui state to reflect hardware-truth
            self.update_servo_position(component_name, clamped)
            #update last sent position
            self.last_sent_positions[component_name] = clamped
            #persist if enabled
            if self.live_persist_enabled and self.live_config_path:
                self._live_persist_last_sent()

    def update_last_sent_by_index(self, servo_index, pulse_width):
        comp_name = self.index_to_name.get(servo_index)
        if comp_name:
            self.update_last_sent(comp_name, pulse_width)

    #get last sent pwm for component
    def get_last_sent(self, component_name):
        return self.last_sent_positions.get(
            component_name,
            self.servo_configurations.get(component_name, {}).get("default_position", 375)
        )

    

    #set realtime smoothing mode for live editors
    def set_realtime_smoothing_enabled(self, enabled):
        if bool(enabled) != self.realtime_smoothing_enabled:
            self.realtime_smoothing_enabled = bool(enabled)
            publish(Events.REALTIME_SMOOTHING_MODE_CHANGED, self.realtime_smoothing_enabled)
    
    #get servo config by index
    def get_servo_config_by_index(self, servo_index):
        name = self.index_to_name.get(servo_index)
        if name and name in self.servo_configurations:
            return name, self.servo_configurations[name]
        return None, None
    
    #get current positions using component groups order for reliable state tracking
    def get_current_component_positions(self):
        positions = {}
        for group_name, components in self.component_groups.items():
            for component_name in components:
                if component_name in self.servo_configurations:
                    config = self.servo_configurations[component_name]
                    positions[component_name] = config["current_position"]
        return positions
    
    #save configuration to file using component groups for order
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
                    "component_groups": self.component_groups.copy(),
                    "components": {}
                }
                
                #save configurations using component groups order (not dict iteration)
                for group_name, components in self.component_groups.items():
                    for component_name in components:
                        if component_name in self.servo_configurations:
                            config = self.servo_configurations[component_name]
                            config_data["components"][component_name] = {
                                "index": config["index"],
                                "pulse_min": config["pulse_min"],
                                "pulse_max": config["pulse_max"],
                                "default_position": config["default_position"],
                                "current_position": config["default_position"]
                            }
                
                #include last sent pwm positions
                config_data["last_sent_positions"] = {}
                for name in list(self.servo_configurations.keys()):
                    if name in self.last_sent_positions:
                        cfg = self.servo_configurations[name]
                        val = max(cfg["pulse_min"], min(cfg["pulse_max"], int(self.last_sent_positions[name])))
                        config_data["last_sent_positions"][name] = val

                with open(file_path, 'w') as file:
                    json.dump(config_data, file, indent=2)

                messagebox.showinfo("config saved", f"configuration saved successfully to:\n{file_path}")
                #enable live persistence for this saved file
                self.set_live_persistence(file_path)
                return True
                
        except Exception as e:
            messagebox.showerror("save error", f"failed to save configuration:\n{str(e)}")
            return False
    
    #cleanup resources
    def cleanup(self):
        self.sequence_manager = None

    #read current live config json
    def _live_read_config(self):
        try:
            if not (self.live_persist_enabled and self.live_config_path):
                return None
            with open(self.live_config_path, 'r') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    #write live config json atomically
    def _live_write_config(self, data):
        try:
            if not (self.live_persist_enabled and self.live_config_path):
                return False
            temp_path = self.live_config_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, self.live_config_path)
            return True
        except Exception:
            return False

    #persist only last sent positions
    def _live_persist_last_sent(self):
        data = self._live_read_config()
        if data is None:
            return False
        out = {}
        for name, cfg in self.servo_configurations.items():
            if name in self.last_sent_positions:
                val = max(cfg["pulse_min"], min(cfg["pulse_max"], int(self.last_sent_positions[name])))
                out[name] = val
        data["last_sent_positions"] = out
        return self._live_write_config(data)

    #persist a single component setting change
    def _live_persist_component_setting(self, component_name, setting, value):
        data = self._live_read_config()
        if data is None:
            return False
        components = data.get("components") or {}
        if component_name in components:
            components[component_name][setting] = value
        data["components"] = components
        #also persist last sent if needed
        return self._live_write_config(data)

    #persist pulse range and clamp last sent
    def _live_persist_range(self, component_name, pulse_min, pulse_max):
        data = self._live_read_config()
        if data is None:
            return False
        components = data.get("components") or {}
        if component_name in components:
            components[component_name]["pulse_min"] = pulse_min
            components[component_name]["pulse_max"] = pulse_max
        #rebuild last sent section with clamping
        self._live_write_config(data)
        return self._live_persist_last_sent()

    #persist index after swap or update
    def _live_persist_index(self, component_name, index_value):
        return self._live_persist_component_setting(component_name, "index", index_value)

    #persist rename across sections
    def _live_persist_rename(self, old_name, new_name):
        data = self._live_read_config()
        if data is None:
            return False
        #components
        components = data.get("components") or {}
        if old_name in components:
            components[new_name] = components.pop(old_name)
        data["components"] = components
        #component groups
        groups = data.get("component_groups") or {}
        for gname, items in groups.items():
            for i, nm in enumerate(list(items)):
                if nm == old_name:
                    items[i] = new_name
        data["component_groups"] = groups
        #last sent positions
        lsp = data.get("last_sent_positions") or {}
        if old_name in lsp:
            lsp[new_name] = lsp.pop(old_name)
        data["last_sent_positions"] = lsp
        return self._live_write_config(data)

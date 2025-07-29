import copy
from core.event_system import subscribe, Events
from core.curve_interpolation import BezierCurveComputer

class SequenceTranslator:
    #handles translation between v3 sequence format and motion editor format
    
    def __init__(self, state_manager, log_callback=None):
        self.state = state_manager                    #reference to v3 state manager
        self.log_callback = log_callback              #for debugging messages
        self.curve_computer = BezierCurveComputer()   #mathematical curve computation
        
        #component name to motion editor mapping
        self.component_to_editor_map = {}    #maps component names to editor servo ids
        self.editor_to_component_map = {}    #reverse mapping for translation back
        
        #subscribe to component changes for dynamic updates
        subscribe([
            Events.COMPONENT_SETTING_CHANGED,
            Events.COMPONENT_RANGE_CHANGED
        ], self._on_component_configuration_changed)
        
        self._build_component_mappings()
    
    #create bidirectional mapping between component names and editor servo ids
    def _build_component_mappings(self):
        self.component_to_editor_map.clear()
        self.editor_to_component_map.clear()
        
        editor_id = 0
        
        #iterate through component groups to maintain order
        component_groups = self.state.get_all_component_groups()
        for group_name, component_list in component_groups.items():
            for component_name in component_list:
                if component_name in self.state.servo_configurations:
                    self.component_to_editor_map[component_name] = editor_id
                    self.editor_to_component_map[editor_id] = component_name
                    editor_id += 1
        
        if self.log_callback:
            self.log_callback(f"built component mappings for {len(self.component_to_editor_map)} components")
    
    #handle component configuration changes from v3 system
    def _on_component_configuration_changed(self, event_type, *args, **kwargs):
        if event_type == Events.COMPONENT_SETTING_CHANGED:
            component_name, setting, value = args
            if setting == "name":  #component was renamed
                self._build_component_mappings()
                if self.log_callback:
                    self.log_callback(f"rebuilt mappings due to component rename: {component_name}")
    
    #convert v3 sequence format to motion editor format
    def convert_v3_to_editor_format(self, v3_sequence_data):
        if not v3_sequence_data or "keyframes" not in v3_sequence_data:
            return {}
        
        editor_sequences = {}  #motion editor format: {servo_id: [keyframe_list]}
        v3_keyframes = v3_sequence_data["keyframes"]
        
        for keyframe_data in v3_keyframes:
            keyframe_time = keyframe_data["absolute_time"]
            component_positions = keyframe_data["component_positions"]
            
            #convert each component position to editor format
            for component_name, position_value in component_positions.items():
                if component_name not in self.component_to_editor_map:
                    if self.log_callback:
                        self.log_callback(f"skipping unknown component: {component_name}")
                    continue
                
                editor_servo_id = self.component_to_editor_map[component_name]
                
                #create editor keyframe structure
                editor_keyframe = {
                    'time': keyframe_time,
                    'angle': position_value,  #motion editor uses 'angle' terminology
                    'cp_in': None,           #will be auto-generated if not customised
                    'cp_out': None
                }
                
                #check for existing interpolation data (user customised curves)
                if isinstance(position_value, dict) and "interpolation" in position_value:
                    interpolation_data = position_value["interpolation"]
                    editor_keyframe['angle'] = position_value["value"]
                    
                    #preserve custom control points if they exist
                    if "cp_out" in interpolation_data:
                        editor_keyframe['cp_out'] = copy.deepcopy(interpolation_data["cp_out"])
                    if "cp_in" in interpolation_data:
                        editor_keyframe['cp_in'] = copy.deepcopy(interpolation_data["cp_in"])
                elif isinstance(position_value, (int, float)):
                    #simple numeric value, no custom interpolation
                    editor_keyframe['angle'] = position_value
                
                #add to editor sequences
                if editor_servo_id not in editor_sequences:
                    editor_sequences[editor_servo_id] = []
                
                editor_sequences[editor_servo_id].append(editor_keyframe)
        
        #sort keyframes by time and ensure control points for each sequence
        for servo_id, keyframe_list in editor_sequences.items():
            keyframe_list.sort(key=lambda kf: kf['time'])
            editor_sequences[servo_id] = self.curve_computer.ensure_control_points_for_sequence(keyframe_list)
        
        if self.log_callback:
            component_count = len(editor_sequences)
            self.log_callback(f"converted v3 sequence to editor format: {component_count} components")
        
        return editor_sequences
    
    #convert motion editor format back to v3 sequence format
    def convert_editor_to_v3_format(self, editor_sequences):
        if not editor_sequences:
            return []
        
        #collect all unique times across all servo sequences
        all_keyframe_times = set()
        for servo_id, keyframe_list in editor_sequences.items():
            for keyframe in keyframe_list:
                all_keyframe_times.add(keyframe['time'])
        
        sorted_times = sorted(list(all_keyframe_times))
        v3_keyframes = []
        
        #create v3 keyframes at each unique time
        for time_index, keyframe_time in enumerate(sorted_times):
            #calculate delay to next keyframe
            if time_index < len(sorted_times) - 1:
                delay_to_next = sorted_times[time_index + 1] - keyframe_time
            else:
                delay_to_next = 1000  #default delay for last keyframe
            
            v3_keyframe = {
                'absolute_time': keyframe_time,
                'delay_to_next': delay_to_next,
                'component_positions': {}
            }
            
            #gather component positions at this time
            for servo_id, keyframe_list in editor_sequences.items():
                if servo_id not in self.editor_to_component_map:
                    if self.log_callback:
                        self.log_callback(f"skipping unmapped servo id: {servo_id}")
                    continue
                
                component_name = self.editor_to_component_map[servo_id]
                
                #find keyframe at this exact time
                matching_keyframe = None
                for keyframe in keyframe_list:
                    if keyframe['time'] == keyframe_time:
                        matching_keyframe = keyframe
                        break
                
                if matching_keyframe:
                    #check if this keyframe has custom interpolation data
                    has_custom_interpolation = (
                        matching_keyframe.get('cp_in') is not None or 
                        matching_keyframe.get('cp_out') is not None
                    )
                    
                    if has_custom_interpolation:
                        #save with interpolation metadata for custom curves
                        position_data = {
                            'value': matching_keyframe['angle'],
                            'interpolation': {
                                'type': 'bezier'
                            }
                        }
                        
                        #include control points if they exist
                        if matching_keyframe.get('cp_out'):
                            position_data['interpolation']['cp_out'] = copy.deepcopy(matching_keyframe['cp_out'])
                        if matching_keyframe.get('cp_in'):
                            position_data['interpolation']['cp_in'] = copy.deepcopy(matching_keyframe['cp_in'])
                        
                        v3_keyframe['component_positions'][component_name] = position_data
                    else:
                        #save as simple numeric value for default curves
                        v3_keyframe['component_positions'][component_name] = matching_keyframe['angle']
            
            v3_keyframes.append(v3_keyframe)
        
        if self.log_callback:
            keyframe_count = len(v3_keyframes)
            self.log_callback(f"converted editor sequence to v3 format: {keyframe_count} keyframes")
        
        return v3_keyframes
    
    #get component constraints for motion editor validation
    def get_component_constraints(self, component_name):
        component_config = self.state.get_component_config(component_name)
        if not component_config:
            return {'min': 0, 'max': 180}  #fallback servo range
        
        return {
            'min': component_config.get('pulse_min', 0),
            'max': component_config.get('pulse_max', 180),
            'default': component_config.get('default_position', 90)
        }
    
    #get all available component names for motion editor selection
    def get_available_components(self):
        return list(self.component_to_editor_map.keys())
    
    #get component name from editor servo id
    def get_component_name_from_editor_id(self, editor_servo_id):
        return self.editor_to_component_map.get(editor_servo_id, f"servo_{editor_servo_id}")
    
    #get editor servo id from component name
    def get_editor_id_from_component_name(self, component_name):
        return self.component_to_editor_map.get(component_name, 0)
    
    #validate that all components in editor sequence exist in v3 system
    def validate_editor_sequence(self, editor_sequences):
        validation_errors = []
        
        for servo_id, keyframe_list in editor_sequences.items():
            if servo_id not in self.editor_to_component_map:
                validation_errors.append(f"servo id {servo_id} has no corresponding component")
                continue
            
            component_name = self.editor_to_component_map[servo_id]
            constraints = self.get_component_constraints(component_name)
            
            #validate each keyframe in the sequence
            for keyframe_index, keyframe in enumerate(keyframe_list):
                angle_value = keyframe.get('angle', 90)
                
                if not (constraints['min'] <= angle_value <= constraints['max']):
                    validation_errors.append(
                        f"component {component_name} keyframe {keyframe_index}: "
                        f"value {angle_value} outside range [{constraints['min']}, {constraints['max']}]"
                    )
        
        return validation_errors
    
    #refresh component mappings when v3 system changes
    def refresh_mappings(self):
        self._build_component_mappings()
    
    #get formatted sequence for esp32 serial communication
    def format_sequence_for_serial(self, editor_sequences):
        formatted_sequences = {}
        
        for servo_id, keyframe_list in editor_sequences.items():
            if servo_id not in self.editor_to_component_map:
                continue
            
            component_name = self.editor_to_component_map[servo_id]
            component_config = self.state.get_component_config(component_name)
            
            if not component_config:
                continue
            
            #get actual hardware servo index from component configuration
            hardware_servo_index = component_config['index']
            
            #format keyframes for serial transmission
            keyframe_parts = []
            for keyframe in keyframe_list:
                time_val = int(round(keyframe['time']))
                angle_val = int(round(keyframe['angle']))
                
                control_point_in = keyframe.get('cp_in')
                control_point_out = keyframe.get('cp_out')
                
                #format control point data for serial protocol
                in_dt_str = str(int(round(control_point_in['dt']))) if control_point_in else ""
                in_da_str = str(int(round(control_point_in['da']))) if control_point_in else ""
                out_dt_str = str(int(round(control_point_out['dt']))) if control_point_out else ""
                out_da_str = str(int(round(control_point_out['da']))) if control_point_out else ""
                
                keyframe_parts.append(f"{time_val},{angle_val},{in_dt_str},{in_da_str},{out_dt_str},{out_da_str}")
            
            formatted_sequences[hardware_servo_index] = ";".join(keyframe_parts)
        
        return formatted_sequences
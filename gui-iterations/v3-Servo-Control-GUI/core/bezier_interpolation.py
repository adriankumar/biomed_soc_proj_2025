import numpy as np
import time
#pure mathematical bezier computation functions for servo motion interpolation

def bezier_point(t, p0, p1, p2, p3):
    #compute single point on cubic bezier curve using bernstein polynomials
    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t
    
    time_val = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    angle_val = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    
    return time_val, angle_val

def control_point_absolute(keyframe, cp_type, servo_config):
    #convert relative control point to absolute coordinates with servo constraints
    cp_key = f'cp_{cp_type}'
    if cp_key not in keyframe or keyframe[cp_key] is None:
        return None
    
    cp_data = keyframe[cp_key]
    abs_time = keyframe['time'] + cp_data['dt']
    abs_angle = keyframe['angle'] + cp_data['da']
    
    #clamp angle to servo constraints
    abs_angle = max(servo_config['pulse_min'], min(servo_config['pulse_max'], abs_angle))
    
    return abs_time, abs_angle

def compute_curve_segment(kf_start, kf_next, servo_config, resolution=100):
    #compute bezier curve segment between two keyframes with optional linear fallback
    start_pos = (kf_start['time'], kf_start['angle'])
    end_pos = (kf_next['time'], kf_next['angle'])
    
    start_cp = control_point_absolute(kf_start, 'out', servo_config)
    end_cp = control_point_absolute(kf_next, 'in', servo_config)
    
    if not start_cp or not end_cp:
        #linear fallback when control points missing
        t_vals = np.linspace(start_pos[0], end_pos[0], resolution)
        a_vals = np.linspace(start_pos[1], end_pos[1], resolution)
        return t_vals, a_vals
    
    #generate bezier curve points
    t_params = np.linspace(0, 1, resolution)
    points = [bezier_point(t, start_pos, start_cp, end_cp, end_pos) for t in t_params]
    
    times, angles = zip(*points) if points else ([], [])
    return np.array(times), np.array(angles)

def ensure_control_points(keyframes, use_smooth_defaults=True):
    #ensure all keyframes have proper control points using cubic bezier defaults
    if not keyframes:
        return
    
    num_kf = len(keyframes)
    default_tension = 0.33 if use_smooth_defaults else 0.0
    
    for i, kf in enumerate(keyframes):
        #incoming control point (not for first keyframe)
        if i > 0:
            if 'cp_in' not in kf or kf['cp_in'] is None:
                prev_kf = keyframes[i-1]
                time_diff = kf['time'] - prev_kf['time']
                dt = max(1, time_diff) * -default_tension
                kf['cp_in'] = {'dt': dt, 'da': 0.0}
        else:
            kf['cp_in'] = None
        
        #outgoing control point (not for last keyframe)
        if i < num_kf - 1:
            if 'cp_out' not in kf or kf['cp_out'] is None:
                next_kf = keyframes[i+1]
                time_diff = next_kf['time'] - kf['time']
                dt = max(1, time_diff) * default_tension
                kf['cp_out'] = {'dt': dt, 'da': 0.0}
        else:
            kf['cp_out'] = None

def generate_playback_points(keyframes, servo_config, time_step=50):
    #generate interpolated pwm points for timed playback using bezier curves
    if len(keyframes) < 2:
        return []
    
    points = []
    
    #generate points for each curve segment
    for i in range(len(keyframes) - 1):
        kf_start = keyframes[i]
        kf_end = keyframes[i + 1]
        
        start_time = kf_start['time']
        end_time = kf_end['time']
        
        #generate points at regular intervals
        current_time = start_time
        while current_time <= end_time:
            #calculate interpolated angle using bezier curve
            if current_time == start_time:
                angle = kf_start['angle']
            elif current_time == end_time:
                angle = kf_end['angle']
            else:
                #bezier interpolation
                t = (current_time - start_time) / (end_time - start_time)
                start_pos = (kf_start['time'], kf_start['angle'])
                end_pos = (kf_end['time'], kf_end['angle'])
                start_cp = control_point_absolute(kf_start, 'out', servo_config)
                end_cp = control_point_absolute(kf_end, 'in', servo_config)
                
                if start_cp and end_cp:
                    _, angle = bezier_point(t, start_pos, start_cp, end_cp, end_pos)
                else:
                    #linear fallback
                    angle = kf_start['angle'] + t * (kf_end['angle'] - kf_start['angle'])
            
            #clamp to servo constraints and add to points
            clamped_angle = max(servo_config['pulse_min'], min(servo_config['pulse_max'], angle))
            points.append((current_time, int(round(clamped_angle))))
            current_time += time_step
    
    return points

def convert_recorded_keyframes_to_bezier(time_based_keyframes, component_name):
    #convert time-based recording format to bezier format for specific component
    if not time_based_keyframes:
        return []
    
    bezier_keyframes = []
    
    for keyframe in time_based_keyframes:
        if component_name in keyframe.get("component_positions", {}):
            time_ms = round(keyframe["absolute_time"] * 1000)
            pulse_width = keyframe["component_positions"][component_name]
            
            bezier_keyframe = {
                "time": time_ms,
                "angle": pulse_width,
                "cp_in": None,
                "cp_out": None
            }
            bezier_keyframes.append(bezier_keyframe)
    
    #ensure control points for smooth curves
    ensure_control_points(bezier_keyframes, use_smooth_defaults=True)
    
    return bezier_keyframes

def convert_bezier_to_time_based(bezier_sequences, include_all_times=True):
    #convert bezier format back to time-based recording format
    if not bezier_sequences:
        return []
    
    #collect all unique times
    all_times = set()
    for keyframes in bezier_sequences.values():
        for kf in keyframes:
            all_times.add(kf['time'])
    
    sorted_times = sorted(list(all_times))
    time_based_keyframes = []
    
    #create time-based keyframes
    for i, time_ms in enumerate(sorted_times):
        delay_to_next = (sorted_times[i+1] - time_ms) / 1000.0 if i < len(sorted_times) - 1 else 1.0
        
        keyframe = {
            "absolute_time": time_ms / 1000.0,
            "delay_to_next": delay_to_next,
            "component_positions": {}
        }
        
        #collect component positions at this time
        for component_name, keyframes in bezier_sequences.items():
            for kf in keyframes:
                if kf['time'] == time_ms:
                    keyframe["component_positions"][component_name] = kf['angle']
                    break
        
        time_based_keyframes.append(keyframe)
    
    return time_based_keyframes

def validate_bezier_keyframes(keyframes, servo_config):
    #validate bezier keyframe sequence for consistency and servo constraints
    if not isinstance(keyframes, list) or len(keyframes) < 2:
        return False, "sequence must contain at least 2 keyframes"
    
    previous_time = -1
    
    for i, kf in enumerate(keyframes):
        #validate basic structure
        if not isinstance(kf, dict) or 'time' not in kf or 'angle' not in kf:
            return False, f"keyframe {i} missing required fields"
        
        #validate time ordering
        if kf['time'] <= previous_time:
            return False, f"keyframe {i} time ordering invalid"
        
        #validate angle constraints
        if not (servo_config['pulse_min'] <= kf['angle'] <= servo_config['pulse_max']):
            return False, f"keyframe {i} angle outside servo constraints"
        
        previous_time = kf['time']
    
    return True, "sequence valid"

def create_smooth_bezier_from_points(time_points, angle_points):
    #create smooth bezier keyframes from discrete time/angle point pairs
    if len(time_points) != len(angle_points) or len(time_points) < 2:
        return []
    
    keyframes = []
    for i in range(len(time_points)):
        keyframe = {
            "time": int(time_points[i]),
            "angle": int(angle_points[i]),
            "cp_in": None,
            "cp_out": None
        }
        keyframes.append(keyframe)
    
    #generate smooth control points
    ensure_control_points(keyframes, use_smooth_defaults=True)
    
    return keyframes

def get_unique_timestamps(bezier_sequences):
    #extract all unique timestamps across all component sequences for timeline operations
    all_times = set()
    for component_sequence in bezier_sequences.values():
        for keyframe in component_sequence:
            all_times.add(keyframe['time'])
    return sorted(list(all_times))

def calculate_total_duration_ms(bezier_sequences):
    #calculate maximum timestamp across all component sequences for accurate duration
    if not bezier_sequences:
        return 0
    
    max_time = 0
    for component_sequence in bezier_sequences.values():
        if component_sequence:
            component_max = max(kf['time'] for kf in component_sequence)
            max_time = max(max_time, component_max)
    
    return max_time

def get_sequence_display_info(bezier_sequences, preserve_original_delays=True):
    #create display-compatible keyframe info without precision loss from bezier sequences
    if not bezier_sequences:
        return []
    
    unique_times = get_unique_timestamps(bezier_sequences)
    display_keyframes = []
    
    #build delay tracking for precision preservation
    original_delays = {}
    if preserve_original_delays:
        original_delays = _extract_original_delays(bezier_sequences)
    
    for i, time_ms in enumerate(unique_times):
        #calculate delay with precision preservation
        if i < len(unique_times) - 1:
            next_time_ms = unique_times[i + 1]
            
            if preserve_original_delays and time_ms in original_delays:
                delay_to_next = original_delays[time_ms]
            else:
                delay_to_next = (next_time_ms - time_ms) / 1000.0
        else:
            delay_to_next = 0.0 #for every recent recorded step, the time delay will dislay as zero unless another keyframe is added after it, which will then modify the 0.0 to the correct delay value
            #this is because there is no "next" keyframe to calculate a delay from
        
        #collect component positions at this timestamp
        component_positions = {}
        for component_name, component_sequence in bezier_sequences.items():
            for keyframe in component_sequence:
                if keyframe['time'] == time_ms:
                    component_positions[component_name] = keyframe['angle']
                    break
        
        display_keyframe = {
            "absolute_time": time_ms / 1000.0,
            "delay_to_next": delay_to_next,
            "component_positions": component_positions,
            "timestamp_ms": time_ms  #preserve exact timestamp for editing operations
        }
        
        display_keyframes.append(display_keyframe)
    
    return display_keyframes

def _extract_original_delays(bezier_sequences):
    #extract original recording delays from bezier sequence metadata if available
    delays = {}
    
    #for now return empty dict since original delays not yet stored in bezier format
    #this will be enhanced in future phases to preserve recording intentions
    return delays

def find_keyframes_at_timestamp(bezier_sequences, timestamp_ms):
    #find all component keyframes at specific timestamp for editing operations
    found_keyframes = {}
    
    for component_name, component_sequence in bezier_sequences.items():
        for i, keyframe in enumerate(component_sequence):
            if keyframe['time'] == timestamp_ms:
                found_keyframes[component_name] = {
                    'keyframe': keyframe,
                    'component_index': i,
                    'component_name': component_name
                }
                break
    
    return found_keyframes

def remove_keyframes_at_timestamp(bezier_sequences, timestamp_ms):
    #remove keyframes at specific timestamp across all components for unified editing
    removed_components = []
    
    for component_name, component_sequence in bezier_sequences.items():
        original_length = len(component_sequence)
        
        #remove keyframes matching timestamp
        component_sequence[:] = [kf for kf in component_sequence if kf['time'] != timestamp_ms]
        
        if len(component_sequence) != original_length:
            removed_components.append(component_name)
            
            #regenerate control points after removal
            ensure_control_points(component_sequence, use_smooth_defaults=True)
    
    return removed_components

def edit_keyframe_delay_at_timestamp(bezier_sequences, target_timestamp_ms, new_delay_ms):
    #edit delay between keyframes by shifting subsequent timestamps uniformly
    unique_times = get_unique_timestamps(bezier_sequences)
    
    try:
        current_index = unique_times.index(target_timestamp_ms)
    except ValueError:
        return False, "timestamp not found in sequence"
    
    if current_index >= len(unique_times) - 1:
        return False, "cannot edit delay of final keyframe"
    
    #calculate shift amount
    next_timestamp = unique_times[current_index + 1]
    current_delay_ms = next_timestamp - target_timestamp_ms
    shift_amount_ms = new_delay_ms - current_delay_ms
    
    #apply shift to all subsequent timestamps across all components
    for component_sequence in bezier_sequences.values():
        for keyframe in component_sequence:
            if keyframe['time'] > target_timestamp_ms:
                keyframe['time'] += shift_amount_ms
    
    #regenerate control points to maintain smooth curves after timing changes
    for component_sequence in bezier_sequences.values():
        ensure_control_points(component_sequence, use_smooth_defaults=True)
    
    return True, "delay updated successfully"

def create_command_timeline_from_bezier(bezier_sequences, servo_configurations, time_step=50):
    #generate unified command timeline from bezier sequences for async playback
    command_timeline = []
    
    for component_name, component_sequence in bezier_sequences.items():
        if component_name in servo_configurations:
            servo_config = servo_configurations[component_name]
            servo_index = servo_config['index']
            
            #generate interpolated points using existing function
            playback_points = generate_playback_points(component_sequence, servo_config, time_step)
            
            #convert to servo commands
            for time_ms, angle in playback_points:
                command_timeline.append((time_ms, f"SP:{servo_index}:{angle}"))
    
    #sort by timestamp for sequential execution
    command_timeline.sort(key=lambda x: x[0])
    return command_timeline

def get_keyframe_count_from_bezier(bezier_sequences):
    #count unique timestamps across all component sequences for display purposes
    return len(get_unique_timestamps(bezier_sequences))

def get_sequence_components_from_bezier(bezier_sequences):
    #get sorted list of components that have bezier sequences
    return sorted(list(bezier_sequences.keys()))

def validate_bezier_sequence_integrity(bezier_sequences, servo_configurations):
    #validate entire bezier sequence collection for consistency across components
    issues = []
    
    for component_name, component_sequence in bezier_sequences.items():
        if component_name not in servo_configurations:
            issues.append(f"component '{component_name}' no longer exists")
            continue
        
        servo_config = servo_configurations[component_name]
        is_valid, error_msg = validate_bezier_keyframes(component_sequence, servo_config)
        if not is_valid:
            issues.append(f"component '{component_name}': {error_msg}")
    
    return issues

def create_bezier_keyframe_at_timestamp(timestamp_ms, component_positions):
    #create bezier keyframes for multiple components at specific timestamp
    bezier_keyframes = {}
    
    for component_name, angle in component_positions.items():
        bezier_keyframes[component_name] = {
            "time": timestamp_ms,
            "angle": angle,
            "cp_in": None,
            "cp_out": None
        }
    
    return bezier_keyframes

def insert_keyframes_into_bezier_sequences(bezier_sequences, timestamp_ms, component_positions):
    #insert new keyframes at timestamp across multiple components with automatic sorting
    for component_name, angle in component_positions.items():
        if component_name not in bezier_sequences:
            bezier_sequences[component_name] = []
        
        #create new keyframe
        new_keyframe = {
            "time": timestamp_ms,
            "angle": angle,
            "cp_in": None,
            "cp_out": None
        }
        
        #insert at correct position to maintain time ordering
        component_sequence = bezier_sequences[component_name]
        insert_index = len(component_sequence)
        
        for i, existing_kf in enumerate(component_sequence):
            if existing_kf['time'] > timestamp_ms:
                insert_index = i
                break
        
        component_sequence.insert(insert_index, new_keyframe)
        
        #regenerate control points for smooth integration
        ensure_control_points(component_sequence, use_smooth_defaults=True)

def get_servo_commands_at_timestamp(bezier_sequences, servo_configurations, timestamp_ms):
    #resolve component positions at timestamp to servo commands for preview operations
    commands = []
    missing_components = []
    
    keyframes_at_time = find_keyframes_at_timestamp(bezier_sequences, timestamp_ms)
    
    for component_name, keyframe_info in keyframes_at_time.items():
        if component_name in servo_configurations:
            servo_config = servo_configurations[component_name]
            servo_index = servo_config['index']
            angle = keyframe_info['keyframe']['angle']
            commands.append(f"SP:{servo_index}:{angle}")
        else:
            missing_components.append(component_name)
    
    return commands, missing_components

#unified playback system functions extracted from working motion editor implementation

def create_unified_playback_executor(gui_widget, serial_connection, log_callback=None):
    #create reusable playback executor using reliable gui thread timing
    class UnifiedPlaybackExecutor:
        def __init__(self, gui_widget, serial_connection, log_callback):
            self.gui_widget = gui_widget  #tkinter widget for .after() scheduling
            self.serial_connection = serial_connection
            self.log_callback = log_callback
            self.playback_active = False
            self.completion_callback = None
        
        def execute_playback(self, bezier_sequences, servo_configurations, completion_callback=None):
            #execute unified playback using proven gui timing mechanism
            if self.playback_active:
                return False, "playback already active"
            
            if not bezier_sequences:
                return False, "no sequences to play"
            
            if not self.serial_connection.is_connected:
                return False, "serial connection required"
            
            #generate command timeline using existing function
            command_timeline = create_command_timeline_from_bezier(
                bezier_sequences, servo_configurations, time_step=50
            )
            
            if not command_timeline:
                return False, "no commands generated from sequences"
            
            #start unified playback execution
            self.completion_callback = completion_callback
            self.playback_active = True
            
            #calculate total duration for logging
            max_duration = max(cmd[0] for cmd in command_timeline) if command_timeline else 0
            
            if self.log_callback:
                component_count = len(bezier_sequences)
                self.log_callback(f"unified playback: {component_count} components, {max_duration}ms duration")
            
            #start command scheduling using proven timing mechanism
            playback_start_time = time.time()
            _schedule_unified_commands(
                self.gui_widget, command_timeline, self.serial_connection,
                playback_start_time, self._on_playback_complete
            )
            
            return True, "unified playback started"
        
        def stop_playback(self):
            #stop unified playback execution
            if self.playback_active:
                self.playback_active = False
                if self.completion_callback:
                    self.completion_callback(True, "playback stopped")
        
        def _on_playback_complete(self, success, error_msg=None):
            #handle playback completion with callback forwarding
            self.playback_active = False
            if self.completion_callback:
                self.completion_callback(success, error_msg)
    
    return UnifiedPlaybackExecutor(gui_widget, serial_connection, log_callback)

def execute_unified_playback(gui_widget, serial_connection, bezier_sequences, servo_configurations, completion_callback=None, log_callback=None):
    #simplified entry point for one-time playback execution
    executor = create_unified_playback_executor(gui_widget, serial_connection, log_callback)
    return executor.execute_playback(bezier_sequences, servo_configurations, completion_callback)

def _schedule_unified_commands(gui_widget, command_timeline, serial_connection, start_time, completion_callback):
    #reliable gui thread command scheduling extracted from motion editor implementation
    if not command_timeline:
        if completion_callback:
            completion_callback(True, "no commands to schedule")
        return
    
    current_time = time.time()
    elapsed_ms = (current_time - start_time) * 1000
    
    #find commands ready for execution with 50ms tolerance
    commands_to_execute = []
    remaining_commands = []
    
    for cmd_time, command in command_timeline:
        if cmd_time <= elapsed_ms + 50:
            commands_to_execute.append(command)
        else:
            remaining_commands.append((cmd_time, command))
    
    #execute ready commands
    for command in commands_to_execute:
        if serial_connection and serial_connection.is_connected:
            serial_connection.send_command(command)
    
    #schedule next batch using reliable gui timing
    if remaining_commands:
        gui_widget.after(20, lambda: _schedule_unified_commands(
            gui_widget, remaining_commands, serial_connection, start_time, completion_callback
        ))
    else:
        #playback complete
        if completion_callback:
            completion_callback(True, "playback completed successfully")
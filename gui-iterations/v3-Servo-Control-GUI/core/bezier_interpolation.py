import numpy as np
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
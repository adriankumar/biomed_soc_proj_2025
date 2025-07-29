import numpy as np
import copy

#default curve parameters for smooth motion
DEFAULT_TENSION_FACTOR = 0.33  #controls how curved vs linear the default interpolation is
DEFAULT_PWM_INFLUENCE = 0.0 #vertical deviation from keyframes in default curves
MIN_TIME_DIFFERENCE = 1  #minimum time between keyframes for curve generation

class BezierCurveComputer:
    #handles all bezier curve mathematical computations with explicit variable naming
    
    def __init__(self, tension_factor=DEFAULT_TENSION_FACTOR):
        self.tension_factor = tension_factor  #how pronounced the s-curve should be
        self.curve_cache = {}                 #stores computed curve segments for performance
        self.cache_resolution = 100           #number of points to pre-compute per curve segment
    
    #generate default control points for smooth s-curve between two keyframes
    def generate_default_control_points(self, keyframe_current, keyframe_next):
        time_current = keyframe_current['time']
        time_next = keyframe_next['time']
        pwm_current = keyframe_current['angle']  #keeping 'angle' for compatibility
        pwm_next = keyframe_next['angle']
        
        time_difference = time_next - time_current
        
        if time_difference < MIN_TIME_DIFFERENCE:
            #too close for meaningful curve generation
            return None, None
        
        #calculate control point time offsets using tension factor
        outgoing_time_offset = time_difference * self.tension_factor
        incoming_time_offset = time_difference * -self.tension_factor
        
        #control points have same pwm as keyframes for default smooth curve
        outgoing_control_point = {
            'dt': outgoing_time_offset,
            'da': DEFAULT_PWM_INFLUENCE
        }
        
        incoming_control_point = {
            'dt': incoming_time_offset, 
            'da': DEFAULT_PWM_INFLUENCE
        }
        
        return outgoing_control_point, incoming_control_point
    
    #ensure all keyframes in a sequence have valid control points
    def ensure_control_points_for_sequence(self, keyframe_sequence):
        sequence_copy = copy.deepcopy(keyframe_sequence)
        total_keyframes = len(sequence_copy)
        
        for current_index in range(total_keyframes):
            current_keyframe = sequence_copy[current_index]
            
            #first keyframe only needs outgoing control point
            if current_index == 0:
                current_keyframe['cp_in'] = None
                if current_index < total_keyframes - 1:
                    next_keyframe = sequence_copy[current_index + 1]
                    outgoing_cp, _ = self.generate_default_control_points(current_keyframe, next_keyframe)
                    current_keyframe['cp_out'] = outgoing_cp
                else:
                    current_keyframe['cp_out'] = None
            
            #last keyframe only needs incoming control point  
            elif current_index == total_keyframes - 1:
                current_keyframe['cp_out'] = None
                if current_index > 0:
                    previous_keyframe = sequence_copy[current_index - 1]
                    _, incoming_cp = self.generate_default_control_points(previous_keyframe, current_keyframe)
                    current_keyframe['cp_in'] = incoming_cp
                else:
                    current_keyframe['cp_in'] = None
            
            #intermediate keyframes need both control points
            else:
                previous_keyframe = sequence_copy[current_index - 1]
                next_keyframe = sequence_copy[current_index + 1]
                
                #incoming control point from previous keyframe
                _, incoming_cp = self.generate_default_control_points(previous_keyframe, current_keyframe)
                current_keyframe['cp_in'] = incoming_cp
                
                #outgoing control point to next keyframe
                outgoing_cp, _ = self.generate_default_control_points(current_keyframe, next_keyframe)
                current_keyframe['cp_out'] = outgoing_cp
        
        return sequence_copy
    
    #convert relative control point to absolute coordinates for plotting
    def control_point_to_absolute_coordinates(self, keyframe, control_point_type):
        if control_point_type not in ['cp_in', 'cp_out']:
            return None
        
        control_point_data = keyframe.get(control_point_type)
        if not control_point_data:
            return None
        
        keyframe_time = keyframe['time']
        keyframe_pwm = keyframe['angle']
        
        absolute_time = keyframe_time + control_point_data['dt']
        absolute_pwm = keyframe_pwm + control_point_data['da']
        
        #clamp pwm to valid servo range
        absolute_pwm = max(0, min(180, absolute_pwm))
        
        return absolute_time, absolute_pwm
    
    #compute a single point on cubic bezier curve using bernstein polynomials
    def compute_bezier_point_at_parameter(self, parameter_t, start_point, start_control, end_control, end_point):
        #bernstein basis polynomials for cubic bezier
        basis_0 = (1 - parameter_t) ** 3
        basis_1 = 3 * (1 - parameter_t) ** 2 * parameter_t
        basis_2 = 3 * (1 - parameter_t) * parameter_t ** 2
        basis_3 = parameter_t ** 3
        
        #compute time coordinate
        interpolated_time = (basis_0 * start_point[0] + 
                           basis_1 * start_control[0] + 
                           basis_2 * end_control[0] + 
                           basis_3 * end_point[0])
        
        #compute pwm coordinate  
        interpolated_pwm = (basis_0 * start_point[1] + 
                          basis_1 * start_control[1] + 
                          basis_2 * end_control[1] + 
                          basis_3 * end_point[1])
        
        return interpolated_time, interpolated_pwm
    
    #generate smooth curve segment between two keyframes
    def compute_curve_segment(self, keyframe_start, keyframe_end, resolution=None):
        if resolution is None:
            resolution = self.cache_resolution
        
        #extract keyframe positions
        start_point = (keyframe_start['time'], keyframe_start['angle'])
        end_point = (keyframe_end['time'], keyframe_end['angle'])
        
        #get control points in absolute coordinates
        start_control_abs = self.control_point_to_absolute_coordinates(keyframe_start, 'cp_out')
        end_control_abs = self.control_point_to_absolute_coordinates(keyframe_end, 'cp_in')
        
        if not start_control_abs or not end_control_abs:
            #fallback to linear interpolation if control points missing
            return self._linear_interpolation(start_point, end_point, resolution)
        
        #generate curve points using bezier mathematics
        parameter_values = np.linspace(0, 1, resolution)
        curve_points = []
        
        for parameter_t in parameter_values:
            interpolated_point = self.compute_bezier_point_at_parameter(
                parameter_t, start_point, start_control_abs, end_control_abs, end_point
            )
            curve_points.append(interpolated_point)
        
        #separate time and pwm arrays for plotting
        time_values = [point[0] for point in curve_points]
        pwm_values = [point[1] for point in curve_points]
        
        return np.array(time_values), np.array(pwm_values)
    
    #fallback linear interpolation when bezier fails
    def _linear_interpolation(self, start_point, end_point, resolution):
        time_values = np.linspace(start_point[0], end_point[0], resolution)
        pwm_values = np.linspace(start_point[1], end_point[1], resolution)
        return time_values, pwm_values
    
    #generate interpolated pwm value at specific time using cached curves
    def interpolate_pwm_at_time(self, keyframe_sequence, component_name, target_time):
        #find which curve segment contains the target time
        for segment_index in range(len(keyframe_sequence) - 1):
            keyframe_current = keyframe_sequence[segment_index]
            keyframe_next = keyframe_sequence[segment_index + 1]
            
            if keyframe_current['time'] <= target_time <= keyframe_next['time']:
                #generate or retrieve cached curve segment
                cache_key = f"{component_name}_{segment_index}"
                
                if cache_key not in self.curve_cache:
                    time_array, pwm_array = self.compute_curve_segment(keyframe_current, keyframe_next)
                    self.curve_cache[cache_key] = (time_array, pwm_array)
                
                time_array, pwm_array = self.curve_cache[cache_key]
                
                #find closest time sample and return corresponding pwm
                closest_index = np.argmin(np.abs(time_array - target_time))
                return int(round(pwm_array[closest_index]))
        
        #if time is outside sequence range, return nearest keyframe value
        if target_time <= keyframe_sequence[0]['time']:
            return keyframe_sequence[0]['angle']
        else:
            return keyframe_sequence[-1]['angle']
    
    #clear interpolation cache when keyframes change
    def invalidate_cache(self, component_name=None):
        if component_name:
            #clear cache for specific component
            keys_to_remove = [key for key in self.curve_cache.keys() if key.startswith(component_name)]
            for key in keys_to_remove:
                del self.curve_cache[key]
        else:
            #clear entire cache
            self.curve_cache.clear()
    
    #update tension factor and clear cache to apply changes
    def set_tension_factor(self, new_tension):
        if 0.0 <= new_tension <= 1.0:
            self.tension_factor = new_tension
            self.invalidate_cache()  #force recalculation with new tension
            return True
        return False
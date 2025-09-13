#centralised validation for servo control system

#hardware constraints
PCA9685_MAX_COUNT = 4095
MAX_SERVOS = 25
MIN_PULSE_WIDTH = 0
MAX_PULSE_WIDTH = PCA9685_MAX_COUNT
SERVO_INDEX_MIN = 0
SERVO_INDEX_MAX = 31 #for daisy chained pca boards
DEFAULT_PULSE_MIN = 150
DEFAULT_PULSE_MAX = 600
DEFAULT_PULSE_CENTER = 375

#sequence constraints
MAX_SEQUENCE_DURATION = 120.0
MIN_KEYFRAME_INTERVAL = 0.01
MAX_KEYFRAME_DELAY = 30.0
DEFAULT_KEYFRAME_DELAY = 1.0

#motion curve constraints (for motion editor integration)
MIN_TENSION_FACTOR = 0.0
MAX_TENSION_FACTOR = 1.0
DEFAULT_TENSION_FACTOR = 0.33
MAX_CONTROL_POINT_TIME_OFFSET = 10000  #maximum milliseconds offset for control points
MIN_CONTROL_POINT_TIME_OFFSET = 1      #minimum milliseconds offset for control points

#gui performance
SLIDER_THROTTLE_MS = 50 #controls how fast the slider sends pulse width values; only used for the slider
PLAYBACK_COMMAND_INTERVAL = 0.005
PLAYBACK_TIMING_PRECISION = 0.01

#smoothing preferences
SMALL_DELTA_PWM = 50
SMOOTH_SHORT_S = 0.5
SMOOTH_LONG_S = 1.0
LEAD_IN_DURATION_MS = 1000

#command terminal
COMMAND_HISTORY_LIMIT = 10

class ValidationResult:
    #simple validation result container
    def __init__(self, is_valid, value=None, error_message=""):
        self.is_valid = is_valid
        self.value = value
        self.error_message = error_message

#validate pulse width values
def validate_pulse_width(pulse_width_str):
    try:
        pulse_width_str = pulse_width_str.strip()
        if not pulse_width_str:
            return ValidationResult(False, 0, "pulse width cannot be empty")
        
        pulse_width = int(pulse_width_str)
        if not MIN_PULSE_WIDTH <= pulse_width <= MAX_PULSE_WIDTH:
            return ValidationResult(False, 0, f"pulse width must be between {MIN_PULSE_WIDTH} and {MAX_PULSE_WIDTH}")
        
        return ValidationResult(True, pulse_width, "")
    except ValueError:
        return ValidationResult(False, 0, "pulse width must be a valid number")

#validate servo index values
def validate_servo_index(index_str):
    try:
        index_str = index_str.strip()
        if not index_str:
            return ValidationResult(False, 0, "index cannot be empty")
        
        index = int(index_str)
        if not SERVO_INDEX_MIN <= index <= SERVO_INDEX_MAX:
            return ValidationResult(False, 0, f"index must be between {SERVO_INDEX_MIN} and {SERVO_INDEX_MAX}")
        
        return ValidationResult(True, index, "")
    except ValueError:
        return ValidationResult(False, 0, "index must be a valid number")

#validate pulse range configuration
def validate_pulse_range(pulse_min, pulse_max):
    if pulse_min >= pulse_max:
        return ValidationResult(False, None, "minimum must be less than maximum")
    
    if not (MIN_PULSE_WIDTH <= pulse_min <= MAX_PULSE_WIDTH):
        return ValidationResult(False, None, f"minimum must be between {MIN_PULSE_WIDTH} and {MAX_PULSE_WIDTH}")
    
    if not (MIN_PULSE_WIDTH <= pulse_max <= MAX_PULSE_WIDTH):
        return ValidationResult(False, None, f"maximum must be between {MIN_PULSE_WIDTH} and {MAX_PULSE_WIDTH}")
    
    return ValidationResult(True, (pulse_min, pulse_max), "")

#validate pulse width against component constraints
def validate_pulse_within_range(pulse_width, pulse_min, pulse_max, component_name=""):
    if not (pulse_min <= pulse_width <= pulse_max):
        prefix = f"{component_name} " if component_name else ""
        return ValidationResult(False, pulse_width, f"{prefix}pulse width {pulse_width} outside range [{pulse_min}, {pulse_max}]")
    
    return ValidationResult(True, pulse_width, "")

#validate timing constraints for sequences
def validate_timing(absolute_time, delay_to_next):
    if absolute_time < 0 or absolute_time > MAX_SEQUENCE_DURATION:
        return ValidationResult(False, None, f"time must be between 0 and {MAX_SEQUENCE_DURATION} seconds")
    
    if delay_to_next < MIN_KEYFRAME_INTERVAL or delay_to_next > MAX_KEYFRAME_DELAY:
        return ValidationResult(False, None, f"delay must be between {MIN_KEYFRAME_INTERVAL} and {MAX_KEYFRAME_DELAY} seconds")
    
    total_time = absolute_time + delay_to_next
    if total_time > MAX_SEQUENCE_DURATION:
        return ValidationResult(False, None, f"total time exceeds maximum duration of {MAX_SEQUENCE_DURATION} seconds")
    
    return ValidationResult(True, (absolute_time, delay_to_next), "")

#validate component positions dictionary
def validate_component_positions(component_positions, servo_configurations):
    if not isinstance(component_positions, dict):
        return ValidationResult(False, None, "component positions must be a dictionary")
    
    if not component_positions:
        return ValidationResult(False, None, "no component positions provided")
    
    for component_name, pulse_width in component_positions.items():
        if component_name not in servo_configurations:
            return ValidationResult(False, None, f"component '{component_name}' not found in servo configuration")
        
        config = servo_configurations[component_name]
        range_result = validate_pulse_within_range(pulse_width, config["pulse_min"], config["pulse_max"], component_name)
        if not range_result.is_valid:
            return range_result
    
    return ValidationResult(True, component_positions, "")

#validate component name format
def validate_component_name(component_name):
    if not component_name or not isinstance(component_name, str):
        return ValidationResult(False, "", "component name must be a non-empty string")
    
    component_name = component_name.strip()
    if not component_name:
        return ValidationResult(False, "", "component name cannot be empty")
    
    #basic naming constraints
    if len(component_name) > 50:
        return ValidationResult(False, component_name, "component name too long (max 50 characters)")
    
    return ValidationResult(True, component_name, "")

#validate motion curve tension factor (for motion editor)
def validate_tension_factor(tension_value):
    try:
        if isinstance(tension_value, str):
            tension_value = float(tension_value.strip())
        
        if not (MIN_TENSION_FACTOR <= tension_value <= MAX_TENSION_FACTOR):
            return ValidationResult(False, DEFAULT_TENSION_FACTOR, 
                f"tension factor must be between {MIN_TENSION_FACTOR} and {MAX_TENSION_FACTOR}")
        
        return ValidationResult(True, tension_value, "")
    except (ValueError, TypeError):
        return ValidationResult(False, DEFAULT_TENSION_FACTOR, "tension factor must be a valid number")

#validate control point time offset (for motion editor)
def validate_control_point_offset(time_offset, control_type="out"):
    try:
        if isinstance(time_offset, str):
            time_offset = float(time_offset.strip())
        
        if abs(time_offset) > MAX_CONTROL_POINT_TIME_OFFSET:
            return ValidationResult(False, 0, f"control point offset too large (max {MAX_CONTROL_POINT_TIME_OFFSET}ms)")
        
        if abs(time_offset) < MIN_CONTROL_POINT_TIME_OFFSET:
            return ValidationResult(False, 0, f"control point offset too small (min {MIN_CONTROL_POINT_TIME_OFFSET}ms)")
        
        #validate direction constraints
        if control_type == "out" and time_offset < 0:
            return ValidationResult(False, abs(time_offset), "outgoing control points must have positive time offset")
        elif control_type == "in" and time_offset > 0:
            return ValidationResult(False, -abs(time_offset), "incoming control points must have negative time offset")
        
        return ValidationResult(True, time_offset, "")
    except (ValueError, TypeError):
        return ValidationResult(False, 0, "control point offset must be a valid number")

#validate bezier curve keyframe structure (for motion editor integration)
def validate_bezier_keyframe(keyframe_data):
    if not isinstance(keyframe_data, dict):
        return ValidationResult(False, None, "keyframe must be a dictionary")
    
    required_fields = ["time", "angle"]
    for field in required_fields:
        if field not in keyframe_data:
            return ValidationResult(False, None, f"keyframe missing required field: {field}")
    
    #validate time value
    try:
        time_value = float(keyframe_data["time"])
        if time_value < 0 or time_value > MAX_SEQUENCE_DURATION * 1000:  #convert to milliseconds
            return ValidationResult(False, None, f"keyframe time {time_value} outside valid range")
    except (ValueError, TypeError):
        return ValidationResult(False, None, "keyframe time must be a valid number")
    
    #validate angle/pwm value
    try:
        angle_value = float(keyframe_data["angle"])
        if not (MIN_PULSE_WIDTH <= angle_value <= MAX_PULSE_WIDTH):
            return ValidationResult(False, None, f"keyframe angle {angle_value} outside pulse width range")
    except (ValueError, TypeError):
        return ValidationResult(False, None, "keyframe angle must be a valid number")
    
    #validate control points if present
    for cp_type in ["cp_in", "cp_out"]:
        if cp_type in keyframe_data and keyframe_data[cp_type] is not None:
            cp_data = keyframe_data[cp_type]
            if not isinstance(cp_data, dict) or "dt" not in cp_data or "da" not in cp_data:
                return ValidationResult(False, None, f"invalid {cp_type} control point structure")
            
            #validate time offset
            offset_result = validate_control_point_offset(cp_data["dt"], cp_type.split("_")[1])
            if not offset_result.is_valid:
                return ValidationResult(False, None, f"{cp_type} {offset_result.error_message}")
    
    return ValidationResult(True, keyframe_data, "")

#validate entire bezier sequence structure (for motion editor integration)
def validate_bezier_sequence(sequence_data):
    if not isinstance(sequence_data, list):
        return ValidationResult(False, None, "sequence must be a list of keyframes")
    
    if len(sequence_data) < 2:
        return ValidationResult(False, None, "sequence must contain at least 2 keyframes")
    
    validation_errors = []
    previous_time = -1
    
    for i, keyframe in enumerate(sequence_data):
        #validate individual keyframe
        keyframe_result = validate_bezier_keyframe(keyframe)
        if not keyframe_result.is_valid:
            validation_errors.append(f"keyframe {i}: {keyframe_result.error_message}")
            continue
        
        #validate time ordering
        current_time = keyframe["time"]
        if current_time <= previous_time:
            validation_errors.append(f"keyframe {i}: time {current_time} not after previous time {previous_time}")
        
        previous_time = current_time
    
    if validation_errors:
        return ValidationResult(False, None, "; ".join(validation_errors))
    
    return ValidationResult(True, sequence_data, "")

#validate interpolation data structure (for sequence files with curve data)
def validate_interpolation_data(interpolation_data, component_name=""):
    if not isinstance(interpolation_data, dict):
        return ValidationResult(False, None, "interpolation data must be a dictionary")
    
    component_prefix = f"{component_name}: " if component_name else ""
    
    #validate interpolation type
    if "type" not in interpolation_data:
        return ValidationResult(False, None, f"{component_prefix}interpolation type not specified")
    
    if interpolation_data["type"] not in ["linear", "bezier"]:
        return ValidationResult(False, None, f"{component_prefix}invalid interpolation type: {interpolation_data['type']}")
    
    #validate bezier-specific data
    if interpolation_data["type"] == "bezier":
        for cp_type in ["cp_in", "cp_out"]:
            if cp_type in interpolation_data:
                cp_data = interpolation_data[cp_type]
                if cp_data is not None:
                    if not isinstance(cp_data, dict) or "dt" not in cp_data or "da" not in cp_data:
                        return ValidationResult(False, None, f"{component_prefix}invalid {cp_type} structure")
                    
                    #validate control point offset
                    offset_result = validate_control_point_offset(cp_data["dt"], cp_type.split("_")[1])
                    if not offset_result.is_valid:
                        return ValidationResult(False, None, f"{component_prefix}{cp_type} {offset_result.error_message}")
    
    return ValidationResult(True, interpolation_data, "")

#realtime smoothing activation check
def is_smoothing_active(state_manager, serial_connection):
    try:
        return bool(serial_connection and serial_connection.is_connected and state_manager.realtime_smoothing_enabled)
    except Exception:
        return False

#filter transition targets by removing components that do not need movement
def filter_transition_targets(state_manager, targets, tolerance_pwm=0):
    if not isinstance(targets, dict):
        return {}
    filtered = {}
    for name, target in targets.items():
        try:
            last_sent = state_manager.get_last_sent(name)
            if abs(int(target) - int(last_sent)) <= int(tolerance_pwm):
                continue
            cfg = state_manager.get_component_config(name)
            if not cfg:
                continue
            clamped = max(cfg["pulse_min"], min(cfg["pulse_max"], int(target)))
            filtered[name] = clamped
        except Exception:
            continue
    return filtered

#plan lead-in based on realtime smoothing and actual movement needs
def plan_lead_in(state_manager, serial_connection, targets, duration_ms=LEAD_IN_DURATION_MS, tolerance_pwm=0):
    if not is_smoothing_active(state_manager, serial_connection):
        return False, {}, 0
    filtered = filter_transition_targets(state_manager, targets, tolerance_pwm=tolerance_pwm)
    if not filtered:
        return False, {}, 0
    return True, filtered, int(duration_ms)

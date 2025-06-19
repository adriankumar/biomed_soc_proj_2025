#centralised validation for servo control system

#hardware constraints
PCA9685_MAX_COUNT = 4095
MAX_SERVOS = 25
MIN_PULSE_WIDTH = 0
MAX_PULSE_WIDTH = PCA9685_MAX_COUNT
SERVO_INDEX_MIN = 0
SERVO_INDEX_MAX = 24
DEFAULT_PULSE_MIN = 150
DEFAULT_PULSE_MAX = 600
DEFAULT_PULSE_CENTER = 375

#sequence constraints
MAX_SEQUENCE_DURATION = 120.0
MIN_KEYFRAME_INTERVAL = 0.01
MAX_KEYFRAME_DELAY = 30.0
DEFAULT_KEYFRAME_DELAY = 1.0

#gui performance
SLIDER_THROTTLE_MS = 50 #controls how fast the slider sends pulse width values; only used for the slider
PLAYBACK_COMMAND_INTERVAL = 0.005
PLAYBACK_TIMING_PRECISION = 0.01

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
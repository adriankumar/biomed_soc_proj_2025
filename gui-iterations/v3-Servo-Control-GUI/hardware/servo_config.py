#hardware configuration for servo control system

from core.validation import DEFAULT_PULSE_MIN, DEFAULT_PULSE_MAX, DEFAULT_PULSE_CENTER

#hardware constants
MAX_SERVOS = 25
BAUD_RATE = 115200
PWM_FREQUENCY = 50  #fixed frequency for all servos
SERIAL_TIMEOUT = 1.0

#default component configurations
DEFAULT_COMPONENT_CONFIGS = {
    "head_1": {"index": 0, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "head_2": {"index": 1, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "head_3": {"index": 2, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "head_4": {"index": 3, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "head_5": {"index": 4, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_hand_1": {"index": 5, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_hand_2": {"index": 6, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_hand_3": {"index": 7, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_hand_4": {"index": 8, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_hand_5": {"index": 9, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_hand_1": {"index": 10, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_hand_2": {"index": 11, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_hand_3": {"index": 12, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_hand_4": {"index": 13, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_hand_5": {"index": 14, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_elbow_1": {"index": 15, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_elbow_2": {"index": 16, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_elbow_1": {"index": 17, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_elbow_2": {"index": 18, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_shoulder_1": {"index": 19, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_shoulder_2": {"index": 20, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "left_shoulder_3": {"index": 21, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_shoulder_1": {"index": 22, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_shoulder_2": {"index": 23, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER},
    "right_shoulder_3": {"index": 24, "pulse_min": DEFAULT_PULSE_MIN, "pulse_max": DEFAULT_PULSE_MAX, "default_position": DEFAULT_PULSE_CENTER, "current_position": DEFAULT_PULSE_CENTER}
}

#component groups for organised display
COMPONENT_GROUPS = {
    "head": ["head_1", "head_2", "head_3", "head_4", "head_5"],
    "left_hand": ["left_hand_1", "left_hand_2", "left_hand_3", "left_hand_4", "left_hand_5"],
    "right_hand": ["right_hand_1", "right_hand_2", "right_hand_3", "right_hand_4", "right_hand_5"],
    "left_elbow": ["left_elbow_1", "left_elbow_2"],
    "right_elbow": ["right_elbow_1", "right_elbow_2"],
    "left_shoulder": ["left_shoulder_1", "left_shoulder_2", "left_shoulder_3"],
    "right_shoulder": ["right_shoulder_1", "right_shoulder_2", "right_shoulder_3"]
}
#configuration constants for motion curve behavior and appearance
#modify these values to change default curve characteristics across the system

#default bezier curve parameters
DEFAULT_TENSION_FACTOR = 0.33      #how pronounced the s-curve is (0.1=tight, 0.5=dramatic)
DEFAULT_PWM_INFLUENCE = 0.0        #vertical deviation from keyframes (0=horizontal handles)
DEFAULT_SYMMETRY_BIAS = 0.0        #curve asymmetry (-1=favor start, 1=favor end)

#curve computation settings  
CURVE_RESOLUTION = 100             #number of points computed per curve segment
CACHE_RESOLUTION = 10              #millisecond intervals for playback cache
MIN_TIME_DIFFERENCE = 1            #minimum time between keyframes for curve generation
MAX_CONTROL_POINT_DISTANCE = 5000  #maximum time offset for control points (ms)

#component-specific curve overrides
#allows different curve behavior for different types of components
COMPONENT_CURVE_OVERRIDES = {
    "eye_horizontal": {
        "tension_factor": 0.4,         #eyes need extra smooth motion
        "pwm_influence": 0.0
    },
    "eye_vertical": {
        "tension_factor": 0.4,         #eyes need extra smooth motion  
        "pwm_influence": 0.0
    },
    "left_hand_1": {
        "tension_factor": 0.25,        #hands can be slightly snappier
        "pwm_influence": 0.0
    },
    "right_hand_1": {
        "tension_factor": 0.25,        #hands can be slightly snappier
        "pwm_influence": 0.0
    }
}

#curve preset definitions for different motion styles
CURVE_PRESETS = {
    "linear": {
        "tension_factor": 0.0,
        "pwm_influence": 0.0,
        "description": "straight line interpolation"
    },
    "ease": {
        "tension_factor": 0.33,
        "pwm_influence": 0.0, 
        "description": "smooth s-curve (default)"
    },
    "ease_dramatic": {
        "tension_factor": 0.5,
        "pwm_influence": 0.0,
        "description": "pronounced s-curve with strong acceleration/deceleration"
    },
    "ease_tight": {
        "tension_factor": 0.2,
        "pwm_influence": 0.0,
        "description": "subtle s-curve, closer to linear"
    },
    "bounce": {
        "tension_factor": 0.4,
        "pwm_influence": 8.0,
        "description": "overshoot effect with bounce"
    },
    "anticipation": {
        "tension_factor": 0.35,
        "pwm_influence": -5.0,
        "description": "slight dip before movement (anticipation)"
    }
}

#motion editor ui configuration
MOTION_EDITOR_CONFIG = {
    "default_window_size": (1200, 800),
    "plot_background_color": "white",
    "keyframe_color": "red",
    "keyframe_size": 100,
    "curve_color": "blue", 
    "curve_linewidth": 2,
    "control_point_color": "green",
    "control_point_size": 60,
    "control_handle_color": "green",
    "control_handle_alpha": 0.7,
    "playback_indicator_color": "orange",
    "grid_alpha": 0.3
}

#performance and caching settings
PERFORMANCE_CONFIG = {
    "max_cache_size_mb": 50,           #maximum memory for curve interpolation cache
    "cache_cleanup_interval": 300,     #seconds between cache cleanup cycles
    "enable_curve_caching": True,      #whether to cache computed curve segments
    "enable_playback_caching": True,   #whether to pre-compute playback values
    "max_sequence_duration": 120000,   #maximum sequence length in milliseconds
    "playback_update_interval": 50     #milliseconds between playback animation updates
}

#validation and safety limits
VALIDATION_CONFIG = {
    "max_keyframes_per_component": 100,    #prevent excessive keyframe counts
    "min_keyframe_spacing": 10,            #minimum milliseconds between keyframes
    "max_pwm_value": 4095,                 #hardware pwm limit
    "min_pwm_value": 0,                    #hardware pwm minimum
    "auto_clamp_values": True,             #automatically clamp pwm to component ranges
    "validate_curve_continuity": True      #check that curves connect properly
}

#hardware communication settings for motion editor
HARDWARE_CONFIG = {
    "preview_command_delay": 0.01,         #seconds between real-time preview commands
    "playback_command_delay": 0.005,       #seconds between sequence playback commands  
    "enable_real_time_preview": True,      #send commands during curve editing
    "enable_keyframe_preview": True,       #send commands when selecting keyframes
    "preview_debounce_time": 0.05          #minimum time between preview updates
}

class CurveConfigurationManager:
    #manages runtime configuration for curve behavior
    
    def __init__(self):
        self.active_preset = "ease"                    #currently active curve preset
        self.custom_overrides = {}                     #runtime configuration overrides
        self.component_specific_settings = {}          #per-component curve settings
    
    #get curve parameters for a specific component
    def get_curve_parameters(self, component_name=None):
        #start with global defaults
        params = {
            "tension_factor": DEFAULT_TENSION_FACTOR,
            "pwm_influence": DEFAULT_PWM_INFLUENCE,
            "symmetry_bias": DEFAULT_SYMMETRY_BIAS
        }
        
        #apply active preset
        if self.active_preset in CURVE_PRESETS:
            preset_params = CURVE_PRESETS[self.active_preset]
            params.update({k: v for k, v in preset_params.items() if k != "description"})
        
        #apply component-specific overrides
        if component_name and component_name in COMPONENT_CURVE_OVERRIDES:
            component_overrides = COMPONENT_CURVE_OVERRIDES[component_name]
            params.update(component_overrides)
        
        #apply any custom overrides
        if component_name and component_name in self.component_specific_settings:
            custom_overrides = self.component_specific_settings[component_name]
            params.update(custom_overrides)
        
        #apply global custom overrides
        params.update(self.custom_overrides)
        
        return params
    
    #set curve preset for all components
    def set_curve_preset(self, preset_name):
        if preset_name in CURVE_PRESETS:
            self.active_preset = preset_name
            return True
        return False
    
    #set custom curve parameters for specific component
    def set_component_curve_parameters(self, component_name, **kwargs):
        if component_name not in self.component_specific_settings:
            self.component_specific_settings[component_name] = {}
        
        valid_params = ["tension_factor", "pwm_influence", "symmetry_bias"]
        for param, value in kwargs.items():
            if param in valid_params:
                self.component_specific_settings[component_name][param] = value
    
    #set global curve parameter overrides
    def set_global_override(self, parameter, value):
        valid_params = ["tension_factor", "pwm_influence", "symmetry_bias"]
        if parameter in valid_params:
            self.custom_overrides[parameter] = value
            return True
        return False
    
    #get list of available curve presets
    def get_available_presets(self):
        return list(CURVE_PRESETS.keys())
    
    #get description of curve preset
    def get_preset_description(self, preset_name):
        if preset_name in CURVE_PRESETS:
            return CURVE_PRESETS[preset_name].get("description", "no description")
        return "unknown preset"
    
    #reset all custom settings to defaults
    def reset_to_defaults(self):
        self.active_preset = "ease"
        self.custom_overrides.clear()
        self.component_specific_settings.clear()
    
    #export current configuration for saving
    def export_configuration(self):
        return {
            "active_preset": self.active_preset,
            "custom_overrides": self.custom_overrides.copy(),
            "component_specific_settings": self.component_specific_settings.copy()
        }
    
    #import configuration from saved data
    def import_configuration(self, config_data):
        if "active_preset" in config_data:
            self.set_curve_preset(config_data["active_preset"])
        
        if "custom_overrides" in config_data:
            self.custom_overrides.update(config_data["custom_overrides"])
        
        if "component_specific_settings" in config_data:
            self.component_specific_settings.update(config_data["component_specific_settings"])

#global configuration manager instance
curve_config_manager = CurveConfigurationManager()

#convenience functions for getting configuration values
def get_tension_factor(component_name=None):
    return curve_config_manager.get_curve_parameters(component_name)["tension_factor"]

def get_pwm_influence(component_name=None):
    return curve_config_manager.get_curve_parameters(component_name)["pwm_influence"]

def get_symmetry_bias(component_name=None):
    return curve_config_manager.get_curve_parameters(component_name)["symmetry_bias"]

def set_curve_preset(preset_name):
    return curve_config_manager.set_curve_preset(preset_name)

def get_available_presets():
    return curve_config_manager.get_available_presets()
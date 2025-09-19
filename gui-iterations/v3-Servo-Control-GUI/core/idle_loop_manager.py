import os
import json
import random
import time
from core.bezier_interpolation import _clamp_to_config
 
 
class IdleLoopManager:
    #manages idle emote playback with random selection and timing
    def __init__(self, sequence_manager, playback_manager, state_manager, gui_widget, log_callback):
        self.sequence_manager = sequence_manager
        self.playback_manager = playback_manager
        self.state_manager = state_manager
        self.gui_widget = gui_widget
        self.log_callback = log_callback
       
        #idle state management
        self.is_active = False
        self.current_timer_id = None
        self.last_played_emote = None
        self.original_sequence_backup = None
       
        #emote data storage
        self.preloaded_emotes = {}  #{filename: sequence_data}
        self.emote_directory = os.path.join("gui-iterations", "v3-Servo-Control-GUI", "data", "emotes")
       
        #timing configuration
        self.min_idle_time = 5  #seconds
        self.max_idle_time = 5 #seconds
       
        #pre-load all emotes at initialization
        self._load_emotes_from_directory()
   
    #scan and pre-load all emote sequences from hardcoded directory
    def _load_emotes_from_directory(self):
        if not os.path.exists(self.emote_directory):
            if self.log_callback:
                self.log_callback(f"emote directory not found: {self.emote_directory}")
            return
       
        try:
            json_files = [f for f in os.listdir(self.emote_directory) if f.endswith('.json')]
           
            for filename in json_files:
                file_path = os.path.join(self.emote_directory, filename)
                try:
                    with open(file_path, 'r') as file:
                        emote_data = json.load(file)
                   
                    #validate basic structure before storing
                    if self._validate_emote_data(emote_data):
                        #clamp all keyframe angles to current component constraints
                        clamped_emote_data = self._clamp_emote_to_constraints(emote_data)
                        emote_name = os.path.splitext(filename)[0]
                        self.preloaded_emotes[emote_name] = clamped_emote_data
                    else:
                        if self.log_callback:
                            self.log_callback(f"invalid emote format: {filename}")
               
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"failed to load emote {filename}: {str(e)}")
           
            if self.log_callback:
                self.log_callback(f"pre-loaded {len(self.preloaded_emotes)} emotes for idle system")
       
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"error scanning emote directory: {str(e)}")
   
    #clamp emote keyframe angles to current component constraints
    def _clamp_emote_to_constraints(self, emote_data):
        clamped_data = json.loads(json.dumps(emote_data))  #deep copy
       
        #clamp servo_sequences format (unified bezier)
        if "servo_sequences" in clamped_data:
            for component_name, keyframes in clamped_data["servo_sequences"].items():
                for keyframe in keyframes:
                    if "angle" in keyframe:
                        keyframe["angle"] = _clamp_to_config(
                            component_name, keyframe["angle"], self.state_manager.servo_configurations
                        )
       
        #clamp legacy keyframes format
        elif "keyframes" in clamped_data:
            for keyframe in clamped_data["keyframes"]:
                if "component_positions" in keyframe:
                    for component_name, angle in keyframe["component_positions"].items():
                        keyframe["component_positions"][component_name] = _clamp_to_config(
                            component_name, angle, self.state_manager.servo_configurations
                        )
       
        return clamped_data
   
    #validate emote data has required structure
    def _validate_emote_data(self, emote_data):
        if not isinstance(emote_data, dict):
            return False
       
        #check for unified bezier format or legacy format
        has_servo_sequences = "servo_sequences" in emote_data
        has_keyframes = "keyframes" in emote_data
       
        return has_servo_sequences or has_keyframes
   
    #toggle idle loop on/off
    def toggle(self):
        if self.is_active:
            return self.stop_idle_loop()
        else:
            return self.start_idle_loop()
   
    #start idle loop system
    def start_idle_loop(self):
        if self.is_active:
            return False, "idle loop already active"
       
        if not self.preloaded_emotes:
            return False, "no emotes available for idle loop"
       
        if self.playback_manager.is_playing():
            return False, "cannot start idle while sequence is playing"
       
        #backup current sequence state
        self.original_sequence_backup = self.sequence_manager.get_sequence_data()
       
        self.is_active = True
        self.last_played_emote = None
       
        if self.log_callback:
            self.log_callback(f"started idle loop with {len(self.preloaded_emotes)} emotes")
       
        #start first cycle
        self._schedule_next_cycle()
        return True, "idle loop started"
   
    #stop idle loop and restore original sequence
    def stop_idle_loop(self):
        if not self.is_active:
            return True, "idle loop not active"
       
        self.is_active = False
       
        #cancel any pending timer
        if self.current_timer_id:
            try:
                self.gui_widget.after_cancel(self.current_timer_id)
            except:
                pass
            self.current_timer_id = None
       
        #stop any active playback
        if self.playback_manager.is_playing():
            self.playback_manager.stop_playback()
       
        #restore original sequence if backed up
        if self.original_sequence_backup is not None:
            self.sequence_manager.update_sequence_data(self.original_sequence_backup)
            self.original_sequence_backup = None
       
        if self.log_callback:
            self.log_callback("stopped idle loop and restored original sequence")
       
        return True, "idle loop stopped"
   
    #schedule next idle cycle with random timing
    def _schedule_next_cycle(self):
        if not self.is_active:
            return
       
        #generate random idle time
        idle_seconds = random.uniform(self.min_idle_time, self.max_idle_time)
        idle_ms = int(idle_seconds * 1000)
       
        if self.log_callback:
            self.log_callback(f"idle waiting {idle_seconds:.1f}s before next emote")
       
        #schedule emote playback using gui timing
        self.current_timer_id = self.gui_widget.after(idle_ms, self._play_random_emote)
   
    #select and play random emote
    def _play_random_emote(self):
        if not self.is_active or not self.preloaded_emotes:
            return
       
        #select random emote (avoid repeating last one)
        available_emotes = list(self.preloaded_emotes.keys())
        if len(available_emotes) > 1 and self.last_played_emote:
            available_emotes = [name for name in available_emotes if name != self.last_played_emote]
       
        selected_emote = random.choice(available_emotes)
        emote_data = self.preloaded_emotes[selected_emote]
       
        self.last_played_emote = selected_emote
       
        if self.log_callback:
            self.log_callback(f"playing idle emote: {selected_emote}")
       
        #temporarily load emote sequence
        try:
            #extract sequence data based on format
            if "servo_sequences" in emote_data:
                #unified bezier format
                sequence_data = emote_data["servo_sequences"]
            elif "keyframes" in emote_data:
                #legacy format - let sequence manager handle conversion
                success, message = self.sequence_manager.load_sequence(
                    os.path.join(self.emote_directory, f"{selected_emote}.json")
                )
                if not success:
                    if self.log_callback:
                        self.log_callback(f"failed to load legacy emote: {message}")
                    self._schedule_next_cycle()
                    return
                sequence_data = self.sequence_manager.get_sequence_data()
            else:
                if self.log_callback:
                    self.log_callback(f"invalid emote format: {selected_emote}")
                self._schedule_next_cycle()
                return
           
            #update sequence manager with emote data
            success, message = self.sequence_manager.update_sequence_data(sequence_data)
            if not success:
                if self.log_callback:
                    self.log_callback(f"failed to load emote sequence: {message}")
                self._schedule_next_cycle()
                return
           
            #play emote using existing playback system
            success, message = self.playback_manager.start_playback(self._on_emote_playback_complete)
            if not success:
                if self.log_callback:
                    self.log_callback(f"failed to start emote playback: {message}")
                self._schedule_next_cycle()
       
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"error playing emote {selected_emote}: {str(e)}")
            self._schedule_next_cycle()
   
    #handle emote playback completion
    def _on_emote_playback_complete(self, success, error_msg=None):
        if not self.is_active:
            return
       
        if not success and error_msg:
            if self.log_callback:
                self.log_callback(f"emote playback error: {error_msg}")
       
        #reset servos to defaults using existing system
        try:
            self.state_manager.reset_all_servos_to_defaults()
            if self.log_callback:
                self.log_callback("reset to defaults after emote")
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"error resetting to defaults: {str(e)}")
       
        #schedule next cycle if still active
        if self.is_active:
            self._schedule_next_cycle()
   
    #get current idle loop status
    def get_status(self):
        return {
            "is_active": self.is_active,
            "emotes_loaded": len(self.preloaded_emotes),
            "last_played": self.last_played_emote,
            "has_backup": self.original_sequence_backup is not None
        }
   
    #cleanup resources
    def cleanup(self):
        self.stop_idle_loop()
        self.preloaded_emotes.clear()
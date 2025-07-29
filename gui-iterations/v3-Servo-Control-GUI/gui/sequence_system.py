import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
import copy
from core.validation import (
    MAX_SEQUENCE_DURATION, MIN_KEYFRAME_INTERVAL, MAX_KEYFRAME_DELAY, 
    DEFAULT_KEYFRAME_DELAY, PLAYBACK_COMMAND_INTERVAL, PLAYBACK_TIMING_PRECISION,
    validate_timing, validate_component_positions
)
from core.event_system import publish, Events
from core.bezier_interpolation import (
    ensure_control_points, generate_playback_points, create_smooth_bezier_from_points,
    validate_bezier_keyframes
)
from gui.motion_editor import MotionEditor

class SequenceManager:
    #manages sequence data using unified bezier format for both recording and motion editing
    def __init__(self, state_manager):
        self.state = state_manager
        #unified bezier format as primary storage - no more dual formats
        self.sequence_data = {
            "metadata": {
                "max_duration": MAX_SEQUENCE_DURATION,
                "total_keyframes": 0,
                "creation_timestamp": None,
                "component_count": 0
            },
            "servo_sequences": {}  #bezier format: {component_name: [bezier_keyframes]}
        }
        self.gui_callbacks = []
        
        #recording state for time tracking
        self.next_recording_time = 0.0
    
    #add gui callback for updates
    def add_gui_callback(self, callback):
        if callback not in self.gui_callbacks:
            self.gui_callbacks.append(callback)
    
    #remove gui callback
    def remove_gui_callback(self, callback):
        if callback in self.gui_callbacks:
            self.gui_callbacks.remove(callback)
    
    #notify gui callbacks and event system
    def _notify_gui(self, event_type, *args):
        for callback in self.gui_callbacks[:]:
            try:
                callback(event_type, *args)
            except Exception:
                if callback in self.gui_callbacks:
                    self.gui_callbacks.remove(callback)
        
        publish(event_type, *args)
    
    #record keyframe directly in bezier format with automatic smooth curve generation
    def record_keyframe(self, delay_to_next):
        component_positions = self.state.get_current_component_positions()
        
        #validate timing for recording consistency
        timing_result = validate_timing(self.next_recording_time, delay_to_next)
        if not timing_result.is_valid:
            return False, timing_result.error_message
        
        #validate component positions
        positions_result = validate_component_positions(component_positions, self.state.servo_configurations)
        if not positions_result.is_valid:
            return False, positions_result.error_message
        
        current_time_ms = round(self.next_recording_time * 1000)
        
        #create bezier keyframes for each component
        for component_name, pulse_width in component_positions.items():
            if component_name not in self.sequence_data["servo_sequences"]:
                self.sequence_data["servo_sequences"][component_name] = []
            
            component_sequence = self.sequence_data["servo_sequences"][component_name]
            
            #create bezier keyframe
            bezier_keyframe = {
                "time": current_time_ms,
                "angle": pulse_width,
                "cp_in": None,
                "cp_out": None
            }
            
            component_sequence.append(bezier_keyframe)
        
        #update recording time for next keyframe
        self.next_recording_time += delay_to_next
        
        #ensure smooth bezier curves for all component sequences
        for component_name in self.sequence_data["servo_sequences"]:
            ensure_control_points(self.sequence_data["servo_sequences"][component_name], use_smooth_defaults=True)
        
        #update metadata
        self._update_metadata()
        
        if self.sequence_data["metadata"]["creation_timestamp"] is None:
            self.sequence_data["metadata"]["creation_timestamp"] = time.time()
        
        self._notify_gui(Events.SEQUENCE_KEYFRAME_ADDED, self._get_total_keyframe_count() - 1)
        return True, "keyframe recorded successfully"
    
    #update sequence metadata from current bezier data
    def _update_metadata(self):
        total_keyframes = 0
        component_count = len(self.sequence_data["servo_sequences"])
        
        for component_sequence in self.sequence_data["servo_sequences"].values():
            total_keyframes += len(component_sequence)
        
        self.sequence_data["metadata"]["total_keyframes"] = total_keyframes
        self.sequence_data["metadata"]["component_count"] = component_count
    
    #get total keyframe count across all components
    def _get_total_keyframe_count(self):
        total = 0
        for component_sequence in self.sequence_data["servo_sequences"].values():
            total += len(component_sequence)
        return total
    
    #remove keyframe by component and index with bezier curve regeneration
    def remove_keyframe(self, component_name, keyframe_index):
        if component_name not in self.sequence_data["servo_sequences"]:
            return False, "component not found in sequence"
        
        component_sequence = self.sequence_data["servo_sequences"][component_name]
        
        if keyframe_index < 0 or keyframe_index >= len(component_sequence):
            return False, "invalid keyframe index"
        
        if len(component_sequence) <= 2:
            return False, "cannot remove keyframe - minimum of 2 required per component"
        
        component_sequence.pop(keyframe_index)
        
        #regenerate smooth control points
        ensure_control_points(component_sequence, use_smooth_defaults=True)
        
        self._update_metadata()
        self._notify_gui(Events.SEQUENCE_KEYFRAME_REMOVED, keyframe_index)
        return True, "keyframe removed successfully"
    
    #clear entire sequence and reset recording state
    def clear_sequence(self):
        self.sequence_data["servo_sequences"].clear()
        self.sequence_data["metadata"]["total_keyframes"] = 0
        self.sequence_data["metadata"]["creation_timestamp"] = None
        self.sequence_data["metadata"]["component_count"] = 0
        self.next_recording_time = 0.0
        
        self._notify_gui(Events.SEQUENCE_CLEARED)
        return True, "sequence cleared successfully"
    
    #get bezier sequence data directly for motion editor (no conversion needed)
    def get_sequence_data(self):
        return copy.deepcopy(self.sequence_data["servo_sequences"])
    
    #update sequence data from motion editor (direct replacement)
    def update_sequence_data(self, updated_bezier_sequences):
        if not isinstance(updated_bezier_sequences, dict):
            return False, "invalid sequence data format"
        
        try:
            #validate all component sequences
            for component_name, keyframes in updated_bezier_sequences.items():
                if component_name in self.state.servo_configurations:
                    servo_config = self.state.get_component_config(component_name)
                    is_valid, error_msg = validate_bezier_keyframes(keyframes, servo_config)
                    if not is_valid:
                        return False, f"{component_name}: {error_msg}"
            
            #replace sequence data directly
            self.sequence_data["servo_sequences"] = copy.deepcopy(updated_bezier_sequences)
            self._update_metadata()
            self._notify_gui(Events.SEQUENCE_UPDATED)
            return True, "sequence updated successfully"
            
        except Exception as e:
            return False, f"failed to update sequence: {str(e)}"
    
    #get keyframes in time-based format for display compatibility (conversion for ui only)
    def get_keyframes(self):
        #generate time-based representation for display purposes only
        time_based_keyframes = []
        
        if not self.sequence_data["servo_sequences"]:
            return time_based_keyframes
        
        #collect all unique timestamps
        all_times = set()
        for component_sequence in self.sequence_data["servo_sequences"].values():
            for kf in component_sequence:
                all_times.add(kf["time"])
        
        sorted_times = sorted(list(all_times))
        
        #create time-based keyframes for display
        for i, time_ms in enumerate(sorted_times):
            delay_to_next = (sorted_times[i+1] - time_ms) / 1000.0 if i < len(sorted_times) - 1 else 1.0
            
            keyframe = {
                "absolute_time": time_ms / 1000.0,
                "delay_to_next": delay_to_next,
                "component_positions": {}
            }
            
            #collect component positions at this time
            for component_name, component_sequence in self.sequence_data["servo_sequences"].items():
                for kf in component_sequence:
                    if kf["time"] == time_ms:
                        keyframe["component_positions"][component_name] = kf["angle"]
                        break
            
            time_based_keyframes.append(keyframe)
        
        return time_based_keyframes
    
    #get keyframe by display index (for ui compatibility)
    def get_keyframe(self, index):
        keyframes = self.get_keyframes()
        if 0 <= index < len(keyframes):
            return keyframes[index].copy()
        return None
    
    #check if any sequences have keyframes
    def has_keyframes(self):
        return len(self.sequence_data["servo_sequences"]) > 0 and any(
            len(seq) > 0 for seq in self.sequence_data["servo_sequences"].values()
        )
    
    #get total keyframe count for display
    def get_keyframe_count(self):
        return len(self.get_keyframes())  #display count, not total bezier keyframes
    
    #get total sequence duration from bezier data
    def get_total_duration(self):
        if not self.sequence_data["servo_sequences"]:
            return 0.0
        
        max_time = 0
        for component_sequence in self.sequence_data["servo_sequences"].values():
            if component_sequence:
                component_max = max(kf["time"] for kf in component_sequence)
                max_time = max(max_time, component_max)
        
        return max_time / 1000.0  #convert to seconds
    
    #get all components that have sequences
    def get_sequence_components(self):
        return sorted(list(self.sequence_data["servo_sequences"].keys()))
    
    #resolve keyframe to servo commands using bezier interpolation
    def resolve_keyframe_to_commands(self, keyframe):
        if "component_positions" not in keyframe:
            return [], []
        
        commands = []
        missing_components = []
        
        for component_name, pulse_width in keyframe["component_positions"].items():
            if component_name in self.state.servo_configurations:
                servo_index = self.state.servo_configurations[component_name]["index"]
                commands.append(f"SP:{servo_index}:{pulse_width}")
            else:
                missing_components.append(component_name)
        
        return commands, missing_components
    
    #validate sequence integrity
    def validate_sequence_integrity(self):
        issues = []
        
        for component_name, component_sequence in self.sequence_data["servo_sequences"].items():
            if component_name not in self.state.servo_configurations:
                issues.append(f"component '{component_name}' no longer exists")
                continue
            
            servo_config = self.state.get_component_config(component_name)
            is_valid, error_msg = validate_bezier_keyframes(component_sequence, servo_config)
            if not is_valid:
                issues.append(f"component '{component_name}': {error_msg}")
        
        return issues
    
    #save sequence in bezier format for curve preservation
    def save_sequence(self, file_path=None):
        if not self.has_keyframes():
            return False, "no sequence to save"
        
        if file_path is None:
            file_path = filedialog.asksaveasfilename(
                title="save sequence",
                defaultextension=".json",
                filetypes=[("json files", "*.json"), ("all files", "*.*")]
            )
        
        if not file_path:
            return False, "no file selected"
        
        try:
            save_data = {
                "metadata": {
                    "version": "3.0",
                    "format": "bezier_unified",
                    "creation_timestamp": self.sequence_data["metadata"]["creation_timestamp"],
                    "total_duration": self.get_total_duration(),
                    "interpolation_resolution": 50,
                    "timing_precision": PLAYBACK_TIMING_PRECISION
                },
                "servo_sequences": copy.deepcopy(self.sequence_data["servo_sequences"]),
                "servo_configs": {}
            }
            
            #include servo configurations for validation on load
            components_used = self.get_sequence_components()
            for component_name in components_used:
                if component_name in self.state.servo_configurations:
                    config = self.state.servo_configurations[component_name]
                    save_data["servo_configs"][component_name] = {
                        "index": config["index"],
                        "pulse_min": config["pulse_min"],
                        "pulse_max": config["pulse_max"],
                        "name": component_name
                    }
            
            with open(file_path, 'w') as file:
                json.dump(save_data, file, indent=2)
            
            return True, f"sequence saved to {file_path}"
            
        except Exception as e:
            return False, f"error saving sequence: {str(e)}"
    
    #load sequence from bezier or legacy formats
    def load_sequence(self, file_path=None, next_delay=DEFAULT_KEYFRAME_DELAY):
        if file_path is None:
            file_path = filedialog.askopenfilename(
                title="load sequence",
                filetypes=[("json files", "*.json"), ("all files", "*.*")]
            )
        
        if not file_path:
            return False, "no file selected"
        
        try:
            with open(file_path, 'r') as file:
                loaded_data = json.load(file)
            
            #handle unified bezier format
            if "servo_sequences" in loaded_data and loaded_data.get("metadata", {}).get("format") == "bezier_unified":
                self.sequence_data["servo_sequences"] = copy.deepcopy(loaded_data["servo_sequences"])
                
                #ensure all sequences have proper control points
                for component_name in self.sequence_data["servo_sequences"]:
                    ensure_control_points(self.sequence_data["servo_sequences"][component_name], use_smooth_defaults=True)
                
                if "metadata" in loaded_data:
                    self.sequence_data["metadata"].update(loaded_data["metadata"])
                
                #reset recording time to end of loaded sequence
                self.next_recording_time = self.get_total_duration() + next_delay
                
            #handle legacy time-based format (convert to bezier)
            elif "keyframes" in loaded_data and "metadata" in loaded_data:
                self._convert_legacy_format(loaded_data)
                
            #handle legacy motion-centric format (direct use)
            elif "servo_sequences" in loaded_data:
                self.sequence_data["servo_sequences"] = copy.deepcopy(loaded_data["servo_sequences"])
                
                #ensure control points
                for component_name in self.sequence_data["servo_sequences"]:
                    ensure_control_points(self.sequence_data["servo_sequences"][component_name], use_smooth_defaults=True)
                
                self.next_recording_time = self.get_total_duration()
                
            else:
                return False, "invalid sequence file format"
            
            self._update_metadata()
            self._notify_gui(Events.SEQUENCE_LOADED)
            return True, f"sequence loaded from {file_path}"
            
        except Exception as e:
            return False, f"error loading sequence: {str(e)}"
    
    #convert legacy time-based format to unified bezier format
    def _convert_legacy_format(self, legacy_data):
        self.sequence_data["servo_sequences"].clear()
        
        #extract component sequences from time-based keyframes
        for keyframe in legacy_data["keyframes"]:
            time_ms = round(keyframe["absolute_time"] * 1000)
            
            for component_name, pulse_width in keyframe["component_positions"].items():
                if component_name not in self.sequence_data["servo_sequences"]:
                    self.sequence_data["servo_sequences"][component_name] = []
                
                bezier_keyframe = {
                    "time": time_ms,
                    "angle": pulse_width,
                    "cp_in": None,
                    "cp_out": None
                }
                
                self.sequence_data["servo_sequences"][component_name].append(bezier_keyframe)
        
        #generate smooth control points for all sequences
        for component_name in self.sequence_data["servo_sequences"]:
            ensure_control_points(self.sequence_data["servo_sequences"][component_name], use_smooth_defaults=True)
        
        self.next_recording_time = self.get_total_duration()


class PlaybackManager:
    #manages sequence playback using unified bezier interpolation
    def __init__(self, sequence_manager, serial_connection, log_callback, gui_callback):
        self.sequence_manager = sequence_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        self.gui_callback = gui_callback
        
        self.is_playing_flag = False
        self.playback_thread = None
        self.stop_requested = False
    
    #check playback status
    def is_playing(self):
        return self.is_playing_flag
    
    #start sequence playback using bezier interpolation
    def start_playback(self):
        if self.is_playing_flag:
            return False, "playback already in progress"
        
        if not self.sequence_manager.has_keyframes():
            return False, "no sequence to play"
        
        if not self.serial_connection.is_connected:
            return False, "serial connection required"
        
        self.stop_requested = False
        self.playback_thread = threading.Thread(target=self._playback_thread, daemon=True)
        self.playback_thread.start()
        
        return True, "playback started"
    
    #stop sequence playback
    def stop_playback(self):
        if self.is_playing_flag:
            self.stop_requested = True
            
            if self.playback_thread and self.playback_thread.is_alive():
                self.playback_thread.join(timeout=1.0)
        
        self._reset_playback_state()
    
    #reset playback state
    def _reset_playback_state(self):
        self.is_playing_flag = False
        self.stop_requested = False
        self.playback_thread = None
        self._notify_gui("playback_stopped")
    
    #notify gui of events
    def _notify_gui(self, event_type, *args):
        if self.gui_callback:
            try:
                self.gui_callback(event_type, *args)
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"gui callback error: {str(e)}")
    
    #main playback thread using bezier interpolation
    def _playback_thread(self):
        try:
            self.is_playing_flag = True
            self._notify_gui("playback_started")
            
            total_duration = self.sequence_manager.get_total_duration()
            
            if self.log_callback:
                components_used = self.sequence_manager.get_sequence_components()
                self.log_callback(f"starting bezier playback: {len(components_used)} components, {total_duration:.1f}s duration")
            
            self._execute_bezier_playback(total_duration)
            
            if self.log_callback:
                self.log_callback("bezier sequence playback completed")
                
        except Exception as e:
            error_msg = f"playback error: {str(e)}"
            if self.log_callback:
                self.log_callback(error_msg)
            self._notify_gui("playback_error", error_msg)
            
        finally:
            self._reset_playback_state()
    
    #execute sequence using unified bezier interpolation
    def _execute_bezier_playback(self, total_duration):
        #generate interpolated command timeline for all components
        command_timeline = []
        
        bezier_sequences = self.sequence_manager.get_sequence_data()
        
        for component_name, component_sequence in bezier_sequences.items():
            if component_name in self.sequence_manager.state.servo_configurations:
                servo_config = self.sequence_manager.state.get_component_config(component_name)
                servo_index = servo_config["index"]
                
                #generate playback points using shared bezier interpolation
                playback_points = generate_playback_points(component_sequence, servo_config, time_step=50)
                
                for time_ms, angle in playback_points:
                    command_timeline.append((time_ms, f"SP:{servo_index}:{angle}"))
        
        #sort commands by time
        command_timeline.sort(key=lambda x: x[0])
        
        #execute timed playback
        playback_start_time = time.time()
        
        for cmd_time_ms, command in command_timeline:
            if self.stop_requested:
                break
            
            #wait for correct timing
            target_time = playback_start_time + (cmd_time_ms / 1000.0)
            current_time = time.time()
            
            if current_time < target_time:
                time.sleep(target_time - current_time)
            
            #send command
            if self.serial_connection.is_connected:
                self.serial_connection.send_command(command)
            
            #small delay to prevent command flooding
            time.sleep(PLAYBACK_COMMAND_INTERVAL)
    
    #preview keyframe commands (for display compatibility)
    def preview_keyframe_commands(self, keyframe_index):
        keyframes = self.sequence_manager.get_keyframes()
        
        if not (0 <= keyframe_index < len(keyframes)):
            return [], ["invalid keyframe index"]
        
        keyframe = keyframes[keyframe_index]
        return self.sequence_manager.resolve_keyframe_to_commands(keyframe)


class TimelineVisualiser:
    #timeline visualisation for sequence display using bezier data
    def __init__(self, parent, max_duration=120.0, height=40):
        self.frame = ttk.Frame(parent)
        self.max_duration = max_duration
        self.height = height
        
        self.keyframes = []
        self.total_duration = 0.0
        self.is_animating = False
        self.animation_start_time = 0.0
        self.animation_duration = 0.0
        self.playback_line_id = None
        
        self._create_timeline()
    
    #create timeline canvas
    def _create_timeline(self):
        self.canvas = tk.Canvas(self.frame, height=self.height, bg="white", relief="sunken", bd=1)
        self.canvas.pack(fill="x", padx=5, pady=2)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._draw_timeline()
    
    #handle canvas resize
    def _on_canvas_resize(self, event):
        self._draw_timeline()
    
    #update sequence data for visualisation
    def update_sequence(self, keyframes, total_duration):
        self.keyframes = keyframes.copy() if keyframes else []
        self.total_duration = total_duration
        self._draw_timeline()
    
    #draw complete timeline
    def _draw_timeline(self):
        if not self.canvas:
            return
        
        self.canvas.delete("all")
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        self._draw_background(canvas_width, canvas_height)
        self._draw_time_markers(canvas_width, canvas_height)
        self._draw_keyframes(canvas_width, canvas_height)
        
        if self.is_animating and self.playback_line_id:
            self._update_playback_line()
    
    #draw timeline background
    def _draw_background(self, width, height):
        self.canvas.create_rectangle(0, 0, width, height, fill="#f8f8f8", outline="#cccccc")
        
        track_y = height // 2
        track_height = 6
        self.canvas.create_rectangle(10, track_y - track_height//2, width - 10, track_y + track_height//2, fill="#e0e0e0", outline="#cccccc")
        
        if self.max_duration > 0:
            duration_ratio = min(1.0, self.total_duration / self.max_duration)
            duration_width = int((width - 20) * duration_ratio)
            
            if duration_width > 0:
                self.canvas.create_rectangle(10, track_y - track_height//2, 10 + duration_width, track_y + track_height//2, fill="#4CAF50", outline="")
    
    #draw time markers
    def _draw_time_markers(self, width, height):
        if self.max_duration <= 0:
            return
        
        marker_interval = 10.0 if self.max_duration > 60 else (5.0 if self.max_duration > 10 else 1.0)
        
        current_time = 0.0
        while current_time <= self.max_duration:
            x_pos = 10 + int((current_time / self.max_duration) * (width - 20))
            
            self.canvas.create_line(x_pos, height - 15, x_pos, height - 5, fill="#666666", width=1)
            
            if current_time == 0 or current_time % (marker_interval * 2) == 0:
                time_text = f"{current_time:.0f}s"
                self.canvas.create_text(x_pos, height - 18, text=time_text, font=("Arial", 8), fill="#666666", anchor="s")
            
            current_time += marker_interval
    
    #draw keyframe indicators
    def _draw_keyframes(self, width, height):
        if not self.keyframes or self.max_duration <= 0:
            return
        
        track_y = height // 2
        keyframe_height = 12
        timeline_width = width - 20
        
        colours = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#607D8B"]
        
        for i, keyframe in enumerate(self.keyframes):
            start_time = keyframe["absolute_time"]
            duration = keyframe["delay_to_next"]
            
            start_ratio = start_time / self.max_duration
            duration_ratio = duration / self.max_duration
            
            start_x = 10 + int(start_ratio * timeline_width)
            duration_width = max(4, int(duration_ratio * timeline_width))
            end_x = min(width - 10, start_x + duration_width)
            
            if end_x > start_x:
                keyframe_colour = colours[i % len(colours)]
                
                self.canvas.create_rectangle(start_x, track_y - keyframe_height//2, end_x, track_y + keyframe_height//2, fill=keyframe_colour, outline="#333333", width=1)
                
                if (end_x - start_x) >= 15:
                    label_x = start_x + (end_x - start_x) // 2
                    self.canvas.create_text(label_x, track_y, text=str(i + 1), font=("Arial", 8, "bold"), fill="white", anchor="center")
    
    #start playback animation
    def start_playback_animation(self, duration):
        if duration <= 0:
            return
        
        self.is_animating = True
        self.animation_start_time = time.time()
        self.animation_duration = duration
        
        self.playback_line_id = self.canvas.create_line(0, 0, 0, self.canvas.winfo_height(), fill="#FF5722", width=2)
        
        self._animate_playback()
    
    #stop playback animation
    def stop_playback_animation(self):
        self.is_animating = False
        if self.playback_line_id:
            self.canvas.delete(self.playback_line_id)
            self.playback_line_id = None
    
    #animate playback line
    def _animate_playback(self):
        if not self.is_animating or not self.playback_line_id:
            return
        
        elapsed_time = time.time() - self.animation_start_time
        
        if elapsed_time >= self.animation_duration:
            self.stop_playback_animation()
            return
        
        self._update_playback_line(elapsed_time)
        self.canvas.after(50, self._animate_playback)
    
    #update playback line position
    def _update_playback_line(self, elapsed_seconds=None):
        if not self.playback_line_id or not self.is_animating:
            return
        
        if elapsed_seconds is None:
            elapsed_seconds = time.time() - self.animation_start_time
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or self.max_duration <= 0:
            return
        
        timeline_ratio = (elapsed_seconds / self.max_duration) if self.max_duration > 0 else 0
        timeline_ratio = max(0.0, min(1.0, timeline_ratio))
        
        x_pos = 10 + int(timeline_ratio * (canvas_width - 20))
        self.canvas.coords(self.playback_line_id, x_pos, 0, x_pos, canvas_height)


class SequenceRecorderWidget:
    #sequence recording interface with unified bezier integration
    def __init__(self, parent, sequence_manager, serial_connection, log_callback):
        self.frame = ttk.LabelFrame(parent, text="sequence recording")
        self.sequence_manager = sequence_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #gui variables
        self.delay_var = tk.DoubleVar(value=DEFAULT_KEYFRAME_DELAY)
        self.selected_step_index = None
        
        #playback manager using unified bezier system
        self.playback_manager = PlaybackManager(
            sequence_manager=sequence_manager,
            serial_connection=serial_connection,
            log_callback=log_callback,
            gui_callback=self._on_playback_event
        )
        
        #motion editor window reference
        self.motion_editor_window = None
        
        self._create_ui()
        
        #register gui callback for updates
        self.sequence_manager.add_gui_callback(self._on_sequence_event)
    
    #create recording interface
    def _create_ui(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        #delay control
        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(fill="x", pady=5)
        
        ttk.Label(delay_frame, text="delay to next step (seconds):").pack(side="left", padx=5)
        
        self.delay_spinbox = ttk.Spinbox(delay_frame, from_=MIN_KEYFRAME_INTERVAL, to=MAX_KEYFRAME_DELAY, increment=0.1, textvariable=self.delay_var, width=8, format="%.1f")
        self.delay_spinbox.pack(side="left", padx=5)
        
        #control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill="x", pady=5)
        
        self.record_button = ttk.Button(control_frame, text="record step", command=self._record_step)
        self.record_button.pack(side="left", padx=5)
        
        self.play_button = ttk.Button(control_frame, text="play sequence", command=self._play_sequence)
        self.play_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="stop", command=self._stop_playback, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(control_frame, text="clear", command=self._clear_sequence)
        self.clear_button.pack(side="left", padx=5)
        
        #file operations and motion editor
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill="x", pady=5)
        
        self.save_button = ttk.Button(file_frame, text="save sequence", command=self._save_sequence)
        self.save_button.pack(side="left", padx=5)
        
        self.load_button = ttk.Button(file_frame, text="load sequence", command=self._load_sequence)
        self.load_button.pack(side="left", padx=5)
        
        #motion editor integration - simplified without format conversion
        self.motion_editor_button = ttk.Button(file_frame, text="edit motion curves", command=self._launch_motion_editor, state="disabled")
        self.motion_editor_button.pack(side="left", padx=5)
        
        #timeline visualiser
        timeline_frame = ttk.LabelFrame(main_frame, text="timeline")
        timeline_frame.pack(fill="x", pady=5)
        
        self.timeline_visualiser = TimelineVisualiser(timeline_frame, MAX_SEQUENCE_DURATION, 40)
        self.timeline_visualiser.frame.pack(fill="x")
        
        #sequence display
        display_frame = ttk.LabelFrame(main_frame, text="recorded steps")
        display_frame.pack(fill="both", expand=True, pady=5)
        
        #step tree
        columns = ("step", "time", "duration", "components")
        self.step_tree = ttk.Treeview(display_frame, columns=columns, show="headings", height=8)
        
        self.step_tree.heading("step", text="step")
        self.step_tree.heading("time", text="time (s)")
        self.step_tree.heading("duration", text="duration (s)")
        self.step_tree.heading("components", text="components")
        
        self.step_tree.column("step", width=50, anchor="center")
        self.step_tree.column("time", width=80, anchor="center")
        self.step_tree.column("duration", width=80, anchor="center")
        self.step_tree.column("components", width=300, anchor="w")
        
        scrollbar = ttk.Scrollbar(display_frame, orient="vertical", command=self.step_tree.yview)
        self.step_tree.configure(yscrollcommand=scrollbar.set)
        
        self.step_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.step_tree.bind("<<TreeviewSelect>>", self._on_step_selected)
        
        #step management
        step_frame = ttk.Frame(main_frame)
        step_frame.pack(fill="x", pady=5)
        
        self.remove_button = ttk.Button(step_frame, text="remove selected", command=self._remove_selected_step)
        self.remove_button.pack(side="left", padx=5)
        
        self.preview_button = ttk.Button(step_frame, text="preview", command=self._preview_selected_step)
        self.preview_button.pack(side="left", padx=5)
        
        #force initial update
        self._update_all_displays()
    
    #launch motion editor with simplified integration (no format conversion needed)
    def _launch_motion_editor(self):
        if not self.sequence_manager.has_keyframes():
            messagebox.showinfo("no sequence", "no sequence data to edit")
            return
        
        #close existing motion editor if open
        if self.motion_editor_window:
            try:
                self.motion_editor_window.window.destroy()
            except:
                pass
            self.motion_editor_window = None
        
        #get bezier sequence data directly (no conversion needed)
        sequence_data = self.sequence_manager.get_sequence_data()
        
        #define save callback function for data persistence
        def save_callback(updated_data):
            success, message = self.sequence_manager.update_sequence_data(updated_data)
            if success:
                self._update_all_displays()  #refresh displays immediately
            return success, message
        
        #create motion editor instance with callback
        self.motion_editor_window = MotionEditor(
            parent=self.frame,
            sequence_data=sequence_data,
            state_manager=self.sequence_manager.state,
            serial_connection=self.serial_connection,
            log_callback=self.log_callback,
            save_callback=save_callback
        )
        
        self.motion_editor_window.show()
        
        if self.log_callback:
            self.log_callback("launched motion editor")
    
    #record new step
    def _record_step(self):
        delay = self.delay_var.get()
        success, message = self.sequence_manager.record_keyframe(delay)
        
        if success:
            components_used = len(self.sequence_manager.get_sequence_components())
            self.log_callback(f"recorded bezier step {self.sequence_manager.get_keyframe_count()}: {components_used} components")
        else:
            messagebox.showerror("recording error", message)
            self.log_callback(f"recording failed: {message}")
    
    #play sequence using unified bezier interpolation
    def _play_sequence(self):
        if not self.sequence_manager.has_keyframes():
            messagebox.showinfo("no sequence", "no sequence to play")
            return
        
        if not self.serial_connection.is_connected:
            messagebox.showwarning("not connected", "serial connection required for playback")
            return
        
        success, message = self.playback_manager.start_playback()
        if not success:
            messagebox.showerror("playback error", message)
    
    #stop playback
    def _stop_playback(self):
        self.playback_manager.stop_playback()
    
    #clear sequence
    def _clear_sequence(self):
        if not self.sequence_manager.has_keyframes():
            return
        
        if messagebox.askyesno("confirm clear", "clear the entire sequence?"):
            success, message = self.sequence_manager.clear_sequence()
            if success:
                self.log_callback("sequence cleared")
    
    #save sequence in unified bezier format
    def _save_sequence(self):
        success, message = self.sequence_manager.save_sequence()
        
        if success:
            messagebox.showinfo("save successful", message)
            self.log_callback(message)
        elif "no file selected" not in message:
            messagebox.showerror("save error", message)
    
    #load sequence with unified bezier support
    def _load_sequence(self):
        current_delay = self.delay_var.get()
        success, message = self.sequence_manager.load_sequence(next_delay=current_delay)
        
        if success:
            messagebox.showinfo("load successful", message)
            self.log_callback(message)
        elif "no file selected" not in message:
            messagebox.showerror("load error", message)
    
    #handle step selection
    def _on_step_selected(self, event):
        selection = self.step_tree.selection()
        if selection:
            self.selected_step_index = self.step_tree.index(selection[0])
        else:
            self.selected_step_index = None
        self._update_button_states()
    
    #remove selected step (simplified without delay editing)
    def _remove_selected_step(self):
        if self.selected_step_index is None:
            return
        
        #get target timestamp from display format
        keyframes = self.sequence_manager.get_keyframes()
        if self.selected_step_index >= len(keyframes):
            return
        
        target_keyframe = keyframes[self.selected_step_index]
        target_time_ms = round(target_keyframe["absolute_time"] * 1000)
        
        #surgical removal from bezier format across all components
        components_modified = []
        components_invalid = []
        
        for component_name, component_sequence in self.sequence_manager.sequence_data["servo_sequences"].items():
            #find and remove keyframes matching target timestamp
            original_length = len(component_sequence)
            component_sequence[:] = [kf for kf in component_sequence if kf["time"] != target_time_ms]
            new_length = len(component_sequence)
            
            if new_length != original_length:
                components_modified.append(component_name)
                
                #check if component sequence is still valid (minimum 2 keyframes)
                if new_length < 2:
                    components_invalid.append(component_name)
        
        #prevent removal if it would invalidate any sequences
        if components_invalid:
            messagebox.showwarning("removal blocked", 
                f"cannot remove step - would leave insufficient keyframes in: {', '.join(components_invalid)}")
            return
        
        #update system state after successful removal
        if components_modified:
            self.sequence_manager._update_metadata()
            self.log_callback(f"removed step {self.selected_step_index + 1} from {len(components_modified)} components")
            
            #refresh displays and clear selection
            self.selected_step_index = None
            self._update_all_displays()
        else:
            self.log_callback(f"no keyframes found at step {self.selected_step_index + 1} timestamp")
    
    #preview selected step
    def _preview_selected_step(self):
        if self.selected_step_index is None:
            return
        
        if not self.serial_connection.is_connected:
            messagebox.showwarning("not connected", "serial connection required for preview")
            return
        
        commands, missing = self.playback_manager.preview_keyframe_commands(self.selected_step_index)
        
        if missing:
            messagebox.showwarning("missing components", f"components not found: {', '.join(missing)}")
        
        if commands:
            success_count = self.serial_connection.send_batch_commands(commands)
            self.log_callback(f"previewed step {self.selected_step_index + 1}: sent {success_count}/{len(commands)} commands")
    
    #handle sequence events
    def _on_sequence_event(self, event_type, *args):
        self._update_all_displays()
    
    #handle playback events
    def _on_playback_event(self, event_type, *args):
        if event_type == "playback_started":
            self._update_button_states()
            self.timeline_visualiser.start_playback_animation(self.sequence_manager.get_total_duration())
            
        elif event_type == "playback_stopped":
            self._update_button_states()
            self.timeline_visualiser.stop_playback_animation()
            
        elif event_type == "playback_error":
            error_msg = args[0] if args else "unknown error"
            messagebox.showerror("playback error", error_msg)
    
    #update all displays
    def _update_all_displays(self):
        self._update_sequence_display()
        self._update_timeline()
        self._update_button_states()
    
    #update sequence display (using display-compatible format)
    def _update_sequence_display(self):
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
        
        keyframes = self.sequence_manager.get_keyframes()
        
        for i, keyframe in enumerate(keyframes):
            component_positions = keyframe["component_positions"]
            component_count = len(component_positions)
            
            if component_count <= 3:
                component_summary = ", ".join([f"{name}:{val}" for name, val in list(component_positions.items())[:3]])
            else:
                items = list(component_positions.items())[:2]
                component_summary = ", ".join([f"{name}:{val}" for name, val in items]) + f", ... ({component_count} total)"
            
            self.step_tree.insert("", "end", values=(
                i + 1,
                f"{keyframe['absolute_time']:.1f}",
                f"{keyframe['delay_to_next']:.1f}",
                component_summary
            ))
    
    #update timeline visualiser
    def _update_timeline(self):
        keyframes = self.sequence_manager.get_keyframes()
        total_duration = self.sequence_manager.get_total_duration()
        self.timeline_visualiser.update_sequence(keyframes, total_duration)
    
    #update button states
    def _update_button_states(self):
        has_keyframes = self.sequence_manager.has_keyframes()
        is_playing = self.playback_manager.is_playing()
        has_selection = self.selected_step_index is not None
        is_connected = self.serial_connection.is_connected
        
        self.record_button.config(state="normal" if not is_playing else "disabled")
        self.play_button.config(state="normal" if has_keyframes and not is_playing and is_connected else "disabled")
        self.stop_button.config(state="normal" if is_playing else "disabled")
        self.clear_button.config(state="normal" if has_keyframes and not is_playing else "disabled")
        
        self.save_button.config(state="normal" if has_keyframes else "disabled")
        self.load_button.config(state="normal" if not is_playing else "disabled")
        
        self.remove_button.config(state="normal" if has_selection and not is_playing else "disabled")
        self.preview_button.config(state="normal" if has_selection and not is_playing and is_connected else "disabled")
        
        self.delay_spinbox.config(state="normal" if not is_playing else "disabled")
        
        #motion editor button
        self.motion_editor_button.config(state="normal" if has_keyframes and not is_playing else "disabled")
    
    #widget visibility methods
    def show(self):
        self.frame.pack(fill="both", expand=True)
        self._update_all_displays()
    
    def hide(self):
        self.frame.pack_forget()
    
    def is_visible(self):
        return self.frame.winfo_manager() == "pack"
    
    #cleanup
    def cleanup(self):
        if self.motion_editor_window:
            try:
                self.motion_editor_window.window.destroy()
            except:
                pass
            self.motion_editor_window = None
        
        if hasattr(self, 'sequence_manager'):
            self.sequence_manager.remove_gui_callback(self._on_sequence_event)
    
    def __del__(self):
        self.cleanup()
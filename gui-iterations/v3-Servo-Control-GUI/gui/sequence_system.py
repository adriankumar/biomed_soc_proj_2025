#sequence recording and playback system with reliable gui updates

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
from core.validation import (
    MAX_SEQUENCE_DURATION, MIN_KEYFRAME_INTERVAL, MAX_KEYFRAME_DELAY, 
    DEFAULT_KEYFRAME_DELAY, PLAYBACK_COMMAND_INTERVAL, PLAYBACK_TIMING_PRECISION,
    validate_timing, validate_component_positions
)
from core.event_system import subscribe, publish, Events

class SequenceManager:
    #manages sequence data and operations
    def __init__(self, state_manager):
        self.state = state_manager
        self.sequence_data = {
            "metadata": {
                "max_duration": MAX_SEQUENCE_DURATION,
                "total_keyframes": 0,
                "creation_timestamp": None,
                "component_count": 0
            },
            "keyframes": []
        }
        self.dirty_timing_from_index = None
        self.gui_callbacks = []  #direct callbacks for reliability
    
    #add gui callback for updates
    def add_gui_callback(self, callback):
        if callback not in self.gui_callbacks:
            self.gui_callbacks.append(callback)
    
    #remove gui callback
    def remove_gui_callback(self, callback):
        if callback in self.gui_callbacks:
            self.gui_callbacks.remove(callback)
    
    #notify gui callbacks directly
    def _notify_gui(self, event_type, *args):
        #use direct callbacks for reliability
        for callback in self.gui_callbacks[:]:  #copy list to avoid modification during iteration
            try:
                callback(event_type, *args)
            except Exception:
                #remove failed callbacks
                if callback in self.gui_callbacks:
                    self.gui_callbacks.remove(callback)
        
        #also publish to event system for other subscribers
        publish(event_type, *args)
    
    #record keyframe with current component positions
    def record_keyframe(self, delay_to_next):
        component_positions = self.state.get_current_component_positions()
        absolute_time = self._calculate_next_absolute_time()
        
        #validate timing
        timing_result = validate_timing(absolute_time, delay_to_next)
        if not timing_result.is_valid:
            return False, timing_result.error_message
        
        #validate component positions
        positions_result = validate_component_positions(component_positions, self.state.servo_configurations)
        if not positions_result.is_valid:
            return False, positions_result.error_message
        
        #create keyframe
        keyframe = {
            "absolute_time": round(absolute_time, 3),
            "component_positions": component_positions.copy(),
            "delay_to_next": round(delay_to_next, 3)
        }
        
        self.sequence_data["keyframes"].append(keyframe)
        self.sequence_data["metadata"]["total_keyframes"] = len(self.sequence_data["keyframes"])
        self.sequence_data["metadata"]["component_count"] = len(component_positions)
        
        if self.sequence_data["metadata"]["creation_timestamp"] is None:
            self.sequence_data["metadata"]["creation_timestamp"] = time.time()
        
        self._notify_gui(Events.SEQUENCE_KEYFRAME_ADDED, len(self.sequence_data["keyframes"]) - 1)
        return True, "keyframe recorded successfully"
    
    #remove keyframe with optimised recalculation
    def remove_keyframe(self, index):
        if index < 0 or index >= len(self.sequence_data["keyframes"]):
            return False, "invalid keyframe index"
        
        if len(self.sequence_data["keyframes"]) <= 1:
            return False, "cannot remove the only keyframe, use clear instead"
        
        self.sequence_data["keyframes"].pop(index)
        
        #mark timing dirty from removal point
        self.dirty_timing_from_index = index
        self._recalculate_timing_from_dirty()
        
        self.sequence_data["metadata"]["total_keyframes"] = len(self.sequence_data["keyframes"])
        
        self._notify_gui(Events.SEQUENCE_KEYFRAME_REMOVED, index)
        return True, "keyframe removed successfully"
    
    #update keyframe delay with optimised recalculation
    def update_keyframe_delay(self, index, new_delay):
        if index < 0 or index >= len(self.sequence_data["keyframes"]):
            return False, "invalid keyframe index"
        
        old_keyframe = self.sequence_data["keyframes"][index].copy()
        
        #update delay
        self.sequence_data["keyframes"][index]["delay_to_next"] = round(new_delay, 3)
        
        #mark timing dirty from this point
        self.dirty_timing_from_index = index + 1
        self._recalculate_timing_from_dirty()
        
        #validate total duration
        total_duration = self.get_total_duration()
        if total_duration > MAX_SEQUENCE_DURATION:
            #revert change
            self.sequence_data["keyframes"][index] = old_keyframe
            self.dirty_timing_from_index = index + 1
            self._recalculate_timing_from_dirty()
            return False, f"delay would exceed maximum duration of {MAX_SEQUENCE_DURATION} seconds"
        
        self._notify_gui(Events.SEQUENCE_UPDATED)
        return True, "keyframe delay updated successfully"
    
    #optimised timing recalculation
    def _recalculate_timing_from_dirty(self):
        if self.dirty_timing_from_index is None:
            return
        
        keyframes = self.sequence_data["keyframes"]
        if not keyframes or self.dirty_timing_from_index >= len(keyframes):
            self.dirty_timing_from_index = None
            return
        
        #recalculate from dirty index forward
        for i in range(self.dirty_timing_from_index, len(keyframes)):
            if i == 0:
                keyframes[i]["absolute_time"] = 0.0
            else:
                prev_keyframe = keyframes[i-1]
                keyframes[i]["absolute_time"] = round(
                    prev_keyframe["absolute_time"] + prev_keyframe["delay_to_next"], 3
                )
        
        self.dirty_timing_from_index = None
    
    #calculate next keyframe absolute time
    def _calculate_next_absolute_time(self):
        if not self.sequence_data["keyframes"]:
            return 0.0
        
        last_keyframe = self.sequence_data["keyframes"][-1]
        return last_keyframe["absolute_time"] + last_keyframe["delay_to_next"]
    
    #clear entire sequence
    def clear_sequence(self):
        self.sequence_data["keyframes"].clear()
        self.sequence_data["metadata"]["total_keyframes"] = 0
        self.sequence_data["metadata"]["creation_timestamp"] = None
        self.sequence_data["metadata"]["component_count"] = 0
        self.dirty_timing_from_index = None
        
        self._notify_gui(Events.SEQUENCE_CLEARED)
        return True, "sequence cleared successfully"
    
    #get sequence data
    def get_keyframes(self):
        return self.sequence_data["keyframes"].copy()
    
    def get_keyframe(self, index):
        if 0 <= index < len(self.sequence_data["keyframes"]):
            return self.sequence_data["keyframes"][index].copy()
        return None
    
    def has_keyframes(self):
        return len(self.sequence_data["keyframes"]) > 0
    
    def get_keyframe_count(self):
        return len(self.sequence_data["keyframes"])
    
    def get_total_duration(self):
        if not self.sequence_data["keyframes"]:
            return 0.0
        
        last_keyframe = self.sequence_data["keyframes"][-1]
        return last_keyframe["absolute_time"] + last_keyframe["delay_to_next"]
    
    def get_sequence_components(self):
        components = set()
        for keyframe in self.sequence_data["keyframes"]:
            components.update(keyframe["component_positions"].keys())
        return sorted(list(components))
    
    #resolve component positions to servo commands
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
        
        for i, keyframe in enumerate(self.sequence_data["keyframes"]):
            for component_name, pulse_width in keyframe["component_positions"].items():
                if component_name not in self.state.servo_configurations:
                    issues.append(f"keyframe {i+1}: component '{component_name}' no longer exists")
                else:
                    config = self.state.servo_configurations[component_name]
                    if not (config["pulse_min"] <= pulse_width <= config["pulse_max"]):
                        issues.append(f"keyframe {i+1}: component '{component_name}' pulse {pulse_width} outside range")
        
        return issues
    
    #save sequence to file
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
            #ensure timing consistency
            self._recalculate_timing_from_dirty()
            
            save_data = {
                "metadata": self.sequence_data["metadata"].copy(),
                "keyframes": self.sequence_data["keyframes"].copy(),
                "servo_configurations": {}
            }
            
            #include servo configurations for reference
            for component_name, config in self.state.servo_configurations.items():
                save_data["servo_configurations"][component_name] = {
                    "index": config["index"],
                    "pulse_min": config["pulse_min"],
                    "pulse_max": config["pulse_max"]
                }
            
            with open(file_path, 'w') as file:
                json.dump(save_data, file, indent=2)
            
            return True, f"sequence saved to {file_path}"
            
        except Exception as e:
            return False, f"error saving sequence: {str(e)}"
    
    #load sequence from file
    def load_sequence(self, file_path=None):
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
            
            if "keyframes" not in loaded_data or "metadata" not in loaded_data:
                return False, "invalid sequence file format"
            
            #validate keyframes
            for i, keyframe in enumerate(loaded_data["keyframes"]):
                required_keys = ["absolute_time", "component_positions", "delay_to_next"]
                if not all(key in keyframe for key in required_keys):
                    return False, f"invalid keyframe {i} format"
            
            self.sequence_data["keyframes"] = loaded_data["keyframes"]
            self.sequence_data["metadata"].update(loaded_data["metadata"])
            
            #recalculate timing to ensure consistency
            self.dirty_timing_from_index = 0
            self._recalculate_timing_from_dirty()
            
            self._notify_gui(Events.SEQUENCE_LOADED)
            return True, f"sequence loaded from {file_path}"
            
        except Exception as e:
            return False, f"error loading sequence: {str(e)}"


class PlaybackManager:
    #manages sequence playback with simplified threading
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
    
    #start sequence playback
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
    
    #main playback thread
    def _playback_thread(self):
        try:
            self.is_playing_flag = True
            self._notify_gui("playback_started")
            
            keyframes = self.sequence_manager.get_keyframes()
            total_duration = self.sequence_manager.get_total_duration()
            
            if self.log_callback:
                components_used = self.sequence_manager.get_sequence_components()
                self.log_callback(f"starting playback: {len(components_used)} components, {total_duration:.1f}s duration")
            
            self._execute_sequence_playback(keyframes, total_duration)
            
            if self.log_callback:
                self.log_callback("sequence playback completed")
                
        except Exception as e:
            error_msg = f"playback error: {str(e)}"
            if self.log_callback:
                self.log_callback(error_msg)
            self._notify_gui("playback_error", error_msg)
            
        finally:
            self._reset_playback_state()
    
    #execute sequence with precise timing
    def _execute_sequence_playback(self, keyframes, total_duration):
        playback_start_time = time.time()
        current_keyframe_index = 0
        
        #move to first keyframe immediately
        if keyframes:
            commands, missing = self.sequence_manager.resolve_keyframe_to_commands(keyframes[0])
            self.serial_connection.send_batch_commands(commands, PLAYBACK_COMMAND_INTERVAL)
            if self.log_callback:
                self.log_callback(f"moved to initial position (step 1)")
        
        #main playback loop
        while current_keyframe_index < len(keyframes) and not self.stop_requested:
            current_time = time.time()
            elapsed_seconds = current_time - playback_start_time
            
            #find current keyframe based on elapsed time
            target_keyframe_index = self._find_current_keyframe(keyframes, elapsed_seconds)
            
            #advance to new keyframe if needed
            if target_keyframe_index > current_keyframe_index:
                for step_index in range(current_keyframe_index + 1, target_keyframe_index + 1):
                    if step_index < len(keyframes) and not self.stop_requested:
                        commands, missing = self.sequence_manager.resolve_keyframe_to_commands(keyframes[step_index])
                        self.serial_connection.send_batch_commands(commands, PLAYBACK_COMMAND_INTERVAL)
                        if self.log_callback:
                            self.log_callback(f"executing step {step_index + 1}")
                
                current_keyframe_index = target_keyframe_index
            
            #check completion
            if elapsed_seconds >= total_duration:
                break
            
            time.sleep(PLAYBACK_TIMING_PRECISION)
    
    #find current keyframe based on elapsed time
    def _find_current_keyframe(self, keyframes, elapsed_seconds):
        for i, keyframe in enumerate(keyframes):
            keyframe_end_time = keyframe["absolute_time"] + keyframe["delay_to_next"]
            if elapsed_seconds < keyframe_end_time:
                return i
        return len(keyframes) - 1
    
    #preview keyframe commands
    def preview_keyframe_commands(self, keyframe_index):
        keyframes = self.sequence_manager.get_keyframes()
        
        if not (0 <= keyframe_index < len(keyframes)):
            return [], ["invalid keyframe index"]
        
        keyframe = keyframes[keyframe_index]
        return self.sequence_manager.resolve_keyframe_to_commands(keyframe)


class TimelineVisualiser:
    #timeline visualisation for sequence
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
        self.canvas = tk.Canvas(
            self.frame,
            height=self.height,
            bg="white",
            relief="sunken",
            bd=1
        )
        self.canvas.pack(fill="x", padx=5, pady=2)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._draw_timeline()
    
    #handle canvas resize
    def _on_canvas_resize(self, event):
        self._draw_timeline()
    
    #update sequence data
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
        #background
        self.canvas.create_rectangle(0, 0, width, height, fill="#f8f8f8", outline="#cccccc")
        
        #main track
        track_y = height // 2
        track_height = 6
        self.canvas.create_rectangle(
            10, track_y - track_height//2, width - 10, track_y + track_height//2,
            fill="#e0e0e0", outline="#cccccc"
        )
        
        #duration indicator
        if self.max_duration > 0:
            duration_ratio = min(1.0, self.total_duration / self.max_duration)
            duration_width = int((width - 20) * duration_ratio)
            
            if duration_width > 0:
                self.canvas.create_rectangle(
                    10, track_y - track_height//2, 10 + duration_width, track_y + track_height//2,
                    fill="#4CAF50", outline=""
                )
    
    #draw time markers
    def _draw_time_markers(self, width, height):
        if self.max_duration <= 0:
            return
        
        marker_interval = 10.0 if self.max_duration > 60 else (5.0 if self.max_duration > 10 else 1.0)
        
        current_time = 0.0
        while current_time <= self.max_duration:
            x_pos = 10 + int((current_time / self.max_duration) * (width - 20))
            
            #marker line
            self.canvas.create_line(x_pos, height - 15, x_pos, height - 5, fill="#666666", width=1)
            
            #time label
            if current_time == 0 or current_time % (marker_interval * 2) == 0:
                time_text = f"{current_time:.0f}s"
                self.canvas.create_text(x_pos, height - 18, text=time_text, font=("Arial", 8), 
                                      fill="#666666", anchor="s")
            
            current_time += marker_interval
    
    #draw keyframe indicators
    def _draw_keyframes(self, width, height):
        if not self.keyframes or self.max_duration <= 0:
            return
        
        track_y = height // 2
        keyframe_height = 12
        timeline_width = width - 20
        min_keyframe_width = 4
        
        colours = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#607D8B", "#795548", "#009688"]
        
        for i, keyframe in enumerate(self.keyframes):
            start_time = keyframe["absolute_time"]
            duration = keyframe["delay_to_next"]
            
            start_ratio = start_time / self.max_duration
            duration_ratio = duration / self.max_duration
            
            start_x = 10 + int(start_ratio * timeline_width)
            duration_width = max(min_keyframe_width, int(duration_ratio * timeline_width))
            end_x = min(width - 10, start_x + duration_width)
            
            if end_x > start_x:
                keyframe_colour = colours[i % len(colours)]
                
                #keyframe block
                self.canvas.create_rectangle(
                    start_x, track_y - keyframe_height//2, 
                    end_x, track_y + keyframe_height//2,
                    fill=keyframe_colour, outline="#333333", width=1
                )
                
                #keyframe number
                if (end_x - start_x) >= 15:
                    label_x = start_x + (end_x - start_x) // 2
                    self.canvas.create_text(label_x, track_y, text=str(i + 1), font=("Arial", 8, "bold"), 
                                          fill="white", anchor="center")
    
    #start playback animation
    def start_playback_animation(self, duration):
        if duration <= 0:
            return
        
        self.is_animating = True
        self.animation_start_time = time.time()
        self.animation_duration = duration
        
        self.playback_line_id = self.canvas.create_line(
            0, 0, 0, self.canvas.winfo_height(),
            fill="#FF5722", width=2
        )
        
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
    #combined sequence recording interface with timeline
    def __init__(self, parent, sequence_manager, serial_connection, log_callback):
        self.frame = ttk.LabelFrame(parent, text="sequence recording")
        self.sequence_manager = sequence_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #gui variables
        self.delay_var = tk.DoubleVar(value=DEFAULT_KEYFRAME_DELAY)
        self.selected_step_index = None
        
        #playback manager
        self.playback_manager = PlaybackManager(
            sequence_manager=sequence_manager,
            serial_connection=serial_connection,
            log_callback=log_callback,
            gui_callback=self._on_playback_event
        )
        
        self._create_ui()
        
        #register direct callback for reliable updates
        self.sequence_manager.add_gui_callback(self._on_sequence_event)
    
    #create recording interface
    def _create_ui(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        #delay control
        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(fill="x", pady=5)
        
        ttk.Label(delay_frame, text="delay to next step (seconds):").pack(side="left", padx=5)
        
        self.delay_spinbox = ttk.Spinbox(
            delay_frame,
            from_=MIN_KEYFRAME_INTERVAL,
            to=MAX_KEYFRAME_DELAY,
            increment=0.1,
            textvariable=self.delay_var,
            width=8,
            format="%.1f"
        )
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
        
        #file operations
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill="x", pady=5)
        
        self.save_button = ttk.Button(file_frame, text="save sequence", command=self._save_sequence)
        self.save_button.pack(side="left", padx=5)
        
        self.load_button = ttk.Button(file_frame, text="load sequence", command=self._load_sequence)
        self.load_button.pack(side="left", padx=5)
        
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
        
        self.edit_delay_button = ttk.Button(step_frame, text="edit delay", command=self._edit_selected_delay)
        self.edit_delay_button.pack(side="left", padx=5)
        
        self.preview_button = ttk.Button(step_frame, text="preview", command=self._preview_selected_step)
        self.preview_button.pack(side="left", padx=5)
        
        #force initial update
        self._update_all_displays()
    
    #record new step
    def _record_step(self):
        delay = self.delay_var.get()
        success, message = self.sequence_manager.record_keyframe(delay)
        
        if success:
            components_used = len(self.sequence_manager.get_sequence_components())
            self.log_callback(f"recorded step {self.sequence_manager.get_keyframe_count()}: {components_used} components")
        else:
            messagebox.showerror("recording error", message)
            self.log_callback(f"recording failed: {message}")
    
    #play sequence
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
    
    #save sequence
    def _save_sequence(self):
        success, message = self.sequence_manager.save_sequence()
        
        if success:
            messagebox.showinfo("save successful", message)
            self.log_callback(message)
        elif "no file selected" not in message:
            messagebox.showerror("save error", message)
    
    #load sequence
    def _load_sequence(self):
        success, message = self.sequence_manager.load_sequence()
        
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
    
    #remove selected step
    def _remove_selected_step(self):
        if self.selected_step_index is None:
            return
        
        success, message = self.sequence_manager.remove_keyframe(self.selected_step_index)
        if success:
            self.log_callback(f"removed step {self.selected_step_index + 1}")
            self.selected_step_index = None
        else:
            messagebox.showerror("removal error", message)
    
    #edit delay for selected step
    def _edit_selected_delay(self):
        if self.selected_step_index is None:
            return
        
        keyframe = self.sequence_manager.get_keyframe(self.selected_step_index)
        if not keyframe:
            return
        
        #simple input dialog
        dialog = tk.Toplevel(self.frame)
        dialog.title(f"edit delay for step {self.selected_step_index + 1}")
        dialog.geometry("300x120")
        dialog.resizable(False, False)
        dialog.transient(self.frame)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="new delay (seconds):").pack(pady=5)
        
        delay_var = tk.DoubleVar(value=keyframe["delay_to_next"])
        delay_spinbox = ttk.Spinbox(frame, from_=MIN_KEYFRAME_INTERVAL, to=MAX_KEYFRAME_DELAY,
                                   increment=0.1, textvariable=delay_var, width=10, format="%.1f")
        delay_spinbox.pack(pady=5)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        def apply_delay():
            new_delay = delay_var.get()
            success, message = self.sequence_manager.update_keyframe_delay(self.selected_step_index, new_delay)
            
            if success:
                self.log_callback(f"updated delay for step {self.selected_step_index + 1} to {new_delay}s")
                dialog.destroy()
            else:
                messagebox.showerror("delay error", message)
        
        ttk.Button(button_frame, text="apply", command=apply_delay).pack(side="left", padx=5)
        ttk.Button(button_frame, text="cancel", command=dialog.destroy).pack(side="left", padx=5)
    
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
    
    #handle sequence events with forced refresh
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
    
    #force update of all displays
    def _update_all_displays(self):
        self._update_sequence_display()
        self._update_timeline()
        self._update_button_states()
    
    #update sequence display
    def _update_sequence_display(self):
        #clear existing items
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
    
    #update timeline
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
        self.edit_delay_button.config(state="normal" if has_selection and not is_playing else "disabled")
        self.preview_button.config(state="normal" if has_selection and not is_playing and is_connected else "disabled")
        
        self.delay_spinbox.config(state="normal" if not is_playing else "disabled")
    
    #widget visibility methods
    def show(self):
        self.frame.pack(fill="both", expand=True)
        #force refresh when shown
        self._update_all_displays()
    
    def hide(self):
        self.frame.pack_forget()
    
    def is_visible(self):
        return self.frame.winfo_manager() == "pack"
    
    #cleanup when widget is destroyed
    def __del__(self):
        if hasattr(self, 'sequence_manager'):
            self.sequence_manager.remove_gui_callback(self._on_sequence_event)
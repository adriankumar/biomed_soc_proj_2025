import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
import copy
from core.validation import (
    MAX_SEQUENCE_DURATION, MIN_KEYFRAME_INTERVAL, MAX_KEYFRAME_DELAY, 
    DEFAULT_KEYFRAME_DELAY, PLAYBACK_COMMAND_INTERVAL, PLAYBACK_TIMING_PRECISION,
    validate_timing, validate_component_positions, LEAD_IN_DURATION_MS, plan_lead_in
)
from core.event_system import publish, Events
from core.bezier_interpolation import (
    ensure_control_points, generate_playback_points, create_smooth_bezier_from_points,
    validate_bezier_keyframes, get_unique_timestamps, calculate_total_duration_ms,
    get_sequence_display_info, find_keyframes_at_timestamp, remove_keyframes_at_timestamp,
    edit_keyframe_delay_at_timestamp, create_command_timeline_from_bezier,
    get_keyframe_count_from_bezier, get_sequence_components_from_bezier, 
    validate_bezier_sequence_integrity, insert_keyframes_into_bezier_sequences, 
    get_servo_commands_at_timestamp, create_unified_playback_executor,
    execute_smooth_transition
)
from gui.motion_editor import MotionEditor

class SequenceManager:
    #manages sequence data using unified bezier format with preserved user delay intentions
    def __init__(self, state_manager):
        self.state = state_manager
        #unified bezier format as primary storage
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
        
        #recording state with preserved user intentions
        self.next_recording_time = 0.0
        self.pending_recording_delay = DEFAULT_KEYFRAME_DELAY  #preserves user delay input

        #exclude head components from recording/playback option
        self.exclude_head_4 = False
    
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
    
    #set delay for next recording without affecting existing keyframes
    def set_next_recording_delay(self, delay_seconds):
        if MIN_KEYFRAME_INTERVAL <= delay_seconds <= MAX_KEYFRAME_DELAY:
            self.pending_recording_delay = delay_seconds
            return True
        return False
    
    #get current pending delay for ui display
    def get_next_recording_delay(self):
        return self.pending_recording_delay
    
    #record keyframe with preserved user delay intentions
    def record_keyframe(self, delay_to_next):
        component_positions = self.state.get_current_component_positions()

        #optionally exclude first 4 head components from recording
        if self.exclude_head_4:
            for name in self._get_excluded_components():
                if name in component_positions:
                    component_positions.pop(name)
        
        #validate timing for recording consistency
        timing_result = validate_timing(self.next_recording_time, delay_to_next)
        if not timing_result.is_valid:
            return False, timing_result.error_message
        
        #validate component positions
        positions_result = validate_component_positions(component_positions, self.state.servo_configurations)
        if not positions_result.is_valid:
            return False, positions_result.error_message
        
        current_time_ms = round(self.next_recording_time * 1000)
        
        #insert keyframes using unified function
        insert_keyframes_into_bezier_sequences(self.sequence_data["servo_sequences"], current_time_ms, component_positions)
        
        #update recording time preserving user delay intentions
        self.pending_recording_delay = delay_to_next
        self.next_recording_time += delay_to_next
        
        #update metadata without destroying delay intentions
        self._update_metadata_preserve_delay()
        
        if self.sequence_data["metadata"]["creation_timestamp"] is None:
            self.sequence_data["metadata"]["creation_timestamp"] = time.time()
        
        self._notify_gui(Events.SEQUENCE_KEYFRAME_ADDED, self.get_keyframe_count() - 1)
        return True, "keyframe recorded successfully"

    #set exclude head components flag
    def set_exclude_head_4(self, enabled):
        self.exclude_head_4 = bool(enabled)

    #get excluded component names from head group (first 4)
    def _get_excluded_components(self):
        head_group = self.state.get_component_group("head")
        return head_group[:4] if isinstance(head_group, list) else []

    #get sequence data filtered for playback if exclusion is enabled
    def get_sequence_data_for_playback(self):
        data = copy.deepcopy(self.sequence_data["servo_sequences"])
        if not self.exclude_head_4:
            return data
        excluded = set(self._get_excluded_components())
        return {k: v for k, v in data.items() if k not in excluded}
    
    #update sequence metadata preserving user delay intentions
    def _update_metadata_preserve_delay(self):
        #use unified utility functions
        total_keyframes = get_keyframe_count_from_bezier(self.sequence_data["servo_sequences"])
        component_count = len(get_sequence_components_from_bezier(self.sequence_data["servo_sequences"]))
        
        self.sequence_data["metadata"]["total_keyframes"] = total_keyframes
        self.sequence_data["metadata"]["component_count"] = component_count
        
        #preserve user delay intentions instead of resetting to defaults
        #next_recording_time is already set correctly in record_keyframe()
    
    #remove keyframe by timestamp with unified bezier operations
    def remove_keyframe_by_timestamp(self, timestamp_ms):
        removed_components = remove_keyframes_at_timestamp(self.sequence_data["servo_sequences"], timestamp_ms)
        
        if not removed_components:
            return False, "no keyframes found at timestamp"
        
        #validate remaining sequences still have minimum keyframes
        invalid_components = []
        for component_name, component_sequence in self.sequence_data["servo_sequences"].items():
            if len(component_sequence) < 2:
                invalid_components.append(component_name)
        
        if invalid_components:
            return False, f"removal would leave insufficient keyframes in: {', '.join(invalid_components)}"
        
        self._update_metadata_preserve_delay()
        self._notify_gui(Events.SEQUENCE_KEYFRAME_REMOVED, timestamp_ms)
        return True, f"removed keyframes from {len(removed_components)} components"
    
    #edit keyframe delay using unified timestamp approach
    def edit_keyframe_delay_by_timestamp(self, timestamp_ms, new_delay_seconds):
        if not (MIN_KEYFRAME_INTERVAL <= new_delay_seconds <= MAX_KEYFRAME_DELAY):
            return False, f"delay must be between {MIN_KEYFRAME_INTERVAL} and {MAX_KEYFRAME_DELAY}"
        
        new_delay_ms = round(new_delay_seconds * 1000)
        success, message = edit_keyframe_delay_at_timestamp(self.sequence_data["servo_sequences"], timestamp_ms, new_delay_ms)
        
        if success:
            #validate total duration constraint
            new_total_duration = calculate_total_duration_ms(self.sequence_data["servo_sequences"]) / 1000.0
            if new_total_duration > MAX_SEQUENCE_DURATION:
                return False, f"total duration would exceed {MAX_SEQUENCE_DURATION} seconds"
            
            self._update_metadata_preserve_delay()
            self._notify_gui(Events.SEQUENCE_UPDATED)
        
        return success, message
    
    #clear entire sequence and reset recording state preserving delay
    def clear_sequence(self):
        self.sequence_data["servo_sequences"].clear()
        self.sequence_data["metadata"]["total_keyframes"] = 0
        self.sequence_data["metadata"]["creation_timestamp"] = None
        self.sequence_data["metadata"]["component_count"] = 0
        self.next_recording_time = 0.0
        #preserve pending delay across sequence clears
        
        self._notify_gui(Events.SEQUENCE_CLEARED)
        return True, "sequence cleared successfully"
    
    #get bezier sequence data directly for motion editor
    def get_sequence_data(self):
        return copy.deepcopy(self.sequence_data["servo_sequences"])
    
    #update sequence data from motion editor
    def update_sequence_data(self, updated_bezier_sequences):
        if not isinstance(updated_bezier_sequences, dict):
            return False, "invalid sequence data format"
        
        try:
            #validate using unified function
            issues = validate_bezier_sequence_integrity(updated_bezier_sequences, self.state.servo_configurations)
            if issues:
                return False, "; ".join(issues)
            
            #replace sequence data directly
            self.sequence_data["servo_sequences"] = copy.deepcopy(updated_bezier_sequences)
            self._update_metadata_preserve_delay()
            self._notify_gui(Events.SEQUENCE_UPDATED)
            return True, "sequence updated successfully"
            
        except Exception as e:
            return False, f"failed to update sequence: {str(e)}"
    
    #get display info for ui using unified function
    def get_display_keyframes(self):
        return get_sequence_display_info(self.sequence_data["servo_sequences"])
    
    #check if any sequences have keyframes
    def has_keyframes(self):
        return len(self.sequence_data["servo_sequences"]) > 0 and any(
            len(seq) > 0 for seq in self.sequence_data["servo_sequences"].values()
        )
    
    #get keyframe count using unified function
    def get_keyframe_count(self):
        return get_keyframe_count_from_bezier(self.sequence_data["servo_sequences"])
    
    #get total sequence duration using unified function
    def get_total_duration(self):
        return calculate_total_duration_ms(self.sequence_data["servo_sequences"]) / 1000.0
    
    #get sequence components using unified function
    def get_sequence_components(self):
        return get_sequence_components_from_bezier(self.sequence_data["servo_sequences"])
    
    #validate sequence integrity using unified function
    def validate_sequence_integrity(self):
        return validate_bezier_sequence_integrity(self.sequence_data["servo_sequences"], self.state.servo_configurations)
    
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
    
    #load sequence from bezier or legacy formats preserving delay
    def load_sequence(self, file_path=None, next_delay=None):
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
                
                #reset recording time to end of loaded sequence preserving user delay
                self.next_recording_time = self.get_total_duration()
                if next_delay is not None:
                    self.pending_recording_delay = next_delay
                
            #handle legacy time-based format (convert to bezier)
            elif "keyframes" in loaded_data and "metadata" in loaded_data:
                self._convert_legacy_format(loaded_data)
                if next_delay is not None:
                    self.pending_recording_delay = next_delay
                
            #handle legacy motion-centric format (direct use)
            elif "servo_sequences" in loaded_data:
                self.sequence_data["servo_sequences"] = copy.deepcopy(loaded_data["servo_sequences"])
                
                #ensure control points
                for component_name in self.sequence_data["servo_sequences"]:
                    ensure_control_points(self.sequence_data["servo_sequences"][component_name], use_smooth_defaults=True)
                
                self.next_recording_time = self.get_total_duration()
                if next_delay is not None:
                    self.pending_recording_delay = next_delay
                
            else:
                return False, "invalid sequence file format"
            
            self._update_metadata_preserve_delay()
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
            component_positions = keyframe["component_positions"]
            
            #use unified insertion function
            insert_keyframes_into_bezier_sequences(self.sequence_data["servo_sequences"], time_ms, component_positions)
        
        self.next_recording_time = self.get_total_duration()


class PlaybackManager:
    #manages sequence playback using unified bezier interpolation system
    def __init__(self, sequence_manager, serial_connection, gui_widget, log_callback):
        self.sequence_manager = sequence_manager
        self.serial_connection = serial_connection
        self.gui_widget = gui_widget  #gui context for reliable timing
        self.log_callback = log_callback
        
        #unified playback executor for precise timing
        self.playback_executor = create_unified_playback_executor(
            gui_widget, serial_connection, log_callback
        )
    
    #check playback status using unified system
    def is_playing(self):
        return self.playback_executor.playback_active
    
    #start sequence playback using unified executor
    def start_playback(self, completion_callback):
        if self.is_playing():
            return False, "playback already in progress"
        
        if not self.sequence_manager.has_keyframes():
            return False, "no sequence to play"
        
        if not self.serial_connection.is_connected:
            return False, "serial connection required"
        
        #get bezier sequences and servo configurations (apply exclusion if enabled)
        bezier_sequences = self.sequence_manager.get_sequence_data_for_playback()
        servo_configurations = {}
        
        #build servo configuration mapping
        for component_name in bezier_sequences.keys():
            config = self.sequence_manager.state.get_component_config(component_name)
            if config:
                servo_configurations[component_name] = {
                    'index': config['index'],
                    'pulse_min': config['pulse_min'],
                    'pulse_max': config['pulse_max']
                }
        
        #optional lead-in smoothing from last sent when enabled
        def _start():
            return self.playback_executor.execute_playback(
                bezier_sequences, servo_configurations, completion_callback
            )

        state = self.sequence_manager.state
        lead_targets = {}
        for comp, keyframes in bezier_sequences.items():
            if keyframes:
                lead_targets[comp] = int(keyframes[0]['angle'])

        apply, filtered, planned_ms = plan_lead_in(state, self.serial_connection, lead_targets, LEAD_IN_DURATION_MS)
        if apply and filtered:
            try:
                from core.bezier_interpolation import execute_smooth_transition
                execute_smooth_transition(self.gui_widget, self.serial_connection, state, filtered, planned_ms / 1000.0, log_callback=self.log_callback)
                self.gui_widget.after(planned_ms, lambda: _start())
                return True, "lead-in started"
            except Exception:
                pass
        return _start()
    
    #stop sequence playback using unified system
    def stop_playback(self):
        self.playback_executor.stop_playback()


class TimelineVisualiser:
    #timeline visualisation for sequence display using unified bezier data
    def __init__(self, parent, max_duration=120.0, height=40):
        self.frame = ttk.Frame(parent)
        self.max_duration = max_duration
        self.height = height
        
        self.display_keyframes = []  #converted for display only
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
    
    #update sequence data from bezier sequences for visualisation
    def update_bezier_sequence(self, bezier_sequences):
        #convert to display format for rendering only
        self.display_keyframes = get_sequence_display_info(bezier_sequences)
        self.total_duration = calculate_total_duration_ms(bezier_sequences) / 1000.0
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
        if not self.display_keyframes or self.max_duration <= 0:
            return
        
        track_y = height // 2
        keyframe_height = 12
        timeline_width = width - 20
        
        colours = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336", "#607D8B"]
        
        for i, keyframe in enumerate(self.display_keyframes):
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
    #sequence recording interface with unified bezier integration and preserved delay control
    def __init__(self, parent, sequence_manager, serial_connection, log_callback):
        self.frame = ttk.LabelFrame(parent, text="sequence recording")
        self.sequence_manager = sequence_manager
        self.serial_connection = serial_connection
        self.log_callback = log_callback
        
        #gui variables with delay synchronisation
        self.delay_var = tk.DoubleVar(value=sequence_manager.get_next_recording_delay())
        self.selected_step_index = None
        self.selected_timestamp_ms = None  #unified timestamp-based selection
        
        #playback manager using unified system with gui context
        self.playback_manager = PlaybackManager(
            sequence_manager=sequence_manager,
            serial_connection=serial_connection,
            gui_widget=self.frame,  #provides gui context for reliable timing
            log_callback=log_callback
        )
        
        #motion editor window reference
        self.motion_editor_window = None
        
        self._create_ui()
        
        #register gui callback for updates
        self.sequence_manager.add_gui_callback(self._on_sequence_event)
    
    #create recording interface with delay synchronisation
    def _create_ui(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        #delay control with live updates
        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(fill="x", pady=5)
        
        ttk.Label(delay_frame, text="delay to next step (seconds):").pack(side="left", padx=5)
        
        self.delay_spinbox = ttk.Spinbox(delay_frame, from_=MIN_KEYFRAME_INTERVAL, to=MAX_KEYFRAME_DELAY, increment=0.1, textvariable=self.delay_var, width=8, format="%.1f")
        self.delay_spinbox.pack(side="left", padx=5)
        
        #bind delay changes for immediate synchronisation
        self.delay_var.trace_add("write", self._on_delay_changed)
        
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

        #exclude head components toggle
        self.exclude_head_var = tk.BooleanVar(value=False)
        self.exclude_head_toggle = ttk.Checkbutton(
            control_frame,
            text="exclude head (first 4) from recording",
            variable=self.exclude_head_var,
            command=self._on_exclude_head_toggled
        )
        self.exclude_head_toggle.pack(side="left", padx=10)
        
        #file operations and motion editor
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill="x", pady=5)
        
        self.save_button = ttk.Button(file_frame, text="save sequence", command=self._save_sequence)
        self.save_button.pack(side="left", padx=5)
        
        self.load_button = ttk.Button(file_frame, text="load sequence", command=self._load_sequence)
        self.load_button.pack(side="left", padx=5)
        
        #motion editor integration using unified bezier format
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
        
        #step management with unified timestamp editing
        step_frame = ttk.Frame(main_frame)
        step_frame.pack(fill="x", pady=5)
        
        self.remove_button = ttk.Button(step_frame, text="remove selected", command=self._remove_selected_step)
        self.remove_button.pack(side="left", padx=5)
        
        self.preview_button = ttk.Button(step_frame, text="preview", command=self._preview_selected_step)
        self.preview_button.pack(side="left", padx=5)
        
        self.edit_delay_button = ttk.Button(step_frame, text="edit delay", command=self._on_edit_delay_button_clicked)
        self.edit_delay_button.pack(side="left", padx=5)
        
        #force initial update
        self._update_all_displays()

    #handle exclude head toggle
    def _on_exclude_head_toggled(self):
        try:
            enabled = bool(self.exclude_head_var.get())
            self.sequence_manager.set_exclude_head_4(enabled)
        except tk.TclError:
            pass
    
    #handle delay input changes with immediate synchronisation
    def _on_delay_changed(self, *args):
        try:
            new_delay = self.delay_var.get()
            self.sequence_manager.set_next_recording_delay(new_delay)
        except tk.TclError:
            pass
    
    #launch motion editor with unified bezier format
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
        
        #get bezier sequence data directly
        sequence_data = self.sequence_manager.get_sequence_data()
        
        #unified save callback for data persistence
        def save_callback(updated_data):
            success, message = self.sequence_manager.update_sequence_data(updated_data)
            if success:
                self._update_all_displays()
            return success, message
        
        #create motion editor with unified bezier format
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
    
    #record new step with preserved delay intentions
    def _record_step(self):
        delay = self.delay_var.get()
        success, message = self.sequence_manager.record_keyframe(delay)
        
        if success:
            components_used = len(self.sequence_manager.get_sequence_components())
            self.log_callback(f"recorded bezier step {self.sequence_manager.get_keyframe_count()}: {components_used} components, {delay}s delay")
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
        
        #update gui immediately before starting unified playback
        self._update_button_states_for_playing()

        #align timeline with optional lead-in
        sequences = self.sequence_manager.get_sequence_data_for_playback()
        lead_targets = {}
        for comp, keyframes in sequences.items():
            if keyframes:
                first = keyframes[0]
                lead_targets[comp] = int(first['angle']) if isinstance(first, dict) else int(first[1])

        apply, filtered, planned_ms = plan_lead_in(self.sequence_manager.state, self.serial_connection, lead_targets, LEAD_IN_DURATION_MS)
        total_duration = self.sequence_manager.get_total_duration()
        if apply and filtered:
            self.frame.after(planned_ms, lambda: self.timeline_visualiser.start_playback_animation(total_duration))
        else:
            self.timeline_visualiser.start_playback_animation(total_duration)

        #start unified playback
        success, message = self.playback_manager.start_playback(self._on_playback_complete)
        if not success:
            #reset gui if playback failed to start
            self._update_button_states()
            self.timeline_visualiser.stop_playback_animation()
            messagebox.showerror("playback error", message)
    
    #stop playback using unified system
    def _stop_playback(self):
        self.playback_manager.stop_playback()
    
    #handle playback completion with thread-safe gui updates
    def _on_playback_complete(self, success, error_msg=None):
        self.frame.after(0, self._update_button_states)
        self.frame.after(0, self.timeline_visualiser.stop_playback_animation)
        
        if not success and error_msg:
            self.frame.after(0, lambda: messagebox.showerror("playback error", error_msg))
    
    #set button states for active playback mode
    def _update_button_states_for_playing(self):
        self.record_button.config(state="disabled")
        self.play_button.config(state="disabled") 
        self.stop_button.config(state="normal")
        self.clear_button.config(state="disabled")
        self.save_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.remove_button.config(state="disabled")
        self.preview_button.config(state="disabled")
        self.edit_delay_button.config(state="disabled")
        self.delay_spinbox.config(state="disabled")
        self.motion_editor_button.config(state="disabled")

    #clear sequence preserving delay settings
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
    
    #load sequence with unified bezier support preserving delay
    def _load_sequence(self):
        current_delay = self.delay_var.get()
        success, message = self.sequence_manager.load_sequence(next_delay=current_delay)
        
        if success:
            messagebox.showinfo("load successful", message)
            self.log_callback(message)
        elif "no file selected" not in message:
            messagebox.showerror("load error", message)
    
    #handle step selection using unified timestamp approach
    def _on_step_selected(self, event):
        selection = self.step_tree.selection()
        if selection:
            self.selected_step_index = self.step_tree.index(selection[0])
            
            #extract timestamp for unified operations
            display_keyframes = self.sequence_manager.get_display_keyframes()
            if self.selected_step_index < len(display_keyframes):
                self.selected_timestamp_ms = display_keyframes[self.selected_step_index]["timestamp_ms"]
            else:
                self.selected_timestamp_ms = None
        else:
            self.selected_step_index = None
            self.selected_timestamp_ms = None
        
        self._update_button_states()
    
    #remove selected step using unified timestamp operations
    def _remove_selected_step(self):
        if self.selected_timestamp_ms is None:
            return
        
        #use unified timestamp removal
        success, message = self.sequence_manager.remove_keyframe_by_timestamp(self.selected_timestamp_ms)
        
        if success:
            self.log_callback(message)
            self.selected_step_index = None
            self.selected_timestamp_ms = None
            self._update_all_displays()
        else:
            messagebox.showwarning("removal blocked", message)
            self.log_callback(f"removal failed: {message}")
    
    #preview selected step using unified timestamp operations
    def _preview_selected_step(self):
        if self.selected_timestamp_ms is None:
            return
        
        if not self.serial_connection.is_connected:
            messagebox.showwarning("not connected", "serial connection required for preview")
            return
        
        #build targets map at selected timestamp for smooth transition
        bezier_sequences = self.sequence_manager.get_sequence_data()
        found = find_keyframes_at_timestamp(bezier_sequences, self.selected_timestamp_ms)
        targets = {comp: info['keyframe']['angle'] for comp, info in found.items()}
        if not targets:
            messagebox.showwarning("preview unavailable", "no keyframes found at selected time")
            return

        success, msg = execute_smooth_transition(self.frame, self.serial_connection, self.sequence_manager.state, targets, 1.0, self.log_callback)
        if success:
            self.log_callback(f"previewed step {self.selected_step_index + 1} with smooth transition")
    
    #handle sequence events with delay synchronisation
    def _on_sequence_event(self, event_type, *args):
        self._update_all_displays()
        #sync delay display with sequence manager state
        current_delay = self.sequence_manager.get_next_recording_delay()
        if abs(self.delay_var.get() - current_delay) > 0.01:
            self.delay_var.set(current_delay)
    
    #show modal dialog for editing keyframe delay with unified timestamp approach
    def _show_delay_edit_dialog(self, current_delay):
        dialog = tk.Toplevel(self.frame)
        dialog.title("edit keyframe delay")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        
        #centre dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (300 // 2)
        y = (dialog.winfo_screenheight() // 2) - (150 // 2)
        dialog.geometry(f"300x150+{x}+{y}")
        
        #make modal
        dialog.transient(self.frame)
        dialog.grab_set()
        
        result = [None]  #mutable container for result
        
        main_frame = ttk.Frame(dialog)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        ttk.Label(main_frame, text="delay to next step (seconds):").pack(pady=(0, 10))
        
        delay_var = tk.DoubleVar(value=current_delay)
        delay_entry = ttk.Entry(main_frame, textvariable=delay_var, width=10)
        delay_entry.pack(pady=(0, 20))
        delay_entry.select_range(0, tk.END)
        delay_entry.focus()
        
        def on_ok():
            try:
                new_delay = delay_var.get()
                if new_delay > 0:
                    result[0] = new_delay
                    dialog.destroy()
            except tk.TclError:
                pass
        
        def on_cancel():
            dialog.destroy()
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack()
        
        ttk.Button(button_frame, text="ok", command=on_ok).pack(side="left", padx=5)
        ttk.Button(button_frame, text="cancel", command=on_cancel).pack(side="left", padx=5)
        
        delay_entry.bind("<Return>", lambda e: on_ok())
        delay_entry.bind("<Escape>", lambda e: on_cancel())
        
        dialog.wait_window()
        return result[0]

    #handle edit delay button with unified timestamp operations
    def _on_edit_delay_button_clicked(self):
        if self.selected_timestamp_ms is None:
            return
        
        #get current delay from display info
        display_keyframes = self.sequence_manager.get_display_keyframes()
        if self.selected_step_index >= len(display_keyframes) - 1:
            return  #cannot edit last keyframe delay
        
        current_delay = display_keyframes[self.selected_step_index]["delay_to_next"]
        new_delay = self._show_delay_edit_dialog(current_delay)
        
        if new_delay is not None:
            #use unified timestamp-based delay editing
            success, message = self.sequence_manager.edit_keyframe_delay_by_timestamp(self.selected_timestamp_ms, new_delay)
            if success:
                self.log_callback(f"updated keyframe {self.selected_step_index + 1} delay to {new_delay}s")
                self._update_all_displays()
            else:
                messagebox.showerror("edit error", message)
    
    #update all displays
    def _update_all_displays(self):
        self._update_sequence_display()
        self._update_timeline()
        self._update_button_states()
    
    #update sequence display using unified bezier format
    def _update_sequence_display(self):
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
        
        #use unified display function instead of conversion
        display_keyframes = self.sequence_manager.get_display_keyframes()
        
        for i, keyframe in enumerate(display_keyframes):
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
    
    #update timeline visualiser with unified bezier format
    def _update_timeline(self):
        bezier_sequences = self.sequence_manager.get_sequence_data()
        self.timeline_visualiser.update_bezier_sequence(bezier_sequences)
    
    #update button states
    def _update_button_states(self):
        has_keyframes = self.sequence_manager.has_keyframes()
        is_playing = self.playback_manager.is_playing()
        has_selection = self.selected_timestamp_ms is not None
        is_connected = self.serial_connection.is_connected
        
        #calculate if selected keyframe can have delay edited
        can_edit_delay = False
        if has_selection and has_keyframes and not is_playing:
            display_keyframes = self.sequence_manager.get_display_keyframes()
            can_edit_delay = self.selected_step_index < len(display_keyframes) - 1
        
        self.record_button.config(state="normal" if not is_playing else "disabled")
        self.play_button.config(state="normal" if has_keyframes and not is_playing and is_connected else "disabled")
        self.stop_button.config(state="normal" if is_playing else "disabled")
        self.clear_button.config(state="normal" if has_keyframes and not is_playing else "disabled")
        
        self.save_button.config(state="normal" if has_keyframes else "disabled")
        self.load_button.config(state="normal" if not is_playing else "disabled")
        
        self.remove_button.config(state="normal" if has_selection and not is_playing else "disabled")
        self.preview_button.config(state="normal" if has_selection and not is_playing and is_connected else "disabled")
        self.edit_delay_button.config(state="normal" if can_edit_delay else "disabled")
        
        self.delay_spinbox.config(state="normal" if not is_playing else "disabled")

        #motion editor button
        self.motion_editor_button.config(state="normal" if has_keyframes and not is_playing else "disabled")

        #exclude head toggle is only changeable when sequence is empty
        self.exclude_head_toggle.config(state="normal" if (not has_keyframes and not is_playing) else "disabled")
    
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

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
import copy
from servo_motion_editor import ServoMotionEditor

class SequenceRecording:
    def __init__(self, parent, num_servos, get_servo_angles_callback=None, send_command_callback=None):
        # Create main frame
        self.frame = ttk.LabelFrame(parent, text="Sequence Recording")
        
        # Store parameters
        self.num_servos = num_servos
        self.get_servo_angles = get_servo_angles_callback
        self.send_command = send_command_callback
        
        # Sequence data - modified structure for Bezier curve support
        # List of steps, each step has:
        # - time: absolute time in ms from start
        # - delay: time until next step
        # - servos: list of servo states at this step, each with id, angle, cp_in, cp_out
        self.sequence = []
        
        self.is_playing = False
        self.play_thread = None
        
        # Delay between steps (milliseconds)
        self.delay_var = tk.IntVar(value=500)
        
        # Create ui components
        self._create_ui()
        
    # -----------------------------------------------------------------------
    # UI creation
    # -----------------------------------------------------------------------
    def _create_ui(self):
        # Delay setting
        delay_frame = ttk.Frame(self.frame)
        delay_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(delay_frame, text="Delay Until Next Step (ms):").pack(side="left", padx=5)
        
        self.delay_spinbox = ttk.Spinbox(
            delay_frame,
            from_=50,
            to=5000,
            increment=50,
            textvariable=self.delay_var,
            width=5
        )
        self.delay_spinbox.pack(side="left", padx=5)
        
        # Control buttons
        buttons_frame = ttk.Frame(self.frame)
        buttons_frame.pack(fill="x", padx=5, pady=5)
        
        self.record_button = ttk.Button(
            buttons_frame,
            text="Record Step",
            command=self.record_step
        )
        self.record_button.pack(side="left", padx=5)
        
        self.play_button = ttk.Button(
            buttons_frame,
            text="Play Sequence",
            command=self.play_sequence,
            state="disabled"
        )
        self.play_button.pack(side="left", padx=5)
        
        self.stop_button = ttk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_sequence,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)
        
        self.clear_button = ttk.Button(
            buttons_frame,
            text="Clear Sequence",
            command=self.clear_sequence,
            state="disabled"
        )
        self.clear_button.pack(side="left", padx=5)
        
        # Save/load buttons
        file_frame = ttk.Frame(self.frame)
        file_frame.pack(fill="x", padx=5, pady=5)
        
        self.save_button = ttk.Button(
            file_frame,
            text="Save Sequence",
            command=self.save_sequence
        )
        self.save_button.pack(side="left", padx=5)
        
        self.load_button = ttk.Button(
            file_frame,
            text="Load Sequence",
            command=self.load_sequence
        )
        self.load_button.pack(side="left", padx=5)
        
        # Sequence display
        display_frame = ttk.LabelFrame(self.frame, text="Recorded Steps")
        display_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Treeview for steps
        columns = ("Step", "Servos", "StartTime")
        self.step_tree = ttk.Treeview(
            display_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )
        
        # Column headings
        self.step_tree.heading("Step", text="Step")
        self.step_tree.heading("Servos", text="Servo Positions")
        self.step_tree.heading("StartTime", text="Start Time (ms)")
        
        # Column widths
        self.step_tree.column("Step", width=50, anchor="center")
        self.step_tree.column("Servos", width=350, anchor="w")
        self.step_tree.column("StartTime", width=100, anchor="center")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(display_frame, orient="vertical", command=self.step_tree.yview)
        self.step_tree.configure(yscrollcommand=scrollbar.set)
        
        self.step_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons under treeview
        tree_buttons_frame = ttk.Frame(self.frame)
        tree_buttons_frame.pack(fill="x", padx=5, pady=5)
        
        self.remove_button = ttk.Button(
            tree_buttons_frame,
            text="Remove Selected Step",
            command=self.remove_step
        )
        self.remove_button.pack(side="left", padx=5)
        
        self.edit_motion_button = ttk.Button(
            tree_buttons_frame,
            text="Edit Motion Graph",
            command=self.edit_motion_graph,
            state="disabled"
        )
        self.edit_motion_button.pack(side="left", padx=5)
    
    # -----------------------------------------------------------------------
    # Sequence control methods
    # -----------------------------------------------------------------------
    def record_step(self):
        # Check if we can get servo angles
        if not self.get_servo_angles:
            messagebox.showerror("Error", "Cannot get servo angles")
            return
        
        # Get current servo positions
        servo_positions = self.get_servo_angles()
        
        if not servo_positions or len(servo_positions) != self.num_servos:
            messagebox.showerror("Error", "Invalid servo positions")
            return
        
        # Calculate start time for this step
        start_time = 0
        if self.sequence:
            # Time is previous step's time + previous step's delay
            prev_step = self.sequence[-1]
            start_time = prev_step['time'] + prev_step['delay']
        
        # Create step data with the new structure
        step = {
            'time': start_time,  # Absolute time from sequence start
            'delay': self.delay_var.get(),  # Delay until next step
            'servos': []
        }
        
        # Add servo data with control points initialized to None
        for servo in servo_positions:
            step['servos'].append({
                'id': servo['id'],
                'position': servo['position'],
                'angle': servo['position'],  # Duplicate for compatibility
                'cp_in': None,  # Will be set by motion editor
                'cp_out': None  # Will be set by motion editor
            })
        
        # Add to sequence
        self.sequence.append(step)
        
        # Update display
        self._update_sequence_display()
        
        # Update button states
        self._update_buttons()
        
        # Enable delay spinbox now that we have at least one step
        self.delay_spinbox.config(state="normal")
    
    def remove_step(self):
        selected = self.step_tree.selection()
        
        if not selected:
            messagebox.showinfo("Info", "No step selected")
            return
        
        # Get index
        item = selected[0]
        index = self.step_tree.index(item)
        
        # Remove from sequence
        if 0 <= index < len(self.sequence):
            self.sequence.pop(index)
            
            # Update times for all subsequent steps
            self._recalculate_step_times(index)
            
            # Update display
            self._update_sequence_display()
            
            # Update button states
            self._update_buttons()
    
    def _recalculate_step_times(self, start_index=0):
        """Recalculate all step times starting from the given index."""
        if not self.sequence or start_index >= len(self.sequence):
            return
            
        # First step always starts at time 0
        if start_index == 0 and self.sequence:
            self.sequence[0]['time'] = 0
            start_index = 1
        
        # Calculate times for subsequent steps
        for i in range(start_index, len(self.sequence)):
            prev_step = self.sequence[i-1]
            self.sequence[i]['time'] = prev_step['time'] + prev_step['delay']
    
    def play_sequence(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to play")
            return
        
        # Check if we can send commands
        if not self.send_command:
            messagebox.showerror("Error", "Cannot send commands")
            return
        
        # Update ui state
        self.is_playing = True
        self._update_buttons()
        
        # Start sequence playback thread
        self.play_thread = threading.Thread(target=self._playback_thread)
        self.play_thread.daemon = True
        self.play_thread.start()


    def _playback_thread(self):
        try:
            # First, convert the sequence to the format needed by the ESP32
            servo_sequences = self._convert_to_bezier_format()
            
            # Stop any existing playback
            self.send_command("STOP")
            time.sleep(0.2)  # Increased delay
            
            # Clear all sequences
            self.send_command("CLEAR_ALL")
            time.sleep(0.2)  # Increased delay
            
            # Load sequences for each servo
            for servo_id, keyframes in servo_sequences.items():
                if len(keyframes) >= 2:  # Need at least 2 keyframes
                    # Format the keyframe string for this servo with integer values
                    keyframe_string = self._format_keyframes_for_serial(keyframes)
                    
                    # Send the command
                    self.send_command(f"LOAD_SEQ:{servo_id}:{keyframe_string}")
                    time.sleep(0.15)  # Increased delay
            
            # Highlight first step initially
            if self.step_tree.get_children():
                self.step_tree.selection_set(self.step_tree.get_children()[0])
                self.step_tree.see(self.step_tree.get_children()[0])
            
            # Calculate total duration of the sequence
            if not self.sequence:
                return
                
            total_duration = self.sequence[-1]['time'] + self.sequence[-1]['delay']
            
            # Add extra delay before starting playback
            time.sleep(0.2)
            
            # Start playback of all loaded sequences
            self.send_command("PLAY_LOADED")
            
            # Record the exact start time of playback
            start_time = time.time()
            
            # Schedule UI updates on the main thread
            self.frame.after(0, lambda: self._update_playback_ui(start_time, total_duration))
            
        except Exception as e:
            print(f"Error during playback: {str(e)}")
            messagebox.showerror("Playback Error", str(e))
            self.is_playing = False
            self.frame.after(0, self._update_buttons)

    def _update_playback_ui(self, start_time, total_duration):
        """Update the UI during playback using real elapsed time."""
        if not self.is_playing:
            return
            
        # Calculate actual elapsed time in milliseconds
        current_time = time.time()
        elapsed_ms = int((current_time - start_time) * 1000)
        
        # Check if playback is complete
        if elapsed_ms >= total_duration:
            self.is_playing = False
            self.frame.after(0, self._update_buttons)
            return
        
        # Find the current step based on elapsed time
        step_index = 0
        for i, step in enumerate(self.sequence):
            if step['time'] > elapsed_ms:
                break
            step_index = i
        
        # Highlight current step in the UI
        children = self.step_tree.get_children()
        if 0 <= step_index < len(children):
            self.step_tree.selection_set(children[step_index])
            self.step_tree.see(children[step_index])
        
        # Schedule the next update in 30ms for smoother display
        self.frame.after(30, lambda: self._update_playback_ui(start_time, total_duration))
    # def _playback_thread(self):
    #     try:
    #         # First, convert the sequence to the format needed by the ESP32
    #         servo_sequences = self._convert_to_bezier_format()
            
    #         # Stop any existing playback
    #         self.send_command("STOP")
    #         time.sleep(0.2)
            
    #         # Clear all sequences
    #         self.send_command("CLEAR_ALL")
    #         time.sleep(0.2)
            
    #         # Load sequences for each servo
    #         for servo_id, keyframes in servo_sequences.items():
    #             if len(keyframes) >= 2:  # Need at least 2 keyframes
    #                 # Format the keyframe string for this servo
    #                 keyframe_string = self._format_keyframes_for_serial(keyframes)
                    
    #                 # Send the command
    #                 self.send_command(f"LOAD_SEQ:{servo_id}:{keyframe_string}")
    #                 time.sleep(0.15)  # Small delay between commands
            
    #         # Highlight first step
    #         if self.step_tree.get_children():
    #             self.step_tree.selection_set(self.step_tree.get_children()[0])
    #             self.step_tree.see(self.step_tree.get_children()[0])
            
    #         # Start playback of all loaded sequences
    #         time.sleep(0.3)
    #         self.send_command("PLAY_LOADED")
            
    #         # Update UI as playback progresses
    #         if self.sequence:
    #             # Calculate total duration
    #             total_duration = self.sequence[-1]['time'] + self.sequence[-1]['delay']
                
    #             # Wait for playback to complete or be stopped
    #             elapsed = 0
    #             step_index = 0
                
    #             while self.is_playing and elapsed < total_duration:
    #                 # Find current step based on elapsed time
    #                 while (step_index < len(self.sequence) - 1 and 
    #                        elapsed >= self.sequence[step_index + 1]['time']):
    #                     step_index += 1
                    
    #                 # Highlight current step
    #                 children = self.step_tree.get_children()
    #                 if 0 <= step_index < len(children):
    #                     self.step_tree.selection_set(children[step_index])
    #                     self.step_tree.see(children[step_index])
                    
    #                 # Wait a bit
    #                 time.sleep(0.1)
    #                 elapsed += 50  # 50ms increments
                
    #     except Exception as e:
    #         print(f"Error during playback: {str(e)}")
    #         messagebox.showerror("Playback Error", str(e))
            
    #     finally:
    #         # Reset play state
    #         self.is_playing = False
            
    #         # Update ui from main thread
    #         self.frame.after(0, self._update_buttons)
    
    def _convert_to_bezier_format(self):
        """Convert sequence data to format needed for Bezier curves.
        
        Returns:
            dict: {servo_id: [list of keyframes]}
        """
        result = {}
        
        for step in self.sequence:
            step_time = step['time']
            
            for servo_data in step['servos']:
                servo_id = servo_data['id']
                
                if servo_id not in result:
                    result[servo_id] = []
                
                # Create keyframe
                keyframe = {
                    'time': step_time,
                    'angle': servo_data.get('position', servo_data.get('angle', 90)),
                    'cp_in': copy.deepcopy(servo_data.get('cp_in')),
                    'cp_out': copy.deepcopy(servo_data.get('cp_out'))
                }
                
                result[servo_id].append(keyframe)
        
        # Ensure each servo has valid control points
        for servo_id, keyframes in result.items():
            # Sort by time (should already be sorted, but make sure)
            keyframes.sort(key=lambda kf: kf['time'])
            
            # Set default control points if needed
            self._ensure_default_control_points(keyframes)
        
        return result
    
    def _ensure_default_control_points(self, keyframes):
        """Ensure all keyframes have valid control points."""
        num_keyframes = len(keyframes)
        
        for i, kf in enumerate(keyframes):
            default_dt_factor = 0.33
            
            # Incoming control point (not for first keyframe)
            if i > 0:
                if 'cp_in' not in kf or kf['cp_in'] is None:
                    prev_kf = keyframes[i-1]
                    time_diff = kf['time'] - prev_kf['time']
                    dt = max(1, time_diff) * -default_dt_factor
                    kf['cp_in'] = {'dt': dt, 'da': 0.0}
            else:
                # First keyframe has no incoming control point
                kf['cp_in'] = None
            
            # Outgoing control point (not for last keyframe)
            if i < num_keyframes - 1:
                if 'cp_out' not in kf or kf['cp_out'] is None:
                    next_kf = keyframes[i+1]
                    time_diff = next_kf['time'] - kf['time']
                    dt = max(1, time_diff) * default_dt_factor
                    kf['cp_out'] = {'dt': dt, 'da': 0.0}
            else:
                # Last keyframe has no outgoing control point
                kf['cp_out'] = None
    
    def _format_keyframes_for_serial(self, keyframes):
        """Format keyframes for LOAD_SEQ command."""
        parts = []
        for kf in keyframes:
            time_val = int(round(kf['time']))
            angle_val = int(round(kf['angle']))
            cp_in = kf.get('cp_in')
            cp_out = kf.get('cp_out')

            in_dt_str = str(int(round(cp_in['dt']))) if cp_in else ""
            in_da_str = str(int(round(cp_in['da']))) if cp_in else ""
            out_dt_str = str(int(round(cp_out['dt']))) if cp_out else ""
            out_da_str = str(int(round(cp_out['da']))) if cp_out else ""

            parts.append(f"{time_val},{angle_val},{in_dt_str},{in_da_str},{out_dt_str},{out_da_str}")
        return ";".join(parts)
    
    def stop_sequence(self):
        # Stop playback
        self.is_playing = False
        
        # Send stop command
        if self.send_command:
            self.send_command("STOP")
        
        # Update buttons
        self._update_buttons()
    
    def clear_sequence(self):
        if not self.sequence:
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the sequence?"):
            self.sequence = []
            self._update_sequence_display()
            self._update_buttons()
            
            # Disable delay spinbox when no sequence
            self.delay_spinbox.config(state="disabled")
    
    # -----------------------------------------------------------------------
    # File operations
    # -----------------------------------------------------------------------
    def save_sequence(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to save")
            return
            
        # Get file path
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as file:
                json.dump(self.sequence, file, indent=2)
                
            messagebox.showinfo("Success", f"Sequence saved to {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error saving sequence: {str(e)}")
    
    def load_sequence(self):
        # Get file path
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as file:
                loaded_sequence = json.load(file)
                
            # Validate sequence
            if not isinstance(loaded_sequence, list):
                raise ValueError("Invalid sequence format")
                
            for step in loaded_sequence:
                if not isinstance(step, dict) or "servos" not in step:
                    raise ValueError("Invalid step format")
                
                # Ensure time and delay exist
                if "time" not in step:
                    step["time"] = 0
                if "delay" not in step:
                    step["delay"] = 500
                    
            # Update sequence
            self.sequence = loaded_sequence
            self._update_sequence_display()
            self._update_buttons()
            
            # Enable delay spinbox if sequence not empty
            if self.sequence:
                self.delay_spinbox.config(state="normal")
            else:
                self.delay_spinbox.config(state="disabled")
                
            messagebox.showinfo("Success", f"Sequence loaded from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading sequence: {str(e)}")
    
    def edit_motion_graph(self):
        if not self.sequence:
            messagebox.showinfo("Info", "No sequence to edit")
            return
        
        # Convert sequence to format needed by motion editor
        editor_data = self._convert_to_bezier_format()
        
        # Create motion editor
        editor = ServoMotionEditor(
            self.frame,
            editor_data,
            send_command_callback=self.send_command,
            sequence_update_callback=self._update_sequence_from_editor
        )
        
        editor.show()
    
    def _update_sequence_from_editor(self, updated_sequence):
        """Update sequence with data from the motion editor."""
        if updated_sequence is None:
            return
            
        # Update the sequence
        self.sequence = updated_sequence
        
        # Update display
        self._update_sequence_display()
        
        # Update button states
        self._update_buttons()
    
    # -----------------------------------------------------------------------
    # UI update helpers
    # -----------------------------------------------------------------------
    def _update_sequence_display(self):
        # Clear current display
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
            
        # Add sequence steps
        for i, step in enumerate(self.sequence):
            # Format servo positions text
            positions_text = ", ".join([
                f"Servo {servo['id']}: {servo.get('position', servo.get('angle', 90))}°" 
                for servo in step["servos"]
            ])
            
            # Add to treeview
            self.step_tree.insert(
                "",
                "end",
                values=(i+1, positions_text, int(round(step["time"])))
            )
    
    def _update_buttons(self):
        has_sequence = bool(self.sequence)
        
        # Enable/disable buttons based on state
        self.record_button.config(state="disabled" if self.is_playing else "normal")
        self.play_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.stop_button.config(state="normal" if self.is_playing else "disabled")
        self.clear_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.edit_motion_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
        self.remove_button.config(state="disabled" if self.is_playing or not has_sequence else "normal")
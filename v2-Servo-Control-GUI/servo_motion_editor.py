import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import Slider, TextBox, Button
from matplotlib.lines import Line2D
import copy
import logging
import time

class ServoMotionEditor:
    def __init__(self, parent, sequence=None, send_command_callback=None, sequence_update_callback=None):
        """Initialise the motion editor for Bezier curve-based servo control.
        
        Args:
            parent: Tkinter parent widget
            sequence: Sequence data to edit (will be modified through sequence_update_callback)
            send_command_callback: Function to send commands to the ESP32
            sequence_update_callback: Function to update the original sequence after editing
        """
        self.parent = parent
        self.original_sequence = sequence  # Reference to original sequence data
        self.sequence_update_callback = sequence_update_callback
        self.send_command = send_command_callback
        
        # Create a deep copy of the sequence data for editing
        self.all_sequences = self._convert_to_editor_format(sequence) if sequence else {}
        
        # Set defaults if we received empty data
        if not self.all_sequences:
            # Create a default sequence with one servo
            self.all_sequences = {
                0: [
                    {'time': 0, 'angle': 90, 'cp_in': None, 'cp_out': None},
                    {'time': 1000, 'angle': 120, 'cp_in': None, 'cp_out': None}
                ]
            }
        
        # Current servo being edited
        self.servo_ids = sorted(list(self.all_sequences.keys()))
        self.current_servo_id = self.servo_ids[0] if self.servo_ids else 0
        
        # Ensure default control points for all sequences
        for servo_id in self.servo_ids:
            self.ensure_default_control_points(servo_id)
        
        # Editor state variables
        self.scroll_window = 2000  # Width of visible x-axis window in ms
        self.selected_kf_index = None
        self.dragging_element = None
        self.save_status = "Not Saved"
        
        # Playback state variables
        self.playback_active = False
        self.playback_duration = 0
        self.playback_start_time = 0
        
        # Create the editor window as a Toplevel
        self._create_editor_window()
        
    def _convert_to_editor_format(self, sequence):
        """Convert from sequence_recorder format to editor format.
        
        The editor uses a dictionary where keys are servo IDs and values are
        lists of keyframes, where each keyframe is a dictionary with time, angle,
        cp_in, and cp_out.
        """
        if not sequence:
            return {}
            
        result = {}
        
        # Check if the sequence is already in the right format
        if isinstance(sequence, dict) and all(isinstance(sequence[k], list) for k in sequence):
            # Already in the correct format, just deep copy
            return copy.deepcopy(sequence)
        
        # Otherwise, assume it's in the sequence_recorder format:
        # List of steps, each step has time, delay, and list of servos
        for step_idx, step in enumerate(sequence):
            time_ms = step['time']
            
            for servo_data in step['servos']:
                servo_id = servo_data['id']
                
                if servo_id not in result:
                    result[servo_id] = []
                
                keyframe = {
                    'time': time_ms,
                    'angle': servo_data['position'] if 'position' in servo_data else servo_data['angle'],
                    'cp_in': copy.deepcopy(servo_data.get('cp_in')),
                    'cp_out': copy.deepcopy(servo_data.get('cp_out'))
                }
                
                result[servo_id].append(keyframe)
                
        return result
        
    def _convert_to_recorder_format(self):
        """Convert from editor format back to sequence_recorder format."""
        if not self.all_sequences:
            return []
            
        # Get all unique times across all servo sequences
        all_times = set()
        for servo_id, keyframes in self.all_sequences.items():
            for kf in keyframes:
                all_times.add(kf['time'])
        
        sorted_times = sorted(list(all_times))
        
        # Create steps at each unique time
        result = []
        for idx, time_ms in enumerate(sorted_times):
            step = {
                'time': time_ms,
                'delay': sorted_times[idx+1] - time_ms if idx < len(sorted_times) - 1 else 500,
                'servos': []
            }
            
            # For each servo, find the keyframe at this time if it exists
            for servo_id in self.all_sequences:
                # Find keyframe at this time
                matching_kf = None
                for kf in self.all_sequences[servo_id]:
                    if kf['time'] == time_ms:
                        matching_kf = kf
                        break
                
                if matching_kf:
                    # Add this servo's data to the step
                    servo_data = {
                        'id': servo_id,
                        'position': matching_kf['angle'],
                        'angle': matching_kf['angle'],
                        'cp_in': copy.deepcopy(matching_kf.get('cp_in')),
                        'cp_out': copy.deepcopy(matching_kf.get('cp_out'))
                    }
                    step['servos'].append(servo_data)
            
            result.append(step)
            
        return result
    
    def _create_editor_window(self):
        """Create the motion editor window."""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"Servo Motion Editor - Servo {self.current_servo_id}")
        self.window.geometry("1000x700")
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Create main frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top toolbar
        self._create_toolbar(main_frame)
        
        # Create the matplotlib figure
        self.fig = plt.Figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Embed the matplotlib figure in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Add matplotlib toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, main_frame)
        toolbar.update()
        
        # Bottom controls
        self._create_bottom_controls(main_frame)
        
        # Set up plot elements
        self.keyframe_scatter = None
        self.curve_segment_lines = {}
        self.control_point_scatter = {}
        self.control_handle_lines = {}
        self.playback_line = None
        
        # Initialize plot
        self.setup_plot()
        
        # Connect matplotlib event handlers
        self.connect_events()
        
        # Initial draw
        self.update_plot_for_current_servo()
        
    def _create_toolbar(self, parent):
        """Create the toolbar with controls at the top of the window."""
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill="x", padx=5, pady=5, side="top")
        
        # Servo selection
        servo_frame = ttk.Frame(toolbar_frame)
        servo_frame.pack(side="left", padx=10)
        
        ttk.Label(servo_frame, text="Current Servo:").pack(side="left")
        
        self.servo_selector = ttk.Combobox(servo_frame, width=5)
        self.servo_selector['values'] = [str(sid) for sid in self.servo_ids]
        self.servo_selector.current(0)
        self.servo_selector.pack(side="left", padx=5)
        self.servo_selector.bind("<<ComboboxSelected>>", self._on_servo_selected)
        
        ttk.Button(servo_frame, text="Prev", command=self._prev_servo).pack(side="left", padx=2)
        ttk.Button(servo_frame, text="Next", command=self._next_servo).pack(side="left", padx=2)
        
        # Save status and buttons
        save_frame = ttk.Frame(toolbar_frame)
        save_frame.pack(side="right", padx=10)
        
        self.status_label = ttk.Label(save_frame, text=f"Status: {self.save_status}")
        self.status_label.pack(side="left", padx=5)
        
        ttk.Button(save_frame, text="Save Current Servo", 
                 command=self._save_current_servo).pack(side="left", padx=2)
        ttk.Button(save_frame, text="Save All", 
                 command=self._save_all_servos).pack(side="left", padx=2)
    
    def _create_bottom_controls(self, parent):
        """Create controls at the bottom of the window."""
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill="x", padx=5, pady=5, side="bottom")
        
        # Left side: Angle control
        angle_frame = ttk.Frame(controls_frame)
        angle_frame.pack(side="left", padx=10)
        
        ttk.Label(angle_frame, text="Angle (°):").pack(side="left")
        
        self.angle_var = tk.StringVar()
        self.angle_entry = ttk.Entry(angle_frame, textvariable=self.angle_var, width=5)
        self.angle_entry.pack(side="left", padx=5)
        self.angle_entry.bind("<Return>", self._on_angle_entry)
        self.angle_entry.bind("<FocusOut>", self._on_angle_entry)
        
        # Middle: Playback controls
        playback_frame = ttk.Frame(controls_frame)
        playback_frame.pack(side="left", padx=20)
        
        self.play_current_btn = ttk.Button(playback_frame, text="Play Current Servo", 
                                         command=self._play_current_servo)
        self.play_current_btn.pack(side="left", padx=2)
        
        self.play_all_btn = ttk.Button(playback_frame, text="Play All Servos",
                                     command=self._play_all_servos)
        self.play_all_btn.pack(side="left", padx=2)
        
        self.stop_btn = ttk.Button(playback_frame, text="Stop Playback",
                                 command=self._stop_playback, state="disabled")
        self.stop_btn.pack(side="left", padx=2)
        
        # Right side: Add/Remove keyframe
        kf_frame = ttk.Frame(controls_frame)
        kf_frame.pack(side="right", padx=10)
        
        ttk.Button(kf_frame, text="Add Keyframe", 
                 command=self._add_keyframe).pack(side="left", padx=2)
        ttk.Button(kf_frame, text="Remove Selected", 
                 command=self._remove_keyframe).pack(side="left", padx=2)
    
    def _on_servo_selected(self, event):
        """Handle servo selection from dropdown."""
        selection = self.servo_selector.get()
        try:
            new_id = int(selection)
            if new_id in self.servo_ids and new_id != self.current_servo_id:
                self.current_servo_id = new_id
                self.clear_selection()
                self.update_plot_for_current_servo()
                self.window.title(f"Servo Motion Editor - Servo {self.current_servo_id}")
        except ValueError:
            pass
    
    def _prev_servo(self):
        """Switch to previous servo."""
        if not self.servo_ids:
            return
            
        current_index = self.servo_ids.index(self.current_servo_id)
        prev_index = (current_index - 1) % len(self.servo_ids)
        self.current_servo_id = self.servo_ids[prev_index]
        self.servo_selector.set(str(self.current_servo_id))
        self.clear_selection()
        self.update_plot_for_current_servo()
        self.window.title(f"Servo Motion Editor - Servo {self.current_servo_id}")
    
    def _next_servo(self):
        """Switch to next servo."""
        if not self.servo_ids:
            return
            
        current_index = self.servo_ids.index(self.current_servo_id)
        next_index = (current_index + 1) % len(self.servo_ids)
        self.current_servo_id = self.servo_ids[next_index]
        self.servo_selector.set(str(self.current_servo_id))
        self.clear_selection()
        self.update_plot_for_current_servo()
        self.window.title(f"Servo Motion Editor - Servo {self.current_servo_id}")
    
    def _save_current_servo(self):
        """Save changes for the current servo back to the original sequence."""
        if self.sequence_update_callback:
            # Convert to recorder format
            updated_sequence = self._convert_to_recorder_format()
            
            # Update via callback
            self.sequence_update_callback(updated_sequence)
            self.save_status = "Saved"
            self.status_label.config(text=f"Status: {self.save_status}")
            
            logging.info(f"Saved changes for Servo {self.current_servo_id}")
    
    def _save_all_servos(self):
        """Save changes for all servos back to the original sequence."""
        if self.sequence_update_callback:
            # Convert to recorder format
            updated_sequence = self._convert_to_recorder_format()
            
            # Update via callback
            self.sequence_update_callback(updated_sequence)
            self.save_status = "Saved"
            self.status_label.config(text=f"Status: {self.save_status}")
            
            logging.info("Saved changes for all edited servos")
    
    def _format_sequence_for_serial(self, sequence):
        """Format a sequence for LOAD_SEQ command."""
        parts = []
        for kf in sequence:
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
    
    def _get_sequence_duration(self, sequence):
        """Calculate the duration of a sequence in milliseconds."""
        if not sequence:
            return 0
        return max(kf['time'] for kf in sequence)
    
    def _play_current_servo(self):
        """Play the current servo's sequence on the hardware."""
        if not self.send_command:
            messagebox.showinfo("Info", "No serial command function available")
            return
            
        sequence = self.get_current_sequence()
        if not sequence or len(sequence) < 2:
            messagebox.showinfo("Info", "Sequence needs at least 2 keyframes")
            return
        
        # Stop any existing playback
        self._stop_playback()
        
        # Send commands to ESP
        self.send_command("STOP")
        time.sleep(0.2)
        self.send_command("CLEAR_ALL")
        time.sleep(0.2)
        
        # Format and send sequence
        seq_str = self._format_sequence_for_serial(sequence)
        self.send_command(f"LOAD_SEQ:{self.current_servo_id}:{seq_str}")
        time.sleep(0.3)
        
        # Start playback
        self.send_command(f"PLAY_SERVO:{self.current_servo_id}")
        
        # Start GUI animation
        self._start_playback_animation(self._get_sequence_duration(sequence))
    
    def _play_all_servos(self):
        """Play all servo sequences on the hardware."""
        if not self.send_command:
            messagebox.showinfo("Info", "No serial command function available")
            return
            
        if not self.all_sequences:
            messagebox.showinfo("Info", "No sequences to play")
            return
            
        # Stop any existing playback
        self._stop_playback()
        
        # Send commands to ESP
        self.send_command("STOP")
        time.sleep(0.2)
        self.send_command("CLEAR_ALL")
        time.sleep(0.2)
        
        max_duration = 0
        
        # Load all sequences
        for servo_id, sequence in self.all_sequences.items():
            if len(sequence) >= 2:
                seq_str = self._format_sequence_for_serial(sequence)
                self.send_command(f"LOAD_SEQ:{servo_id}:{seq_str}")
                time.sleep(0.15)
                max_duration = max(max_duration, self._get_sequence_duration(sequence))
        
        # Start playback
        self.send_command("PLAY_LOADED")
        
        # Start GUI animation
        self._start_playback_animation(max_duration)
    
    def _stop_playback(self):
        """Stop playback on hardware and GUI."""
        if self.playback_active:
            # Stop animation
            self.playback_active = False
            if self.playback_line:
                self.playback_line.set_visible(False)
            self.canvas.draw_idle()
        
        # Update controls
        self.play_current_btn.config(state="normal")
        self.play_all_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        # Send stop command
        if self.send_command:
            self.send_command("STOP")
    
    def _start_playback_animation(self, duration_ms):
        """Start the playback line animation."""
        if duration_ms <= 0:
            return
            
        # Set up playback state
        self.playback_duration = duration_ms
        self.playback_start_time = time.time()
        self.playback_active = True
        
        # Set up playback line
        if self.playback_line:
            self.playback_line.set_xdata([0])
            self.playback_line.set_visible(True)
        
        # Update controls
        self.play_current_btn.config(state="disabled")
        self.play_all_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # Start animation
        self._update_playback_animation()
    
    def _update_playback_animation(self):
        """Update the playback animation line."""
        if not self.playback_active:
            return
            
        elapsed_s = time.time() - self.playback_start_time
        elapsed_ms = elapsed_s * 1000
        
        if elapsed_ms >= self.playback_duration:
            # Playback finished
            self._stop_playback()
        else:
            # Update line position
            if self.playback_line:
                self.playback_line.set_xdata([elapsed_ms])
                self.canvas.draw_idle()
            
            # Schedule next update
            self.window.after(50, self._update_playback_animation)  # 20fps
    
    def _on_angle_entry(self, event=None):
        """Handle changes to the angle entry field."""
        if self.selected_kf_index is None:
            return
            
        try:
            new_angle = round(max(0, min(180, float(self.angle_var.get()))))
            sequence = self.get_current_sequence()
            
            if self.selected_kf_index < len(sequence):
                old_angle = sequence[self.selected_kf_index]['angle']
                if old_angle != new_angle:
                    sequence[self.selected_kf_index]['angle'] = new_angle
                    self.update_plot_for_current_servo()
                    self.save_status = "Not Saved"
                    self.status_label.config(text=f"Status: {self.save_status}")
                    
                    # NEW CODE: Send SA command to update servo position when changing angle value
                    if self.send_command:
                        self.send_command(f"SA:{self.current_servo_id}:{int(new_angle)}")
                    
                    # Update angle in entry
                    self.angle_var.set(str(new_angle))
            else:
                self.clear_selection()
        except ValueError:
            # Restore valid value
            self._restore_angle_entry()
    
    def _restore_angle_entry(self):
        """Restore the angle entry to current keyframe's value."""
        if self.selected_kf_index is not None:
            sequence = self.get_current_sequence()
            if self.selected_kf_index < len(sequence):
                kf = sequence[self.selected_kf_index]
                self.angle_var.set(str(round(kf['angle'])))
    
    def _add_keyframe(self):
        """Add a new keyframe to the current sequence."""
        sequence = self.get_current_sequence()
        
        # Default to middle of current view if sequence is empty
        if not sequence:
            x_min, x_max = self.ax.get_xlim()
            new_time = (x_min + x_max) / 2
            new_kf = {'time': new_time, 'angle': 90, 'cp_in': None, 'cp_out': None}
            sequence.append(new_kf)
        else:
            # Add keyframe after last one
            last_kf = sequence[-1]
            new_time = last_kf['time'] + 500  # 500ms after last keyframe
            new_kf = {'time': new_time, 'angle': 90, 'cp_in': None, 'cp_out': None}
            sequence.append(new_kf)
        
        # Sort by time
        sequence.sort(key=lambda kf: kf['time'])
        
        # Update control points
        self.ensure_default_control_points(self.current_servo_id)
        
        # Update plot
        self.update_plot_for_current_servo()
        self.save_status = "Not Saved"
        self.status_label.config(text=f"Status: {self.save_status}")
    
    def _remove_keyframe(self):
        """Remove the selected keyframe."""
        if self.selected_kf_index is None:
            messagebox.showinfo("Info", "No keyframe selected")
            return
            
        sequence = self.get_current_sequence()
        if len(sequence) <= 2:
            messagebox.showinfo("Info", "Cannot remove keyframe. Minimum of 2 required.")
            return
            
        # Remove the keyframe
        if 0 <= self.selected_kf_index < len(sequence):
            sequence.pop(self.selected_kf_index)
            self.clear_selection()
            
            # Update control points
            self.ensure_default_control_points(self.current_servo_id)
            
            # Update plot
            self.update_plot_for_current_servo()
            self.save_status = "Not Saved"
            self.status_label.config(text=f"Status: {self.save_status}")
    
    def _on_close(self):
        """Handle window close event."""
        if self.save_status == "Not Saved":
            response = messagebox.askyesnocancel(
                "Unsaved Changes", 
                "You have unsaved changes. Save before closing?")
                
            if response is None:  # Cancel
                return
            elif response:  # Yes, save
                self._save_all_servos()
        
        # Clean up any resources
        plt.close(self.fig)
        self.window.destroy()
        
    def show(self):
        """Show the editor window."""
        self.window.lift()
        self.window.focus_force()
    
    # ---- Data Management and Plot Methods ----
    
    def get_current_sequence(self):
        """Get the keyframe sequence for the current servo."""
        return self.all_sequences.get(self.current_servo_id, [])
    
    def ensure_default_control_points(self, servo_id):
        """Ensure all keyframes have valid control points."""
        if servo_id not in self.all_sequences:
            return
            
        sequence = self.all_sequences[servo_id]
        num_keyframes = len(sequence)
        
        for i, kf in enumerate(sequence):
            default_dt_factor = 0.33
            
            # Incoming control point (not for first keyframe)
            if i > 0:
                if 'cp_in' not in kf or kf['cp_in'] is None:
                    prev_kf = sequence[i-1]
                    time_diff = kf['time'] - prev_kf['time']
                    dt = max(1, time_diff) * -default_dt_factor
                    kf['cp_in'] = {'dt': dt, 'da': 0.0}
                elif not isinstance(kf['cp_in'], dict):
                    kf['cp_in'] = {'dt': 0.0, 'da': 0.0}
            else:
                # First keyframe has no incoming control point
                kf['cp_in'] = None
            
            # Outgoing control point (not for last keyframe)
            if i < num_keyframes - 1:
                if 'cp_out' not in kf or kf['cp_out'] is None:
                    next_kf = sequence[i+1]
                    time_diff = next_kf['time'] - kf['time']
                    dt = max(1, time_diff) * default_dt_factor
                    kf['cp_out'] = {'dt': dt, 'da': 0.0}
                elif not isinstance(kf['cp_out'], dict):
                    kf['cp_out'] = {'dt': 0.0, 'da': 0.0}
            else:
                # Last keyframe has no outgoing control point
                kf['cp_out'] = None
    
    def setup_plot(self):
        """Set up the static plot elements."""
        self.ax.set_ylim(0, 180)
        self.ax.set_xlabel("Time (ms)")
        self.ax.set_ylabel("Servo Angle (°)")
        self.ax.grid(True, which='both', linestyle='--', linewidth=0.5)
        
        # Add playback line (initially invisible)
        self.playback_line = self.ax.axvline(0, color='orange', linestyle='--', lw=2, visible=False, zorder=20)
    
    def update_x_range(self, min_time, max_time=None):
        """Update the visible x-axis range."""
        if max_time is None:
            max_time = min_time + self.scroll_window
        
        min_time = max(0, min_time)
        self.ax.set_xlim(min_time, max_time)
        self.canvas.draw_idle()
    
    def get_control_point_absolute_coords(self, kf_index, cp_type):
        """Calculate absolute coordinates for a control point."""
        sequence = self.get_current_sequence()
        if kf_index >= len(sequence):
            return None
            
        kf = sequence[kf_index]
        cp_key = 'cp_' + cp_type
        
        if cp_key not in kf or kf[cp_key] is None:
            return None
            
        cp_relative = kf[cp_key]
        abs_time = kf['time'] + cp_relative['dt']
        abs_angle = kf['angle'] + cp_relative['da']
        abs_angle = max(0, min(180, abs_angle))  # Clamp
        
        return abs_time, abs_angle
    
    def clear_plot_elements(self):
        """Remove all dynamic plot elements."""
        if self.keyframe_scatter and self.keyframe_scatter in self.ax.collections:
            self.keyframe_scatter.remove()
            self.keyframe_scatter = None
            
        for line in self.curve_segment_lines.values():
            if line in self.ax.lines:
                line.remove()
        self.curve_segment_lines.clear()
        
        for point in self.control_point_scatter.values():
            if point in self.ax.collections:
                point.remove()
        self.control_point_scatter.clear()
        
        for line in self.control_handle_lines.values():
            if line in self.ax.lines:
                line.remove()
        self.control_handle_lines.clear()
    
    def clear_selection(self):
        """Clear the current keyframe selection."""
        self.selected_kf_index = None
        self.angle_var.set("")
    
    def update_plot_for_current_servo(self):
        """Update the plot to show the current servo's sequence."""
        self.clear_plot_elements()
        self.setup_plot()
        
        sequence = self.get_current_sequence()
        
        # Handle selection and textbox update
        if self.selected_kf_index is not None:
            if self.selected_kf_index >= len(sequence):
                self.clear_selection()
            else:
                self._restore_angle_entry()
        
        if not sequence:
            if self.playback_line:
                self.playback_line.set_visible(False)
            self.canvas.draw_idle()
            return
        
        # Plot keyframes
        keyframe_times = [int(round(kf['time'])) for kf in sequence]
        keyframe_angles = [int(round(kf['angle'])) for kf in sequence]
        self.keyframe_scatter = self.ax.scatter(
            keyframe_times, keyframe_angles,
            color="red", s=80, zorder=10, label="Keyframes", picker=5
        )
        
        # Plot curves, control points, and handles
        num_keyframes = len(sequence)
        curve_drawn, handle_label_drawn = False, False
        
        for i in range(num_keyframes):
            kf_pos = (sequence[i]['time'], sequence[i]['angle'])
            
            # Incoming control point
            if i > 0:
                cp_in_abs = self.get_control_point_absolute_coords(i, 'in')
                if cp_in_abs:
                    self._draw_control_point_and_handle(i, 'in', kf_pos, cp_in_abs, not handle_label_drawn)
                    handle_label_drawn = True
            
            # Outgoing control point
            if i < num_keyframes - 1:
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                if cp_out_abs:
                    self._draw_control_point_and_handle(i, 'out', kf_pos, cp_out_abs, not handle_label_drawn)
                    handle_label_drawn = True
            
            # Curve segment
            if i < num_keyframes - 1:
                kf_next = sequence[i+1]
                kf_next_pos = (kf_next['time'], kf_next['angle'])
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                cp_in_abs_next = self.get_control_point_absolute_coords(i + 1, 'in')
                
                if cp_out_abs and cp_in_abs_next:
                    p0, p1, p2, p3 = kf_pos, cp_out_abs, cp_in_abs_next, kf_next_pos
                    time_vals, angle_vals = self._compute_bezier_curve_segment(p0, p1, p2, p3)
                    curve_label = "Curve" if not curve_drawn else None
                    line, = self.ax.plot(time_vals, angle_vals, color='blue', lw=2, zorder=5, label=curve_label)
                    self.curve_segment_lines[i] = line
                    curve_drawn = True
        
        # Update legend
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
            self.ax.legend(handles, labels, loc='best')
        
        # Adjust x-axis to fit content
        if sequence:
            min_time = min(kf['time'] for kf in sequence)
            max_time = max(kf['time'] for kf in sequence)
            padding = max(500, (max_time - min_time) * 0.1)
            self.update_x_range(max(0, min_time - padding), max_time + padding)
        
        # Make sure playback line is hidden if not active
        if not self.playback_active and self.playback_line:
            self.playback_line.set_visible(False)
            
        self.canvas.draw_idle()
    
    def _draw_control_point_and_handle(self, kf_index, cp_type, kf_pos, cp_abs_pos, add_label=False):
        """Draw a control point and its handle line."""
        key = (kf_index, cp_type)
        handle_label = "Control Point" if add_label else None
        
        # Line
        line = Line2D([kf_pos[0], cp_abs_pos[0]], [kf_pos[1], cp_abs_pos[1]],
                      ls=':', color='green', alpha=0.7, zorder=8)
        self.ax.add_line(line)
        self.control_handle_lines[key] = line
        
        # Point
        point = self.ax.scatter(cp_abs_pos[0], cp_abs_pos[1],
                              color='green', s=60, alpha=0.8, zorder=9, picker=5, label=handle_label)
        self.control_point_scatter[key] = point
    
    def _cubic_bezier_point(self, t, p0, p1, p2, p3):
        """Compute a point on a cubic bezier curve."""
        # Bernstein basis polynomials
        b0 = (1 - t)**3
        b1 = 3 * (1 - t)**2 * t
        b2 = 3 * (1 - t) * t**2
        b3 = t**3
        
        # Calculate point coordinates
        time_val = b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0]
        angle_val = b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]
        
        return (time_val, angle_val)
    
    def _compute_bezier_curve_segment(self, p0, p1, p2, p3, num_points=100):
        """Compute points along a cubic bezier curve segment."""
        t_values = np.linspace(0, 1, num_points)
        points = [self._cubic_bezier_point(t, p0, p1, p2, p3) for t in t_values]
        
        # Unzip points into time and angle arrays
        time_values, angle_values = zip(*points) if points else ([], [])
        return np.array(time_values), np.array(angle_values)
    
    # ---- Event Handling ----
    
    def connect_events(self):
        """Connect matplotlib event handlers."""
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
    
    def on_press(self, event):
        """Handle mouse press events."""
        if event.inaxes != self.ax or event.button != 1:
            return
        
        element_selected = False
        
        # Check control points first
        clicked_cp_key = None
        for key, scatter_point in self.control_point_scatter.items():
            cont, _ = scatter_point.contains(event)
            if cont:
                clicked_cp_key = key
                break
        
        if clicked_cp_key:
            element_selected = True
            kf_index, cp_type = clicked_cp_key
            if kf_index < len(self.get_current_sequence()):
                self.dragging_element = {'type': 'control_point', 'kf_index': kf_index, 'cp_type': cp_type}
                self.clear_selection()
                return
            else:
                self.dragging_element = None
                return
        
        # Check keyframes ---- OLD
        # if self.keyframe_scatter:
        #     cont, ind = self.keyframe_scatter.contains(event)
        #     if cont:
        #         element_selected = True
        #         kf_index = ind["ind"][0]
        #         if kf_index < len(self.get_current_sequence()):
        #             self.dragging_element = {'type': 'keyframe', 'index': kf_index}
        #             self.selected_kf_index = kf_index
        #             self._restore_angle_entry()
        #             return
        #         else:
        #             self.dragging_element = None
        #             return

        #check keyframes ----- NEW:
        if self.keyframe_scatter:
            cont, ind = self.keyframe_scatter.contains(event)
            if cont:
                element_selected = True
                kf_index = ind["ind"][0]
                if kf_index < len(self.get_current_sequence()):
                    self.dragging_element = {'type': 'keyframe', 'index': kf_index}
                    self.selected_kf_index = kf_index
                    self._restore_angle_entry()
                    
                    # NEW CODE: Send SA command to update servo position when selecting a keyframe
                    current_angle = self.get_current_sequence()[kf_index]['angle']
                    if self.send_command:
                        self.send_command(f"SA:{self.current_servo_id}:{int(round(current_angle))}")
                    
                    return
                else:
                    self.dragging_element = None
                    return
        
        # If click was in axes but not on a selectable element, clear selection
        if not element_selected:
            self.clear_selection()
    
    def on_release(self, event):
        """Handle mouse release events."""
        if event.button == 1 and self.dragging_element:
            self.dragging_element = None
    
    def on_motion(self, event):
        """Handle mouse motion events."""
        if not self.dragging_element or event.inaxes != self.ax:
            return
        
        sequence = self.get_current_sequence()
        element_type = self.dragging_element['type']
        current_time = event.xdata
        current_angle = event.ydata
        
        if current_time is None or current_angle is None:
            return
        
        current_angle_clamped = max(0, min(180, current_angle))
        needs_update = False
        
        # if element_type == 'keyframe':
        #     kf_index = self.dragging_element['index']
        #     if kf_index < len(sequence):
        #         # Only angle changes now (time fixed to keep order)
        #         target_angle_rounded = round(current_angle_clamped)
        #         if sequence[kf_index]['angle'] != target_angle_rounded:
        #             sequence[kf_index]['angle'] = target_angle_rounded
        #             needs_update = True
        if element_type == 'keyframe':
            kf_index = self.dragging_element['index']
            if kf_index < len(sequence):
                # Only angle changes now (time fixed to keep order)
                target_angle_rounded = round(current_angle_clamped)
                old_angle = sequence[kf_index]['angle']
                
                if old_angle != target_angle_rounded:
                    sequence[kf_index]['angle'] = target_angle_rounded
                    needs_update = True
                    
                    # NEW CODE: Send SA command to update servo position during dragging
                    if self.send_command:
                        self.send_command(f"SA:{self.current_servo_id}:{int(target_angle_rounded)}")
                    
                # Update the textbox display in real-time
                if self.selected_kf_index == kf_index:
                    self.angle_var.set(str(target_angle_rounded))
        
        elif element_type == 'control_point':
            kf_index = self.dragging_element['kf_index']
            if kf_index < len(sequence):
                cp_type = self.dragging_element['cp_type']
                cp_key = 'cp_' + cp_type
                kf = sequence[kf_index]
                
                if cp_key in kf and kf[cp_key] is not None:
                    # Calculate relative dt/da based on target mouse position
                    dt = current_time - kf['time']
                    da = current_angle_clamped - kf['angle']
                    
                    # Apply constraints - outgoing points must be after keyframe, incoming before
                    if cp_type == 'out':
                        dt = max(0.01, dt)
                    if cp_type == 'in':
                        dt = min(-0.01, dt)
                    
                    # Update data structure if changed
                    if sequence[kf_index][cp_key]['dt'] != dt or sequence[kf_index][cp_key]['da'] != da:
                        sequence[kf_index][cp_key]['dt'] = dt
                        sequence[kf_index][cp_key]['da'] = da
                        needs_update = True
        
        # Redraw plot if data changed
        if needs_update:
            self.update_plot_for_current_servo()
            self.save_status = "Not Saved"
            self.status_label.config(text=f"Status: {self.save_status}")
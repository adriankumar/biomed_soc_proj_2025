import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.lines import Line2D
import copy
import time
from core.bezier_interpolation import (
    bezier_point, control_point_absolute, compute_curve_segment, 
    ensure_control_points, generate_playback_points, execute_smooth_transition
)
from core.validation import LEAD_IN_DURATION_MS, is_smoothing_active, plan_lead_in

class MotionEditor:
    #integrated motion editor for servo sequence curve editing using unified bezier format
    def __init__(self, parent, sequence_data, state_manager, serial_connection, log_callback=None, save_callback=None):
        self.parent = parent
        self.sequence_data = copy.deepcopy(sequence_data) if sequence_data else {}  #unified bezier format
        self.state_manager = state_manager  #for servo configuration data
        self.serial_connection = serial_connection  #for hardware preview
        self.log_callback = log_callback
        self.save_callback = save_callback  #callback to push changes back to sequence manager
        
        #current editing state
        self.component_names = sorted(list(self.sequence_data.keys()))
        self.current_component = self.component_names[0] if self.component_names else None
        self.selected_kf_index = None
        self.dragging_element = None
        self.save_status = "not saved"
        
        #playback state
        self.playback_active = False
        self.playback_duration = 0
        self.playback_start_time = 0
        
        #ensure all sequences have proper control points using shared function
        for component_name in self.component_names:
            ensure_control_points(self.sequence_data[component_name], use_smooth_defaults=True)
        
        self._create_editor_window()
    
    #create motion editor window with component-aware interface
    def _create_editor_window(self):
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"motion editor - {self.current_component or 'no component'}")
        self.window.geometry("1200x800")
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        #top toolbar with component selection
        self._create_toolbar(main_frame)
        
        #matplotlib plotting area
        self.fig = plt.Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        toolbar = NavigationToolbar2Tk(self.canvas, main_frame)
        toolbar.update()
        
        #bottom controls for keyframe manipulation
        self._create_bottom_controls(main_frame)
        
        #plot elements for dynamic updates
        self.keyframe_scatter = None
        self.curve_lines = {}
        self.control_points = {}
        self.control_handles = {}
        self.playback_line = None
        
        self._setup_plot()
        self._connect_events()
        self._update_plot()
    
    #create toolbar with component selection and save controls
    def _create_toolbar(self, parent):
        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill="x", pady=(0, 10))
        
        #component selection
        comp_frame = ttk.Frame(toolbar_frame)
        comp_frame.pack(side="left", padx=10)
        
        ttk.Label(comp_frame, text="component:").pack(side="left")
        
        self.component_selector = ttk.Combobox(comp_frame, width=15, state="readonly")
        self.component_selector['values'] = self.component_names
        if self.current_component:
            self.component_selector.set(self.current_component)
        self.component_selector.pack(side="left", padx=5)
        self.component_selector.bind("<<ComboboxSelected>>", self._on_component_changed)
        
        ttk.Button(comp_frame, text="←", command=self._prev_component).pack(side="left", padx=2)
        ttk.Button(comp_frame, text="→", command=self._next_component).pack(side="left", padx=2)
        
        #save controls
        save_frame = ttk.Frame(toolbar_frame)
        save_frame.pack(side="right", padx=10)
        
        self.status_label = ttk.Label(save_frame, text=f"status: {self.save_status}")
        self.status_label.pack(side="left", padx=5)
        
        ttk.Button(save_frame, text="save changes", command=self._save_changes).pack(side="left", padx=2)
        ttk.Button(save_frame, text="reset curves", command=self._reset_curves).pack(side="left", padx=2)
    
    #create bottom controls for angle entry and playback
    def _create_bottom_controls(self, parent):
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill="x", pady=(10, 0))
        
        #angle control
        angle_frame = ttk.Frame(controls_frame)
        angle_frame.pack(side="left", padx=10)
        
        ttk.Label(angle_frame, text="pwm value:").pack(side="left")
        
        self.angle_var = tk.StringVar()
        self.angle_entry = ttk.Entry(angle_frame, textvariable=self.angle_var, width=6)
        self.angle_entry.pack(side="left", padx=5)
        self.angle_entry.bind("<Return>", self._on_angle_changed)
        self.angle_entry.bind("<FocusOut>", self._on_angle_changed)
        
        #playback controls
        playback_frame = ttk.Frame(controls_frame)
        playback_frame.pack(side="left", padx=20)
        
        self.play_current_btn = ttk.Button(playback_frame, text="play component", command=self._play_current)
        self.play_current_btn.pack(side="left", padx=2)
        
        self.play_all_btn = ttk.Button(playback_frame, text="play all", command=self._play_all)
        self.play_all_btn.pack(side="left", padx=2)
        
        self.stop_btn = ttk.Button(playback_frame, text="stop", command=self._stop_playback, state="disabled")
        self.stop_btn.pack(side="left", padx=2)
        
        #keyframe management
        kf_frame = ttk.Frame(controls_frame)
        kf_frame.pack(side="right", padx=10)
        
        ttk.Button(kf_frame, text="add keyframe", command=self._add_keyframe).pack(side="left", padx=2)
        ttk.Button(kf_frame, text="remove selected", command=self._remove_keyframe).pack(side="left", padx=2)
    
    #handle component selection change
    def _on_component_changed(self, event=None):
        selected = self.component_selector.get()
        if selected and selected != self.current_component:
            self.current_component = selected
            self._clear_selection()
            self._update_plot()
            self.window.title(f"motion editor - {self.current_component}")
    
    #navigate to previous component
    def _prev_component(self):
        if not self.component_names or not self.current_component:
            return
        try:
            current_index = self.component_names.index(self.current_component)
            prev_index = (current_index - 1) % len(self.component_names)
            self.current_component = self.component_names[prev_index]
            self.component_selector.set(self.current_component)
            self._on_component_changed()
        except ValueError:
            pass
    
    #navigate to next component
    def _next_component(self):
        if not self.component_names or not self.current_component:
            return
        try:
            current_index = self.component_names.index(self.current_component)
            next_index = (current_index + 1) % len(self.component_names)
            self.current_component = self.component_names[next_index]
            self.component_selector.set(self.current_component)
            self._on_component_changed()
        except ValueError:
            pass
    
    #get servo configuration for component from state manager
    def _get_servo_config(self, component_name):
        config = self.state_manager.get_component_config(component_name)
        if not config:
            return {'index': 0, 'pulse_min': 150, 'pulse_max': 600}
        return {
            'index': config['index'],
            'pulse_min': config['pulse_min'],
            'pulse_max': config['pulse_max']
        }
    
    #setup basic plot configuration
    def _setup_plot(self):
        if not self.current_component:
            return
        
        config = self._get_servo_config(self.current_component)
        self.ax.set_ylim(config['pulse_min'] - 10, config['pulse_max'] + 10)
        self.ax.set_xlabel("time (ms)")
        self.ax.set_ylabel("pwm value")
        self.ax.grid(True, alpha=0.3)
        
        #playback indicator line
        self.playback_line = self.ax.axvline(0, color='orange', linestyle='--', linewidth=2, visible=False, zorder=20)
    
    #get current component keyframe sequence
    def _get_current_sequence(self):
        if not self.current_component or self.current_component not in self.sequence_data:
            return []
        return self.sequence_data[self.current_component]
    
    #clear all dynamic plot elements
    def _clear_plot_elements(self):
        if self.keyframe_scatter and self.keyframe_scatter in self.ax.collections:
            self.keyframe_scatter.remove()
            self.keyframe_scatter = None
        
        for line in self.curve_lines.values():
            if line in self.ax.lines:
                line.remove()
        self.curve_lines.clear()
        
        for point in self.control_points.values():
            if point in self.ax.collections:
                point.remove()
        self.control_points.clear()
        
        for line in self.control_handles.values():
            if line in self.ax.lines:
                line.remove()
        self.control_handles.clear()
    
    #update plot for current component using shared bezier functions
    def _update_plot(self):
        self._clear_plot_elements()
        self._setup_plot()
        
        if not self.current_component:
            self.canvas.draw_idle()
            return
        
        keyframes = self._get_current_sequence()
        if not keyframes:
            self.canvas.draw_idle()
            return
        
        #plot keyframes as scatter points
        kf_times = [kf['time'] for kf in keyframes]
        kf_angles = [kf['angle'] for kf in keyframes]
        
        self.keyframe_scatter = self.ax.scatter(kf_times, kf_angles, color="red", s=100, zorder=15, label="keyframes", picker=True)
        
        #plot curves and control points using shared functions
        self._plot_curves_and_controls(keyframes)
        
        #adjust view range
        if kf_times:
            time_padding = max(500, (max(kf_times) - min(kf_times)) * 0.1)
            self.ax.set_xlim(min(kf_times) - time_padding, max(kf_times) + time_padding)
        
        #update legend
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
            self.ax.legend()
        
        #restore selection highlighting
        if self.selected_kf_index is not None:
            self._update_angle_display()
        
        self.canvas.draw_idle()
    
    #plot bezier curves and control points using shared computation functions
    def _plot_curves_and_controls(self, keyframes):
        if not keyframes:
            return
        
        num_kf = len(keyframes)
        servo_config = self._get_servo_config(self.current_component)
        curve_plotted = False
        control_plotted = False
        
        for i in range(num_kf):
            kf = keyframes[i]
            kf_pos = (kf['time'], kf['angle'])
            
            #plot incoming control point using shared function
            if i > 0:
                cp_in = control_point_absolute(kf, 'in', servo_config)
                if cp_in:
                    self._draw_control_point(i, 'in', kf_pos, cp_in, not control_plotted)
                    control_plotted = True
            
            #plot outgoing control point using shared function
            if i < num_kf - 1:
                cp_out = control_point_absolute(kf, 'out', servo_config)
                if cp_out:
                    self._draw_control_point(i, 'out', kf_pos, cp_out, not control_plotted)
                    control_plotted = True
            
            #plot curve segment using shared computation
            if i < num_kf - 1:
                times, angles = compute_curve_segment(kf, keyframes[i + 1], servo_config)
                curve_label = "bezier curve" if not curve_plotted else None
                line, = self.ax.plot(times, angles, color='blue', linewidth=2, zorder=10, label=curve_label)
                self.curve_lines[i] = line
                curve_plotted = True
    
    #draw control point with handle line
    def _draw_control_point(self, kf_index, cp_type, kf_pos, cp_pos, add_label):
        cp_key = (kf_index, cp_type)
        label_text = "control points" if add_label else None
        
        #handle line
        handle = Line2D([kf_pos[0], cp_pos[0]], [kf_pos[1], cp_pos[1]], linestyle=':', color='green', alpha=0.7, linewidth=1, zorder=8)
        self.ax.add_line(handle)
        self.control_handles[cp_key] = handle
        
        #control point
        point = self.ax.scatter(cp_pos[0], cp_pos[1], color='green', s=60, alpha=0.8, zorder=12, picker=True, label=label_text)
        self.control_points[cp_key] = point
    
    #connect matplotlib event handlers
    def _connect_events(self):
        self.fig.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.fig.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_mouse_motion)

    #apply target positions using realtime smoothing when enabled
    def _apply_targets_smoothly(self, targets, duration_s=1.0, completion_callback=None):
        try:
            if not isinstance(targets, dict) or not targets:
                return
            duration_ms = int(max(0, duration_s * 1000))
            apply, filtered, planned_ms = plan_lead_in(self.state_manager, self.serial_connection, targets, duration_ms)
            if apply and filtered:
                execute_smooth_transition(self.window, self.serial_connection, self.state_manager, filtered, planned_ms / 1000.0)
                if completion_callback:
                    self.window.after(planned_ms, lambda: completion_callback(True, None))
                return
            for comp, val in targets.items():
                try:
                    config = self._get_servo_config(comp)
                    servo_index = config['index']
                    command = f"SP:{servo_index}:{int(round(val))}"
                    if self.serial_connection and self.serial_connection.is_connected:
                        self.serial_connection.send_command(command)
                    if self.log_callback:
                        self.log_callback(f"preview: {comp} -> {int(round(val))}")
                except Exception:
                    pass
            if completion_callback:
                completion_callback(True, None)
        except Exception:
            pass

    #handle mouse press for element selection
    def _on_mouse_press(self, event):
        if event.inaxes != self.ax or event.button != 1:
            return
        
        element_clicked = False
        
        #check control points first
        for cp_key, cp_scatter in self.control_points.items():
            contains, _ = cp_scatter.contains(event)
            if contains:
                kf_index, cp_type = cp_key
                self.dragging_element = {'type': 'control_point', 'kf_index': kf_index, 'cp_type': cp_type}
                self._clear_selection()
                element_clicked = True
                break
        
        #check keyframes
        if not element_clicked and self.keyframe_scatter:
            contains, info = self.keyframe_scatter.contains(event)
            if contains:
                kf_index = info["ind"][0]
                keyframes = self._get_current_sequence()
                
                if kf_index < len(keyframes):
                    self.dragging_element = {'type': 'keyframe', 'index': kf_index}
                    self.selected_kf_index = kf_index
                    self._update_angle_display()
                    
                    #preview current keyframe using smoothing gate
                    current_angle = keyframes[kf_index]['angle']
                    self._apply_targets_smoothly({self.current_component: int(current_angle)}, duration_s=1.0)
                    
                    element_clicked = True
        
        #clear selection if clicking empty space
        if not element_clicked:
            self._clear_selection()
    
    #handle mouse release
    def _on_mouse_release(self, event):
        if event.button == 1:
            #execute smoothing transition on release for keyframe moves when enabled
            if self.dragging_element and self.dragging_element.get('type') == 'keyframe':
                keyframes = self._get_current_sequence()
                idx = self.dragging_element['index']
                if 0 <= idx < len(keyframes):
                    target = int(keyframes[idx]['angle'])
                    last_sent = self.state_manager.get_last_sent(self.current_component)
                    delta = abs(target - last_sent)
                    duration = 0.5 if delta <= 50 else 1.0
                    self._apply_targets_smoothly({self.current_component: target}, duration_s=duration)
            self.dragging_element = None
    
    #handle mouse motion for dragging
    def _on_mouse_motion(self, event):
        if not self.dragging_element or event.inaxes != self.ax:
            return
        
        if event.xdata is None or event.ydata is None:
            return
        
        keyframes = self._get_current_sequence()
        element_type = self.dragging_element['type']
        current_time = event.xdata
        current_angle = event.ydata
        
        #clamp angle to component constraints
        config = self._get_servo_config(self.current_component)
        clamped_angle = max(config['pulse_min'], min(config['pulse_max'], current_angle))
        
        data_changed = False
        
        if element_type == 'keyframe':
            kf_index = self.dragging_element['index']
            if kf_index < len(keyframes):
                #only allow vertical movement to maintain timing
                target_angle = round(clamped_angle)
                old_angle = keyframes[kf_index]['angle']
                
                if old_angle != target_angle:
                    keyframes[kf_index]['angle'] = target_angle
                    data_changed = True
                    
                    #real-time hardware preview only when smoothing off
                    if not self.state_manager.realtime_smoothing_enabled:
                        self._send_position_preview(target_angle)
                    
                    #update angle display
                    if self.selected_kf_index == kf_index:
                        self.angle_var.set(str(target_angle))
        
        elif element_type == 'control_point':
            kf_index = self.dragging_element['kf_index']
            cp_type = self.dragging_element['cp_type']
            
            if kf_index < len(keyframes):
                kf = keyframes[kf_index]
                cp_key = f'cp_{cp_type}'
                
                if cp_key in kf and kf[cp_key]:
                    #calculate relative offsets
                    time_offset = current_time - kf['time']
                    angle_offset = clamped_angle - kf['angle']
                    
                    #enforce direction constraints
                    if cp_type == 'out':
                        time_offset = max(0.01, time_offset)
                    elif cp_type == 'in':
                        time_offset = min(-0.01, time_offset)
                    
                    #update control point data
                    old_dt = kf[cp_key]['dt']
                    old_da = kf[cp_key]['da']
                    
                    if old_dt != time_offset or old_da != angle_offset:
                        kf[cp_key]['dt'] = time_offset
                        kf[cp_key]['da'] = angle_offset
                        data_changed = True
        
        #redraw if data changed
        if data_changed:
            self._update_plot()
            self._mark_unsaved()
    
    #send position to hardware for real-time preview
    def _send_position_preview(self, angle_value):
        if not self.serial_connection or not self.serial_connection.is_connected:
            return
        
        config = self._get_servo_config(self.current_component)
        servo_index = config['index']
        command = f"SP:{servo_index}:{int(round(angle_value))}"
        
        if self.serial_connection.send_command(command):
            if self.log_callback:
                self.log_callback(f"preview: {self.current_component} -> {int(round(angle_value))}")
    
    #handle angle entry changes
    def _on_angle_changed(self, event=None):
        if self.selected_kf_index is None:
            return
        
        try:
            new_angle = round(float(self.angle_var.get()))
            config = self._get_servo_config(self.current_component)
            clamped_angle = max(config['pulse_min'], min(config['pulse_max'], new_angle))
            
            keyframes = self._get_current_sequence()
            if self.selected_kf_index < len(keyframes):
                old_angle = keyframes[self.selected_kf_index]['angle']
                
                if old_angle != clamped_angle:
                    keyframes[self.selected_kf_index]['angle'] = clamped_angle
                    self._update_plot()
                    self._mark_unsaved()
                    
                    #hardware preview
                    self._send_position_preview(clamped_angle)
                
                self.angle_var.set(str(clamped_angle))
        except ValueError:
            self._update_angle_display()
    
    #update angle display from selected keyframe
    def _update_angle_display(self):
        if self.selected_kf_index is not None:
            keyframes = self._get_current_sequence()
            if self.selected_kf_index < len(keyframes):
                current_angle = keyframes[self.selected_kf_index]['angle']
                self.angle_var.set(str(round(current_angle)))
    
    #clear keyframe selection
    def _clear_selection(self):
        self.selected_kf_index = None
        self.angle_var.set("")
    
    #add new keyframe to current sequence
    def _add_keyframe(self):
        keyframes = self._get_current_sequence()
        
        if not keyframes:
            #first keyframe at time 0
            config = self._get_servo_config(self.current_component)
            default_angle = (config['pulse_min'] + config['pulse_max']) // 2
            new_kf = {'time': 0, 'angle': default_angle, 'cp_in': None, 'cp_out': None}
            self.sequence_data[self.current_component] = [new_kf]
        else:
            #add after last keyframe
            last_kf = keyframes[-1]
            new_time = last_kf['time'] + 1000
            config = self._get_servo_config(self.current_component)
            default_angle = (config['pulse_min'] + config['pulse_max']) // 2
            new_kf = {'time': new_time, 'angle': default_angle, 'cp_in': None, 'cp_out': None}
            keyframes.append(new_kf)
        
        #regenerate control points using shared function
        ensure_control_points(self.sequence_data[self.current_component], use_smooth_defaults=True)
        self._update_plot()
        self._mark_unsaved()
        
        if self.log_callback:
            self.log_callback(f"added keyframe to {self.current_component}")
    
    #remove selected keyframe
    def _remove_keyframe(self):
        if self.selected_kf_index is None:
            messagebox.showinfo("no selection", "no keyframe selected for removal")
            return
        
        keyframes = self._get_current_sequence()
        if len(keyframes) <= 2:
            messagebox.showinfo("minimum keyframes", "cannot remove keyframe - minimum of 2 required")
            return
        
        if 0 <= self.selected_kf_index < len(keyframes):
            keyframes.pop(self.selected_kf_index)
            self._clear_selection()
            
            #regenerate control points using shared function
            ensure_control_points(keyframes, use_smooth_defaults=True)
            self._update_plot()
            self._mark_unsaved()
            
            if self.log_callback:
                self.log_callback(f"removed keyframe from {self.current_component}")
    
    #play current component sequence using shared interpolation
    def _play_current(self):
        if not self.current_component:
            messagebox.showinfo("no component", "no component selected")
            return
        
        keyframes = self._get_current_sequence()
        if len(keyframes) < 2:
            messagebox.showinfo("no sequence", "sequence needs at least 2 keyframes")
            return
        
        #generate playback points using shared function
        servo_config = self._get_servo_config(self.current_component)
        playback_points = generate_playback_points(keyframes, servo_config, time_step=50)
        
        if not playback_points:
            messagebox.showinfo("no points", "failed to generate playback points")
            return
        
        sequences = {self.current_component: playback_points}
        self._execute_playback(sequences)
    
    #play all component sequences using shared interpolation
    def _play_all(self):
        if not self.sequence_data:
            messagebox.showinfo("no sequences", "no sequences to play")
            return
        
        all_sequences = {}
        for component_name, keyframes in self.sequence_data.items():
            if len(keyframes) >= 2:
                servo_config = self._get_servo_config(component_name)
                playback_points = generate_playback_points(keyframes, servo_config, time_step=50)
                if playback_points:
                    all_sequences[component_name] = playback_points
        
        if not all_sequences:
            messagebox.showinfo("no valid sequences", "no sequences with enough keyframes")
            return
        
        self._execute_playback(all_sequences)

    def _execute_playback(self, sequences):
        #execute playback using unified bezier interpolation system
        try:
            self._stop_playback()
            
            #calculate total duration for animation
            max_duration = 0
            for component_name, points in sequences.items():
                if points:
                    duration = max(point[0] for point in points)
                    max_duration = max(max_duration, duration)
            
            if max_duration <= 0:
                return
            
            #prepare bezier sequences for unified playback
            bezier_sequences = {}
            for component_name in sequences.keys():
                if component_name in self.sequence_data:
                    bezier_sequences[component_name] = self.sequence_data[component_name]
            
            #get servo configurations for unified playback
            servo_configurations = {}
            for component_name in bezier_sequences.keys():
                servo_configurations[component_name] = self._get_servo_config(component_name)
            
            #lead-in smoothing from last sent if enabled
            def _start_playback(*args):
                from core.bezier_interpolation import execute_unified_playback
                success, message = execute_unified_playback(
                    gui_widget=self.window,
                    serial_connection=self.serial_connection,
                    bezier_sequences=bezier_sequences,
                    servo_configurations=servo_configurations,
                    completion_callback=self._on_unified_playback_complete,
                    log_callback=self.log_callback
                )
                if not success:
                    self._stop_playback()
                    if self.log_callback:
                        self.log_callback(f"unified playback failed: {message}")

            #decide lead-in and align animation start
            lead_targets = {}
            for comp, keyframes in bezier_sequences.items():
                if keyframes:
                    lead_targets[comp] = int(keyframes[0]['angle'])
            apply, filtered, planned_ms = plan_lead_in(self.state_manager, self.serial_connection, lead_targets, LEAD_IN_DURATION_MS)

            def _start_both():
                self._start_playback_animation(max_duration)
                _start_playback()

            if apply and filtered:
                self._apply_targets_smoothly(filtered, duration_s=planned_ms / 1000.0, completion_callback=lambda *_: _start_both())
            else:
                _start_both()
            
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"playback error: {str(e)}")
            self._stop_playback()

    def _on_unified_playback_complete(self, success, error_msg=None):
        #handle completion from unified playback system
        self._stop_playback()
        if not success and error_msg and self.log_callback:
            self.log_callback(f"playback error: {error_msg}")
    
    #execute playback using sp commands with python timing
    # def _execute_playback(self, sequences):
    #     try:
    #         self._stop_playback()
            
    #         #calculate total duration
    #         max_duration = 0
    #         for component_name, points in sequences.items():
    #             if points:
    #                 duration = max(point[0] for point in points)
    #                 max_duration = max(max_duration, duration)
            
    #         if max_duration <= 0:
    #             return
            
    #         #start playback animation
    #         self._start_playback_animation(max_duration)
            
    #         #execute timed playback
    #         self._execute_timed_playback(sequences, max_duration)
            
    #         if self.log_callback:
    #             component_count = len(sequences)
    #             self.log_callback(f"started playback: {component_count} components, {max_duration}ms duration")
        
    #     except Exception as e:
    #         messagebox.showerror("playback error", f"failed to start playback: {str(e)}")
    #         self._stop_playback()
    
    #execute timed playback using sp commands
    # def _execute_timed_playback(self, sequences, total_duration):
    #     start_time = time.time()
        
    #     #create command timeline
    #     command_timeline = []
    #     for component_name, points in sequences.items():
    #         config = self._get_servo_config(component_name)
    #         servo_index = config['index']
            
    #         for point_time, angle in points:
    #             command_timeline.append((point_time, f"SP:{servo_index}:{angle}"))
        
    #     #sort by time
    #     command_timeline.sort(key=lambda x: x[0])
        
    #     #schedule command execution
    #     self._schedule_commands(command_timeline, start_time)
    
    # #schedule command execution with precise timing
    # def _schedule_commands(self, command_timeline, start_time):
    #     if not command_timeline or not self.playback_active:
    #         return
        
    #     current_time = time.time()
    #     elapsed_ms = (current_time - start_time) * 1000
        
    #     #find commands to execute now
    #     commands_to_execute = []
    #     remaining_commands = []
        
    #     for cmd_time, command in command_timeline:
    #         if cmd_time <= elapsed_ms + 50:  #50ms tolerance
    #             commands_to_execute.append(command)
    #         else:
    #             remaining_commands.append((cmd_time, command))
        
    #     #execute commands
    #     for command in commands_to_execute:
    #         if self.serial_connection and self.serial_connection.is_connected:
    #             self.serial_connection.send_command(command)
        
    #     #schedule next batch
    #     if remaining_commands and self.playback_active:
    #         self.window.after(20, lambda: self._schedule_commands(remaining_commands, start_time))
    
    #start playback animation
    def _start_playback_animation(self, duration_ms):
        self.playback_active = True
        self.playback_duration = duration_ms
        self.playback_start_time = time.time()
        
        if self.playback_line:
            self.playback_line.set_visible(True)
            self.playback_line.set_xdata([0])
        
        #update button states
        self.play_current_btn.config(state="disabled")
        self.play_all_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        self._update_playback_animation()
    
    #update playback animation
    def _update_playback_animation(self):
        if not self.playback_active:
            return
        
        elapsed_time = (time.time() - self.playback_start_time) * 1000
        
        if elapsed_time >= self.playback_duration:
            self._stop_playback()
        else:
            if self.playback_line:
                self.playback_line.set_xdata([elapsed_time])
                self.canvas.draw_idle()
            
            self.window.after(50, self._update_playback_animation)
    
    #stop playback
    def _stop_playback(self):
        if self.playback_active:
            self.playback_active = False
            
            if self.playback_line:
                self.playback_line.set_visible(False)
                self.canvas.draw_idle()
        
        #restore button states
        self.play_current_btn.config(state="normal")
        self.play_all_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
    
    #save changes - simplified without format conversion
    def _save_changes(self):
        #push changes back to sequence manager via callback
        if self.save_callback:
            success, message = self.save_callback(self.sequence_data)
            if success:
                self.save_status = "saved"
                self.status_label.config(text=f"status: {self.save_status}")
                
                if self.log_callback:
                    self.log_callback("motion editor changes saved and applied to sequence")
                
                messagebox.showinfo("save successful", "motion curves saved successfully")
            else:
                if self.log_callback:
                    self.log_callback(f"failed to save motion editor changes: {message}")
                messagebox.showerror("save error", f"failed to save changes: {message}")
        else:
            #fallback if no callback provided
            self.save_status = "saved"
            self.status_label.config(text=f"status: {self.save_status}")
            messagebox.showinfo("save successful", "motion curves saved successfully")
    
    #reset current component to default smooth curves
    def _reset_curves(self):
        if not self.current_component:
            return
        
        if messagebox.askyesno("confirm reset", f"reset {self.current_component} to default smooth curves?"):
            keyframes = self._get_current_sequence()
            
            if keyframes:
                #clear control points and regenerate defaults using shared function
                for kf in keyframes:
                    kf['cp_in'] = None
                    kf['cp_out'] = None
                
                ensure_control_points(keyframes, use_smooth_defaults=True)
                self._update_plot()
                self._mark_unsaved()
                
                if self.log_callback:
                    self.log_callback(f"reset {self.current_component} to default curves")
    
    #mark editor as having unsaved changes
    def _mark_unsaved(self):
        self.save_status = "not saved"
        self.status_label.config(text=f"status: {self.save_status}")
    
    #handle window close
    def _on_window_close(self):
        if self.save_status == "not saved":
            response = messagebox.askyesnocancel("unsaved changes", "save changes before closing?")
            
            if response is None:
                return
            elif response:
                self._save_changes()
        
        self._stop_playback()
        plt.close(self.fig)
        self.window.destroy()
        
        if self.log_callback:
            self.log_callback("motion editor closed")
    
    #get updated sequence data for external use (no conversion needed)
    def get_sequence_data(self):
        return copy.deepcopy(self.sequence_data)
    
    #show editor window
    def show(self):
        self.window.lift()
        self.window.focus_force()

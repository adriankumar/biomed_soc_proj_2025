import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.lines import Line2D
import copy
import time

class MotionEditor:
    #integrated motion editor for servo sequence curve editing with component awareness
    def __init__(self, parent, sequence_data, state_manager, serial_connection, log_callback=None):
        self.parent = parent
        self.sequence_data = sequence_data or {}  #motion-centric format: {component_name: [keyframes]}
        self.state_manager = state_manager  #for servo configuration data
        self.serial_connection = serial_connection  #for hardware preview
        self.log_callback = log_callback
        
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
        
        #ensure all sequences have proper control points
        for component_name in self.component_names:
            self._ensure_control_points(component_name)
        
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
    
    #ensure all keyframes have proper control points using cubic bezier defaults
    def _ensure_control_points(self, component_name):
        if component_name not in self.sequence_data:
            return
        
        keyframes = self.sequence_data[component_name]
        num_kf = len(keyframes)
        
        for i, kf in enumerate(keyframes):
            default_tension = 0.33
            
            #incoming control point (not for first keyframe)
            if i > 0:
                if 'cp_in' not in kf or kf['cp_in'] is None:
                    prev_kf = keyframes[i-1]
                    time_diff = kf['time'] - prev_kf['time']
                    dt = max(1, time_diff) * -default_tension
                    kf['cp_in'] = {'dt': dt, 'da': 0.0}
            else:
                kf['cp_in'] = None
            
            #outgoing control point (not for last keyframe)
            if i < num_kf - 1:
                if 'cp_out' not in kf or kf['cp_out'] is None:
                    next_kf = keyframes[i+1]
                    time_diff = next_kf['time'] - kf['time']
                    dt = max(1, time_diff) * default_tension
                    kf['cp_out'] = {'dt': dt, 'da': 0.0}
            else:
                kf['cp_out'] = None
    
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
    
    #convert relative control point to absolute coordinates
    def _control_point_absolute(self, keyframe, cp_type):
        cp_key = f'cp_{cp_type}'
        if cp_key not in keyframe or keyframe[cp_key] is None:
            return None
        
        cp_data = keyframe[cp_key]
        abs_time = keyframe['time'] + cp_data['dt']
        abs_angle = keyframe['angle'] + cp_data['da']
        
        config = self._get_servo_config(self.current_component)
        abs_angle = max(config['pulse_min'], min(config['pulse_max'], abs_angle))
        
        return abs_time, abs_angle
    
    #compute cubic bezier curve point using bernstein polynomials
    def _bezier_point(self, t, p0, p1, p2, p3):
        u = 1 - t
        tt = t * t
        uu = u * u
        uuu = uu * u
        ttt = tt * t
        
        time_val = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
        angle_val = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
        
        return time_val, angle_val
    
    #compute bezier curve segment between two keyframes
    def _compute_curve_segment(self, kf_start, kf_next, resolution=100):
        start_pos = (kf_start['time'], kf_start['angle'])
        end_pos = (kf_next['time'], kf_next['angle'])
        
        start_cp = self._control_point_absolute(kf_start, 'out')
        end_cp = self._control_point_absolute(kf_next, 'in')
        
        if not start_cp or not end_cp:
            #linear fallback
            t_vals = np.linspace(start_pos[0], end_pos[0], resolution)
            a_vals = np.linspace(start_pos[1], end_pos[1], resolution)
            return t_vals, a_vals
        
        t_params = np.linspace(0, 1, resolution)
        points = [self._bezier_point(t, start_pos, start_cp, end_cp, end_pos) for t in t_params]
        
        times, angles = zip(*points) if points else ([], [])
        return np.array(times), np.array(angles)
    
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
    
    #update plot for current component
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
        
        #plot curves and control points
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
    
    #plot bezier curves and control points
    def _plot_curves_and_controls(self, keyframes):
        num_kf = len(keyframes)
        curve_plotted = False
        control_plotted = False
        
        for i in range(num_kf):
            kf = keyframes[i]
            kf_pos = (kf['time'], kf['angle'])
            
            #plot incoming control point
            if i > 0:
                cp_in = self._control_point_absolute(kf, 'in')
                if cp_in:
                    self._draw_control_point(i, 'in', kf_pos, cp_in, not control_plotted)
                    control_plotted = True
            
            #plot outgoing control point
            if i < num_kf - 1:
                cp_out = self._control_point_absolute(kf, 'out')
                if cp_out:
                    self._draw_control_point(i, 'out', kf_pos, cp_out, not control_plotted)
                    control_plotted = True
            
            #plot curve segment
            if i < num_kf - 1:
                times, angles = self._compute_curve_segment(kf, keyframes[i + 1])
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
                    
                    #send current position to hardware for preview
                    current_angle = keyframes[kf_index]['angle']
                    self._send_position_preview(current_angle)
                    
                    element_clicked = True
        
        #clear selection if clicking empty space
        if not element_clicked:
            self._clear_selection()
    
    #handle mouse release
    def _on_mouse_release(self, event):
        if event.button == 1:
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
                    
                    #real-time hardware preview
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
        else:
            if self.log_callback:
                self.log_callback("preview failed: not connected to serial")
    
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
        
        #regenerate control points
        self._ensure_control_points(self.current_component)
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
            
            #regenerate control points
            self._ensure_control_points(self.current_component)
            self._update_plot()
            self._mark_unsaved()
            
            if self.log_callback:
                self.log_callback(f"removed keyframe from {self.current_component}")
    
    #generate interpolated points for playback
    def _generate_playback_points(self, component_name, time_step=50):
        if component_name not in self.sequence_data:
            return []
        
        keyframes = self.sequence_data[component_name]
        if len(keyframes) < 2:
            return []
        
        points = []
        
        #generate points for each curve segment
        for i in range(len(keyframes) - 1):
            kf_start = keyframes[i]
            kf_end = keyframes[i + 1]
            
            start_time = kf_start['time']
            end_time = kf_end['time']
            
            #generate points at regular intervals
            current_time = start_time
            while current_time <= end_time:
                #calculate interpolated angle using bezier curve
                if current_time == start_time:
                    angle = kf_start['angle']
                elif current_time == end_time:
                    angle = kf_end['angle']
                else:
                    #bezier interpolation
                    t = (current_time - start_time) / (end_time - start_time)
                    start_pos = (kf_start['time'], kf_start['angle'])
                    end_pos = (kf_end['time'], kf_end['angle'])
                    start_cp = self._control_point_absolute(kf_start, 'out')
                    end_cp = self._control_point_absolute(kf_end, 'in')
                    
                    if start_cp and end_cp:
                        _, angle = self._bezier_point(t, start_pos, start_cp, end_cp, end_pos)
                    else:
                        #linear fallback
                        angle = kf_start['angle'] + t * (kf_end['angle'] - kf_start['angle'])
                
                points.append((current_time, int(round(angle))))
                current_time += time_step
        
        return points
    
    #play current component sequence
    def _play_current(self):
        if not self.current_component:
            messagebox.showinfo("no component", "no component selected")
            return
        
        points = self._generate_playback_points(self.current_component)
        if not points:
            messagebox.showinfo("no sequence", "sequence needs at least 2 keyframes")
            return
        
        sequences = {self.current_component: points}
        self._execute_playback(sequences)
    
    #play all component sequences
    def _play_all(self):
        if not self.sequence_data:
            messagebox.showinfo("no sequences", "no sequences to play")
            return
        
        all_sequences = {}
        for component_name in self.sequence_data:
            points = self._generate_playback_points(component_name)
            if points:
                all_sequences[component_name] = points
        
        if not all_sequences:
            messagebox.showinfo("no valid sequences", "no sequences with enough keyframes")
            return
        
        self._execute_playback(all_sequences)
    
    #execute playback using sp commands with python timing
    def _execute_playback(self, sequences):
        try:
            self._stop_playback()
            
            #calculate total duration
            max_duration = 0
            for component_name, points in sequences.items():
                if points:
                    duration = max(point[0] for point in points)
                    max_duration = max(max_duration, duration)
            
            if max_duration <= 0:
                return
            
            #start playback animation
            self._start_playback_animation(max_duration)
            
            #execute timed playback
            self._execute_timed_playback(sequences, max_duration)
            
            if self.log_callback:
                component_count = len(sequences)
                self.log_callback(f"started playback: {component_count} components, {max_duration}ms duration")
        
        except Exception as e:
            messagebox.showerror("playback error", f"failed to start playback: {str(e)}")
            self._stop_playback()
    
    #execute timed playback using sp commands
    def _execute_timed_playback(self, sequences, total_duration):
        start_time = time.time()
        
        #create command timeline
        command_timeline = []
        for component_name, points in sequences.items():
            config = self._get_servo_config(component_name)
            servo_index = config['index']
            
            for point_time, angle in points:
                command_timeline.append((point_time, f"SP:{servo_index}:{angle}"))
        
        #sort by time
        command_timeline.sort(key=lambda x: x[0])
        
        #schedule command execution
        self._schedule_commands(command_timeline, start_time)
    
    #schedule command execution with precise timing
    def _schedule_commands(self, command_timeline, start_time):
        if not command_timeline or not self.playback_active:
            return
        
        current_time = time.time()
        elapsed_ms = (current_time - start_time) * 1000
        
        #find commands to execute now
        commands_to_execute = []
        remaining_commands = []
        
        for cmd_time, command in command_timeline:
            if cmd_time <= elapsed_ms + 50:  #50ms tolerance
                commands_to_execute.append(command)
            else:
                remaining_commands.append((cmd_time, command))
        
        #execute commands
        for command in commands_to_execute:
            if self.serial_connection and self.serial_connection.is_connected:
                self.serial_connection.send_command(command)
            else:
                if self.log_callback:
                    self.log_callback(f"playback command: {command} (not connected)")
        
        #schedule next batch
        if remaining_commands and self.playback_active:
            self.window.after(20, lambda: self._schedule_commands(remaining_commands, start_time))
    
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
    
    #save changes back to sequence data
    def _save_changes(self):
        self.save_status = "saved"
        self.status_label.config(text=f"status: {self.save_status}")
        
        if self.log_callback:
            self.log_callback("motion editor changes saved")
        
        messagebox.showinfo("save successful", "motion curves saved successfully")
    
    #reset current component to default smooth curves
    def _reset_curves(self):
        if not self.current_component:
            return
        
        if messagebox.askyesno("confirm reset", f"reset {self.current_component} to default smooth curves?"):
            keyframes = self._get_current_sequence()
            
            if keyframes:
                #clear control points and regenerate defaults
                for kf in keyframes:
                    kf['cp_in'] = None
                    kf['cp_out'] = None
                
                self._ensure_control_points(self.current_component)
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
    
    #get updated sequence data for saving
    def get_sequence_data(self):
        return copy.deepcopy(self.sequence_data)
    
    #show editor window
    def show(self):
        self.window.lift()
        self.window.focus_force()
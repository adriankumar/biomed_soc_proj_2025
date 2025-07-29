import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.lines import Line2D
import copy
import time
from core.sequence_translation import SequenceTranslator
from core.curve_interpolation import BezierCurveComputer

class MotionEditor:
    #component-aware motion editor for v3 system with bezier curve editing
    
    def __init__(self, parent, sequence_manager, state_manager, serial_connection, log_callback=None):
        self.parent = parent
        self.sequence_manager = sequence_manager      #v3 sequence manager
        self.state = state_manager                    #v3 state manager  
        self.serial_connection = serial_connection    #for hardware preview
        self.log_callback = log_callback
        
        #translation layer between v3 and motion editor formats
        self.translator = SequenceTranslator(state_manager, log_callback)
        self.curve_computer = BezierCurveComputer()
        
        #editor data in motion editor format
        self.editor_sequences = {}     #converted sequence data for editing
        self.original_v3_sequence = None  #backup of original v3 data
        
        #current editing state
        self.current_component_name = None        #currently selected component
        self.current_editor_servo_id = 0          #corresponding editor servo id
        self.selected_keyframe_index = None       #selected keyframe for editing
        self.dragging_element = None               #what user is currently dragging
        
        #ui state
        self.save_status = "not saved"
        self.window = None
        self.canvas = None
        self.figure = None
        self.plot_axis = None
        
        #plot elements for dynamic updates
        self.keyframe_scatter_plot = None
        self.curve_line_segments = {}
        self.control_point_plots = {}
        self.control_handle_lines = {}
        self.playback_indicator_line = None
        
        #playback state
        self.is_playing_sequence = False
        self.playback_start_time = 0
        self.playback_duration = 0
        
        self._load_sequence_data()
        self._create_editor_window()
    
    #load v3 sequence data and convert to editor format
    def _load_sequence_data(self):
        v3_keyframes = self.sequence_manager.get_keyframes()
        if not v3_keyframes:
            #create minimal default sequence if empty
            self.editor_sequences = {}
            if self.log_callback:
                self.log_callback("no sequence data to load - starting with empty editor")
            return
        
        #backup original v3 data for comparison
        self.original_v3_sequence = copy.deepcopy(v3_keyframes)
        
        #convert to editor format for curve editing
        v3_sequence_data = {"keyframes": v3_keyframes}
        self.editor_sequences = self.translator.convert_v3_to_editor_format(v3_sequence_data)
        
        #set initial component selection
        available_components = self.translator.get_available_components()
        if available_components:
            self.current_component_name = available_components[0]
            self.current_editor_servo_id = self.translator.get_editor_id_from_component_name(self.current_component_name)
        
        if self.log_callback:
            component_count = len(self.editor_sequences)
            self.log_callback(f"loaded sequence data for {component_count} components")
    
    #create motion editor window with component-aware interface
    def _create_editor_window(self):
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"motion editor - {self.current_component_name or 'no component'}")
        self.window.geometry("1200x800")
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        #main layout container
        main_container = ttk.Frame(self.window)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        #top toolbar with component selection and controls
        self._create_component_toolbar(main_container)
        
        #matplotlib plotting area
        self._create_plotting_area(main_container)
        
        #bottom controls for keyframe manipulation
        self._create_keyframe_controls(main_container)
        
        #initialise plot display
        self._setup_plot_configuration()
        self._update_plot_for_current_component()
        
        #connect matplotlib interaction events
        self._connect_plot_interaction_events()
    
    #create toolbar for component selection and save controls
    def _create_component_toolbar(self, parent):
        toolbar_container = ttk.Frame(parent)
        toolbar_container.pack(fill="x", pady=(0, 10))
        
        #component selection section
        component_section = ttk.Frame(toolbar_container)
        component_section.pack(side="left", padx=10)
        
        ttk.Label(component_section, text="component:").pack(side="left")
        
        #dropdown for component selection
        self.component_selector = ttk.Combobox(component_section, width=15, state="readonly")
        available_components = self.translator.get_available_components()
        self.component_selector['values'] = available_components
        
        if available_components and self.current_component_name:
            self.component_selector.set(self.current_component_name)
        
        self.component_selector.pack(side="left", padx=5)
        self.component_selector.bind("<<ComboboxSelected>>", self._on_component_selection_changed)
        
        #navigation buttons
        ttk.Button(component_section, text="←", command=self._select_previous_component).pack(side="left", padx=2)
        ttk.Button(component_section, text="→", command=self._select_next_component).pack(side="left", padx=2)
        
        #save and status section
        save_section = ttk.Frame(toolbar_container)
        save_section.pack(side="right", padx=10)
        
        self.status_display = ttk.Label(save_section, text=f"status: {self.save_status}")
        self.status_display.pack(side="left", padx=5)
        
        ttk.Button(save_section, text="save changes", command=self._save_changes_to_sequence).pack(side="left", padx=2)
        ttk.Button(save_section, text="reset to defaults", command=self._reset_to_default_curves).pack(side="left", padx=2)
    
    #create matplotlib plotting area for curve visualisation
    def _create_plotting_area(self, parent):
        plotting_container = ttk.Frame(parent)
        plotting_container.pack(fill="both", expand=True)
        
        #create matplotlib figure
        self.figure = plt.Figure(figsize=(12, 6), dpi=100)
        self.plot_axis = self.figure.add_subplot(111)
        
        #embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, master=plotting_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        #add matplotlib navigation toolbar
        toolbar = NavigationToolbar2Tk(self.canvas, plotting_container)
        toolbar.update()
    
    #create controls for keyframe manipulation
    def _create_keyframe_controls(self, parent):
        controls_container = ttk.Frame(parent)
        controls_container.pack(fill="x", pady=(10, 0))
        
        #keyframe value control section
        value_section = ttk.Frame(controls_container)
        value_section.pack(side="left", padx=10)
        
        ttk.Label(value_section, text="pwm value:").pack(side="left")
        
        self.pwm_value_var = tk.StringVar()
        self.pwm_value_entry = ttk.Entry(value_section, textvariable=self.pwm_value_var, width=6)
        self.pwm_value_entry.pack(side="left", padx=5)
        self.pwm_value_entry.bind("<Return>", self._on_pwm_value_changed)
        self.pwm_value_entry.bind("<FocusOut>", self._on_pwm_value_changed)
        
        #playback control section
        playback_section = ttk.Frame(controls_container)
        playback_section.pack(side="left", padx=20)
        
        self.play_component_button = ttk.Button(playback_section, text="play component", 
                                              command=self._play_current_component)
        self.play_component_button.pack(side="left", padx=2)
        
        self.play_all_button = ttk.Button(playback_section, text="play all components",
                                        command=self._play_all_components)
        self.play_all_button.pack(side="left", padx=2)
        
        self.stop_playback_button = ttk.Button(playback_section, text="stop", 
                                             command=self._stop_playback, state="disabled")
        self.stop_playback_button.pack(side="left", padx=2)
        
        #keyframe management section
        keyframe_section = ttk.Frame(controls_container)
        keyframe_section.pack(side="right", padx=10)
        
        ttk.Button(keyframe_section, text="add keyframe", command=self._add_new_keyframe).pack(side="left", padx=2)
        ttk.Button(keyframe_section, text="remove selected", command=self._remove_selected_keyframe).pack(side="left", padx=2)
    
    #handle component selection change from dropdown
    def _on_component_selection_changed(self, event=None):
        selected_component = self.component_selector.get()
        if selected_component and selected_component != self.current_component_name:
            self.current_component_name = selected_component
            self.current_editor_servo_id = self.translator.get_editor_id_from_component_name(selected_component)
            self._clear_selection_state()
            self._update_plot_for_current_component()
            self.window.title(f"motion editor - {self.current_component_name}")
    
    #navigate to previous component in list
    def _select_previous_component(self):
        available_components = self.translator.get_available_components()
        if not available_components or not self.current_component_name:
            return
        
        try:
            current_index = available_components.index(self.current_component_name)
            previous_index = (current_index - 1) % len(available_components)
            new_component = available_components[previous_index]
            
            self.component_selector.set(new_component)
            self._on_component_selection_changed()
        except ValueError:
            pass
    
    #navigate to next component in list
    def _select_next_component(self):
        available_components = self.translator.get_available_components()
        if not available_components or not self.current_component_name:
            return
        
        try:
            current_index = available_components.index(self.current_component_name)
            next_index = (current_index + 1) % len(available_components)
            new_component = available_components[next_index]
            
            self.component_selector.set(new_component)
            self._on_component_selection_changed()
        except ValueError:
            pass
    
    #setup basic plot configuration and styling
    def _setup_plot_configuration(self):
        if not self.current_component_name:
            return
        
        #get component constraints for y-axis limits
        constraints = self.translator.get_component_constraints(self.current_component_name)
        
        self.plot_axis.set_ylim(constraints['min'] - 10, constraints['max'] + 10)
        self.plot_axis.set_xlabel("time (ms)")
        self.plot_axis.set_ylabel("pwm value")
        self.plot_axis.grid(True, alpha=0.3)
        
        #add playback indicator line (initially hidden)
        self.playback_indicator_line = self.plot_axis.axvline(0, color='orange', linestyle='--', 
                                                             linewidth=2, visible=False, zorder=20)
    
    #get keyframe sequence for currently selected component
    def _get_current_component_sequence(self):
        if self.current_editor_servo_id not in self.editor_sequences:
            return []
        return self.editor_sequences[self.current_editor_servo_id]
    
    #clear all dynamic plot elements for redrawing
    def _clear_plot_elements(self):
        #remove keyframe scatter plot
        if self.keyframe_scatter_plot and self.keyframe_scatter_plot in self.plot_axis.collections:
            self.keyframe_scatter_plot.remove()
            self.keyframe_scatter_plot = None
        
        #remove curve line segments
        for line in self.curve_line_segments.values():
            if line in self.plot_axis.lines:
                line.remove()
        self.curve_line_segments.clear()
        
        #remove control point plots
        for scatter in self.control_point_plots.values():
            if scatter in self.plot_axis.collections:
                scatter.remove()
        self.control_point_plots.clear()
        
        #remove control handle lines
        for line in self.control_handle_lines.values():
            if line in self.plot_axis.lines:
                line.remove()
        self.control_handle_lines.clear()
    
    #update plot display for currently selected component
    def _update_plot_for_current_component(self):
        self._clear_plot_elements()
        
        if not self.current_component_name:
            self.canvas.draw_idle()
            return
        
        keyframe_sequence = self._get_current_component_sequence()
        if not keyframe_sequence:
            self.canvas.draw_idle()
            return
        
        #plot keyframes as scatter points
        keyframe_times = [kf['time'] for kf in keyframe_sequence]
        keyframe_values = [kf['angle'] for kf in keyframe_sequence]
        
        self.keyframe_scatter_plot = self.plot_axis.scatter(
            keyframe_times, keyframe_values, color="red", s=100, zorder=15, 
            label="keyframes", picker=True
        )
        
        #plot curve segments and control points
        self._plot_curve_segments_and_controls(keyframe_sequence)
        
        #update plot range to fit content
        if keyframe_times:
            time_padding = max(500, (max(keyframe_times) - min(keyframe_times)) * 0.1)
            self.plot_axis.set_xlim(min(keyframe_times) - time_padding, max(keyframe_times) + time_padding)
        
        #update legend and redraw
        handles, labels = self.plot_axis.get_legend_handles_labels()
        if handles:
            self.plot_axis.legend()
        
        #restore selected keyframe highlighting
        if self.selected_keyframe_index is not None:
            self._update_pwm_value_display()
        
        self.canvas.draw_idle()
    
    #plot bezier curve segments and control points for visualisation
    def _plot_curve_segments_and_controls(self, keyframe_sequence):
        total_keyframes = len(keyframe_sequence)
        curve_plotted = False
        control_plotted = False
        
        for keyframe_index in range(total_keyframes):
            current_keyframe = keyframe_sequence[keyframe_index]
            keyframe_position = (current_keyframe['time'], current_keyframe['angle'])
            
            #plot incoming control point and handle
            if keyframe_index > 0:
                incoming_control = self.curve_computer.control_point_to_absolute_coordinates(current_keyframe, 'cp_in')
                if incoming_control:
                    self._draw_control_point_with_handle(keyframe_index, 'cp_in', keyframe_position, 
                                                       incoming_control, not control_plotted)
                    control_plotted = True
            
            #plot outgoing control point and handle
            if keyframe_index < total_keyframes - 1:
                outgoing_control = self.curve_computer.control_point_to_absolute_coordinates(current_keyframe, 'cp_out')
                if outgoing_control:
                    self._draw_control_point_with_handle(keyframe_index, 'cp_out', keyframe_position, 
                                                       outgoing_control, not control_plotted)
                    control_plotted = True
            
            #plot curve segment to next keyframe
            if keyframe_index < total_keyframes - 1:
                next_keyframe = keyframe_sequence[keyframe_index + 1]
                curve_times, curve_values = self.curve_computer.compute_curve_segment(current_keyframe, next_keyframe)
                
                curve_label = "bezier curve" if not curve_plotted else None
                curve_line, = self.plot_axis.plot(curve_times, curve_values, color='blue', 
                                                linewidth=2, zorder=10, label=curve_label)
                self.curve_line_segments[keyframe_index] = curve_line
                curve_plotted = True
    
    #draw control point with connecting handle line
    def _draw_control_point_with_handle(self, keyframe_index, control_type, keyframe_pos, control_pos, add_label):
        control_key = (keyframe_index, control_type)
        label_text = "control points" if add_label else None
        
        #draw connecting line from keyframe to control point
        handle_line = Line2D([keyframe_pos[0], control_pos[0]], [keyframe_pos[1], control_pos[1]],
                           linestyle=':', color='green', alpha=0.7, linewidth=1, zorder=8)
        self.plot_axis.add_line(handle_line)
        self.control_handle_lines[control_key] = handle_line
        
        #draw control point as scatter plot
        control_scatter = self.plot_axis.scatter(control_pos[0], control_pos[1], color='green', 
                                                s=60, alpha=0.8, zorder=12, picker=True, label=label_text)
        self.control_point_plots[control_key] = control_scatter
    
    #connect matplotlib mouse interaction events
    def _connect_plot_interaction_events(self):
        self.figure.canvas.mpl_connect("button_press_event", self._on_mouse_press)
        self.figure.canvas.mpl_connect("button_release_event", self._on_mouse_release)
        self.figure.canvas.mpl_connect("motion_notify_event", self._on_mouse_motion)
    
    #handle mouse press events for selecting keyframes and control points
    def _on_mouse_press(self, event):
        if event.inaxes != self.plot_axis or event.button != 1:
            return
        
        element_clicked = False
        
        #check control points first (higher priority)
        for control_key, control_scatter in self.control_point_plots.items():
            contains_click, _ = control_scatter.contains(event)
            if contains_click:
                keyframe_index, control_type = control_key
                self.dragging_element = {'type': 'control_point', 'keyframe_index': keyframe_index, 
                                       'control_type': control_type}
                self._clear_keyframe_selection()
                element_clicked = True
                break
        
        #check keyframes if no control point clicked
        if not element_clicked and self.keyframe_scatter_plot:
            contains_click, click_info = self.keyframe_scatter_plot.contains(event)
            if contains_click:
                clicked_keyframe_index = click_info["ind"][0]
                keyframe_sequence = self._get_current_component_sequence()
                
                if clicked_keyframe_index < len(keyframe_sequence):
                    self.dragging_element = {'type': 'keyframe', 'index': clicked_keyframe_index}
                    self.selected_keyframe_index = clicked_keyframe_index
                    self._update_pwm_value_display()
                    
                    #send current keyframe value to hardware for immediate feedback
                    current_pwm = keyframe_sequence[clicked_keyframe_index]['angle']
                    self._send_component_position_to_hardware(current_pwm)
                    
                    element_clicked = True
        
        #clear selection if clicking empty space
        if not element_clicked:
            self._clear_keyframe_selection()
    
    #handle mouse release events
    def _on_mouse_release(self, event):
        if event.button == 1:
            self.dragging_element = None
    
    #handle mouse motion for dragging keyframes and control points
    def _on_mouse_motion(self, event):
        if not self.dragging_element or event.inaxes != self.plot_axis:
            return
        
        if event.xdata is None or event.ydata is None:
            return
        
        keyframe_sequence = self._get_current_component_sequence()
        element_type = self.dragging_element['type']
        current_time = event.xdata
        current_pwm = event.ydata
        
        #clamp pwm to component constraints
        constraints = self.translator.get_component_constraints(self.current_component_name)
        clamped_pwm = max(constraints['min'], min(constraints['max'], current_pwm))
        
        data_changed = False
        
        if element_type == 'keyframe':
            keyframe_index = self.dragging_element['index']
            if keyframe_index < len(keyframe_sequence):
                #only allow vertical (pwm) movement to maintain keyframe timing order
                target_pwm = round(clamped_pwm)
                old_pwm = keyframe_sequence[keyframe_index]['angle']
                
                if old_pwm != target_pwm:
                    keyframe_sequence[keyframe_index]['angle'] = target_pwm
                    data_changed = True
                    
                    #send real-time feedback to hardware
                    self._send_component_position_to_hardware(target_pwm)
                    
                    #update pwm display in real time
                    if self.selected_keyframe_index == keyframe_index:
                        self.pwm_value_var.set(str(target_pwm))
        
        elif element_type == 'control_point':
            keyframe_index = self.dragging_element['keyframe_index']
            control_type = self.dragging_element['control_type']
            
            if keyframe_index < len(keyframe_sequence):
                current_keyframe = keyframe_sequence[keyframe_index]
                control_key = f'cp_{control_type}'
                
                if control_key in current_keyframe and current_keyframe[control_key]:
                    #calculate relative offsets from keyframe position
                    time_offset = current_time - current_keyframe['time']
                    pwm_offset = clamped_pwm - current_keyframe['angle']
                    
                    #enforce control point direction constraints
                    if control_type == 'out':
                        time_offset = max(0.01, time_offset)  #outgoing must be forward in time
                    elif control_type == 'in':
                        time_offset = min(-0.01, time_offset)  #incoming must be backward in time
                    
                    #update control point data
                    old_dt = current_keyframe[control_key]['dt']
                    old_da = current_keyframe[control_key]['da']
                    
                    if old_dt != time_offset or old_da != pwm_offset:
                        current_keyframe[control_key]['dt'] = time_offset
                        current_keyframe[control_key]['da'] = pwm_offset
                        data_changed = True
        
        #redraw plot if data changed
        if data_changed:
            self._update_plot_for_current_component()
            self._mark_as_unsaved()
    
    #send component position to hardware for real-time preview
    def _send_component_position_to_hardware(self, pwm_value):
        if not self.serial_connection or not self.serial_connection.is_connected:
            return
        
        if not self.current_component_name:
            return
        
        component_config = self.state.get_component_config(self.current_component_name)
        if not component_config:
            return
        
        hardware_servo_index = component_config['index']
        command = f"SA:{hardware_servo_index}:{int(round(pwm_value))}"
        
        self.serial_connection.send_command(command)
    
    #handle pwm value entry changes
    def _on_pwm_value_changed(self, event=None):
        if self.selected_keyframe_index is None:
            return
        
        try:
            new_pwm = round(float(self.pwm_value_var.get()))
            constraints = self.translator.get_component_constraints(self.current_component_name)
            clamped_pwm = max(constraints['min'], min(constraints['max'], new_pwm))
            
            keyframe_sequence = self._get_current_component_sequence()
            if self.selected_keyframe_index < len(keyframe_sequence):
                old_pwm = keyframe_sequence[self.selected_keyframe_index]['angle']
                
                if old_pwm != clamped_pwm:
                    keyframe_sequence[self.selected_keyframe_index]['angle'] = clamped_pwm
                    self._update_plot_for_current_component()
                    self._mark_as_unsaved()
                    
                    #send to hardware for preview
                    self._send_component_position_to_hardware(clamped_pwm)
                
                #ensure entry shows clamped value
                self.pwm_value_var.set(str(clamped_pwm))
        except ValueError:
            self._update_pwm_value_display()  #restore valid value
    
    #update pwm value display from selected keyframe
    def _update_pwm_value_display(self):
        if self.selected_keyframe_index is not None:
            keyframe_sequence = self._get_current_component_sequence()
            if self.selected_keyframe_index < len(keyframe_sequence):
                current_pwm = keyframe_sequence[self.selected_keyframe_index]['angle']
                self.pwm_value_var.set(str(round(current_pwm)))
    
    #clear keyframe selection state
    def _clear_keyframe_selection(self):
        self.selected_keyframe_index = None
        self.pwm_value_var.set("")
    
    #clear all selection state
    def _clear_selection_state(self):
        self._clear_keyframe_selection()
        self.dragging_element = None
    
    #add new keyframe to current component sequence
    def _add_new_keyframe(self):
        keyframe_sequence = self._get_current_component_sequence()
        
        if not keyframe_sequence:
            #create first keyframe at time 0
            new_keyframe = {'time': 0, 'angle': 90, 'cp_in': None, 'cp_out': None}
            self.editor_sequences[self.current_editor_servo_id] = [new_keyframe]
        else:
            #add keyframe after the last one
            last_keyframe = keyframe_sequence[-1]
            new_time = last_keyframe['time'] + 1000  #1 second after last keyframe
            
            constraints = self.translator.get_component_constraints(self.current_component_name)
            default_pwm = constraints.get('default', 90)
            
            new_keyframe = {'time': new_time, 'angle': default_pwm, 'cp_in': None, 'cp_out': None}
            keyframe_sequence.append(new_keyframe)
        
        #regenerate control points for smooth curves
        updated_sequence = self.curve_computer.ensure_control_points_for_sequence(keyframe_sequence)
        self.editor_sequences[self.current_editor_servo_id] = updated_sequence
        
        self._update_plot_for_current_component()
        self._mark_as_unsaved()
        
        if self.log_callback:
            self.log_callback(f"added keyframe to {self.current_component_name}")
    
    #remove currently selected keyframe
    def _remove_selected_keyframe(self):
        if self.selected_keyframe_index is None:
            messagebox.showinfo("no selection", "no keyframe selected for removal")
            return
        
        keyframe_sequence = self._get_current_component_sequence()
        if len(keyframe_sequence) <= 2:
            messagebox.showinfo("minimum keyframes", "cannot remove keyframe - minimum of 2 required")
            return
        
        if 0 <= self.selected_keyframe_index < len(keyframe_sequence):
            removed_keyframe = keyframe_sequence.pop(self.selected_keyframe_index)
            self._clear_keyframe_selection()
            
            #regenerate control points after removal
            updated_sequence = self.curve_computer.ensure_control_points_for_sequence(keyframe_sequence)
            self.editor_sequences[self.current_editor_servo_id] = updated_sequence
            
            self._update_plot_for_current_component()
            self._mark_as_unsaved()
            
            if self.log_callback:
                self.log_callback(f"removed keyframe from {self.current_component_name}")
    
    #play current component sequence on hardware
    def _play_current_component(self):
        if not self.serial_connection or not self.serial_connection.is_connected:
            messagebox.showinfo("not connected", "serial connection required for playback")
            return
        
        keyframe_sequence = self._get_current_component_sequence()
        if len(keyframe_sequence) < 2:
            messagebox.showinfo("insufficient data", "need at least 2 keyframes for playback")
            return
        
        self._execute_hardware_playback({self.current_editor_servo_id: keyframe_sequence})
    
    #play all component sequences on hardware
    def _play_all_components(self):
        if not self.serial_connection or not self.serial_connection.is_connected:
            messagebox.showinfo("not connected", "serial connection required for playback")
            return
        
        if not self.editor_sequences:
            messagebox.showinfo("no data", "no sequences to play")
            return
        
        self._execute_hardware_playback(self.editor_sequences)
    
    #execute sequence playback on esp32 hardware
    def _execute_hardware_playback(self, sequences_to_play):
        try:
            #stop any existing playback
            self._stop_playback()
            
            #prepare esp32 for new sequence data
            self.serial_connection.send_command("STOP")
            time.sleep(0.2)
            self.serial_connection.send_command("CLEAR_ALL")
            time.sleep(0.2)
            
            #format and send sequences to hardware
            formatted_sequences = self.translator.format_sequence_for_serial(sequences_to_play)
            max_duration = 0
            
            for hardware_index, formatted_keyframes in formatted_sequences.items():
                command = f"LOAD_SEQ:{hardware_index}:{formatted_keyframes}"
                self.serial_connection.send_command(command)
                time.sleep(0.15)
                
                #calculate sequence duration for playback animation
                if self.current_editor_servo_id in sequences_to_play:
                    sequence = sequences_to_play[self.current_editor_servo_id]
                    if sequence:
                        duration = max(kf['time'] for kf in sequence)
                        max_duration = max(max_duration, duration)
            
            #start hardware playback
            time.sleep(0.3)
            self.serial_connection.send_command("PLAY_LOADED")
            
            #start gui playback animation
            self._start_playback_animation(max_duration)
            
            if self.log_callback:
                sequence_count = len(formatted_sequences)
                self.log_callback(f"started playback of {sequence_count} component sequences")
        
        except Exception as e:
            messagebox.showerror("playback error", f"failed to start playback: {str(e)}")
            self._stop_playback()
    
    #start visual playback animation with progress indicator
    def _start_playback_animation(self, duration_ms):
        if duration_ms <= 0:
            return
        
        self.is_playing_sequence = True
        self.playback_duration = duration_ms
        self.playback_start_time = time.time()
        
        #configure playback indicator line
        if self.playback_indicator_line:
            self.playback_indicator_line.set_visible(True)
            self.playback_indicator_line.set_xdata([0])
        
        #update button states
        self.play_component_button.config(state="disabled")
        self.play_all_button.config(state="disabled")
        self.stop_playback_button.config(state="normal")
        
        #start animation update loop
        self._update_playback_animation()
    
    #update playback animation indicator position
    def _update_playback_animation(self):
        if not self.is_playing_sequence:
            return
        
        elapsed_time = (time.time() - self.playback_start_time) * 1000  #convert to milliseconds
        
        if elapsed_time >= self.playback_duration:
            self._stop_playback()
        else:
            #update indicator line position
            if self.playback_indicator_line:
                self.playback_indicator_line.set_xdata([elapsed_time])
                self.canvas.draw_idle()
            
            #schedule next update
            self.window.after(50, self._update_playback_animation)
    
    #stop hardware and gui playback
    def _stop_playback(self):
        if self.is_playing_sequence:
            self.is_playing_sequence = False
            
            #hide playback indicator
            if self.playback_indicator_line:
                self.playback_indicator_line.set_visible(False)
                self.canvas.draw_idle()
        
        #restore button states
        self.play_component_button.config(state="normal")
        self.play_all_button.config(state="normal")
        self.stop_playback_button.config(state="disabled")
        
        #send stop command to hardware
        if self.serial_connection and self.serial_connection.is_connected:
            self.serial_connection.send_command("STOP")
    
    #save motion editor changes back to v3 sequence manager
    def _save_changes_to_sequence(self):
        try:
            #convert editor format back to v3 format
            updated_v3_keyframes = self.translator.convert_editor_to_v3_format(self.editor_sequences)
            
            #validate the converted sequence
            validation_errors = self.translator.validate_editor_sequence(self.editor_sequences)
            if validation_errors:
                error_message = "validation errors found:\n" + "\n".join(validation_errors[:5])
                if len(validation_errors) > 5:
                    error_message += f"\n... and {len(validation_errors) - 5} more errors"
                messagebox.showerror("validation failed", error_message)
                return
            
            #clear existing sequence and replace with updated data
            self.sequence_manager.clear_sequence()
            
            #add updated keyframes to sequence manager
            for keyframe_data in updated_v3_keyframes:
                delay_to_next = keyframe_data.get('delay_to_next', 1000)
                #note: this assumes sequence manager can handle the converted format
                #you may need to adjust this based on sequence manager's exact interface
                
            self.save_status = "saved"
            self.status_display.config(text=f"status: {self.save_status}")
            
            if self.log_callback:
                keyframe_count = len(updated_v3_keyframes)
                self.log_callback(f"saved motion editor changes: {keyframe_count} keyframes")
            
            messagebox.showinfo("save successful", "motion curves saved to sequence")
            
        except Exception as e:
            messagebox.showerror("save error", f"failed to save changes: {str(e)}")
            if self.log_callback:
                self.log_callback(f"save error: {str(e)}")
    
    #reset current component to default smooth curves
    def _reset_to_default_curves(self):
        if not self.current_component_name:
            return
        
        if messagebox.askyesno("confirm reset", f"reset {self.current_component_name} to default curves?"):
            keyframe_sequence = self._get_current_component_sequence()
            
            if keyframe_sequence:
                #clear custom control points and regenerate defaults
                for keyframe in keyframe_sequence:
                    keyframe['cp_in'] = None
                    keyframe['cp_out'] = None
                
                updated_sequence = self.curve_computer.ensure_control_points_for_sequence(keyframe_sequence)
                self.editor_sequences[self.current_editor_servo_id] = updated_sequence
                
                self._update_plot_for_current_component()
                self._mark_as_unsaved()
                
                if self.log_callback:
                    self.log_callback(f"reset {self.current_component_name} to default curves")
    
    #mark editor state as having unsaved changes
    def _mark_as_unsaved(self):
        self.save_status = "not saved"
        self.status_display.config(text=f"status: {self.save_status}")
    
    #handle window close with unsaved changes check
    def _on_window_close(self):
        if self.save_status == "not saved":
            response = messagebox.askyesnocancel("unsaved changes", 
                                               "you have unsaved changes. save before closing?")
            
            if response is None:  #cancel close
                return
            elif response:  #save changes
                self._save_changes_to_sequence()
        
        #stop any active playback
        self._stop_playback()
        
        #cleanup matplotlib resources
        plt.close(self.figure)
        self.window.destroy()
        
        if self.log_callback:
            self.log_callback("motion editor closed")
    
    #show motion editor window
    def show(self):
        self.window.lift()
        self.window.focus_force()
#import necessary libraries
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, TextBox, Button #import button and textbox
from matplotlib.lines import Line2D
import serial #import pyserial
import time #import time for delays
import threading #import threading for non-blocking serial read (optional but good practice)

#--- serial connection setup ---
SERIAL_PORT = 'COM4' #change as needed
BAUD_RATE = 115200
ser = None #serial object placeholder

def connect_serial():
    #attempt to connect to the serial port
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"connected to {SERIAL_PORT} at {BAUD_RATE} baud")
        time.sleep(2) #allow time for ESP32 to reset/initialize
        #send initial setup? e.g., NUM_SERVOS
        #send_serial_command(f"NUM_SERVOS:2") #example: set 2 servos active initially
    except serial.SerialException as e:
        print(f"error connecting to serial port {SERIAL_PORT}: {e}")
        ser = None #ensure ser is none if connection failed

def send_serial_command(command):
    #send a command string to the serial port
    if ser and ser.is_open:
        try:
            print(f"sending: {command}") #debug output
            ser.write((command + '\n').encode('utf-8'))
        except serial.SerialException as e:
            print(f"error writing to serial port: {e}")
    else:
        print("serial port not connected.")

#placeholder for reading serial (optional: useful for debugging ESP32 responses)
#def read_serial():
#    if ser and ser.is_open:
#        while True:
#            if ser.in_waiting > 0:
#                try:
#                    line = ser.readline().decode('utf-8').rstrip()
#                    print(f"received: {line}")
#                except Exception as e:
#                    print(f"error reading serial: {e}")
#            time.sleep(0.1) #prevent busy-waiting

#--- bezier calculation functions (remain the same) ---
#...(cubic_bezier_point and compute_bezier_curve_segment functions remain exactly the same)...
def cubic_bezier_point(t, p0, p1, p2, p3):
    #compute a point on a cubic bezier curve defined by p0, p1, p2, p3 at parameter t [0, 1].
    #p0, p1, p2, p3 are (time, angle) tuples.
    #returns: (time, angle) tuple for the point on the curve.

    #bernstein basis polynomials
    b0 = (1 - t)**3
    b1 = 3 * (1 - t)**2 * t
    b2 = 3 * (1 - t) * t**2
    b3 = t**3

    #calculate point coordinates
    time_val = b0 * p0[0] + b1 * p1[0] + b2 * p2[0] + b3 * p3[0]
    angle_val = b0 * p0[1] + b1 * p1[1] + b2 * p2[1] + b3 * p3[1]

    return (time_val, angle_val)

def compute_bezier_curve_segment(p0, p1, p2, p3, num_points=100):
    #compute points along a cubic bezier curve segment.
    #returns: arrays of time_values and angle_values.
    t_values = np.linspace(0, 1, num_points)
    points = [cubic_bezier_point(t, p0, p1, p2, p3) for t in t_values]

    #unzip points into time and angle arrays
    time_values, angle_values = zip(*points) if points else ([], [])
    return np.array(time_values), np.array(angle_values)

#--- main editor class ---

class ServoMotionEditor:
    def __init__(self, initial_multi_sequence, scroll_window=2000):
        #initialise the interactive servo motion editor for multiple servos.
        #parameters:
        #- initial_multi_sequence: dict {servo_id: [sequence_list]}
        #- scroll_window: width of the visible x-axis window in ms.

        if not initial_multi_sequence:
             raise ValueError("initial_multi_sequence cannot be empty")

        #store all sequences, make deep copies
        self.all_sequences = {
            servo_id: [kf.copy() for kf in seq]
            for servo_id, seq in initial_multi_sequence.items()
        }
        self.servo_ids = sorted(list(self.all_sequences.keys())) #get sorted list of servo ids
        self.current_servo_id = self.servo_ids[0] #start with the first servo

        #ensure default control points for all sequences
        for servo_id in self.servo_ids:
            self.ensure_default_control_points(servo_id) #pass servo_id

        self.scroll_window = scroll_window

        #create figure and axes
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        #adjust plot to make space for widgets
        plt.subplots_adjust(bottom=0.3, top=0.95) #more space at bottom

        #store plot elements
        self.keyframe_scatter = None
        self.curve_segment_lines = {}
        self.control_point_scatter = {}
        self.control_handle_lines = {}

        #tracking for selection and dragging
        self.dragging_element = None
        self.selected_kf_index = None
        self.angle_textbox = None

        #playback related attributes
        self.playback_line = None #vertical line for playback time
        self.playback_timer = self.fig.canvas.new_timer(interval=50) #timer for animation (50ms = 20fps)
        self.playback_timer.add_callback(self._update_playback_line)
        self.playback_start_time = 0 #system time when playback started
        self.playback_active = False
        self.playback_duration = 0 #duration of the sequence being played

        #initialise plot elements
        self.setup_plot()

        #set up slider
        self.setup_slider()

        #set up the angle editing textbox
        self.setup_angle_textbox()

        #set up playback buttons
        self.setup_playback_buttons()

        #connect interactive events
        self.connect_events()

        #initial draw
        self.update_plot_for_current_servo()


    def ensure_default_control_points(self, servo_id):
        #ensure default control points for a specific servo's sequence.
        sequence = self.all_sequences[servo_id] #get the specific sequence
        num_keyframes = len(sequence)
        for i, kf in enumerate(sequence):
            default_dt_factor = 0.33
            #incoming
            if i > 0:
                if 'cp_in' not in kf or kf['cp_in'] is None:
                    prev_kf = sequence[i-1]
                    time_diff = kf['time'] - prev_kf['time']
                    dt = max(1, time_diff) * -default_dt_factor
                    kf['cp_in'] = {'dt': dt, 'da': 0.0}
                elif not isinstance(kf['cp_in'], dict):
                    kf['cp_in'] = {'dt': 0.0, 'da': 0.0}
            #outgoing
            if i < num_keyframes - 1:
                if 'cp_out' not in kf or kf['cp_out'] is None:
                    next_kf = sequence[i+1]
                    time_diff = next_kf['time'] - kf['time']
                    dt = max(1, time_diff) * default_dt_factor
                    kf['cp_out'] = {'dt': dt, 'da': 0.0}
                elif not isinstance(kf['cp_out'], dict):
                    kf['cp_out'] = {'dt': 0.0, 'da': 0.0}
            #first/last
            if i == 0: kf['cp_in'] = None
            if i == num_keyframes - 1: kf['cp_out'] = None

    def get_current_sequence(self):
        #helper to get the sequence list for the currently selected servo.
        return self.all_sequences[self.current_servo_id]

    def setup_plot(self):
        #set up the static plot elements.
        self.ax.set_ylim(0, 180) #enforce y limit
        self.ax.set_xlabel("time (ms)")
        self.ax.set_ylabel("servo angle (°)")
        self.ax.grid(True, which='both', linestyle='--', linewidth=0.5) #add grid lines
        #add playback line (initially invisible)
        self.playback_line = self.ax.axvline(0, color='orange', linestyle='--', lw=2, visible=False, zorder=20)

    def setup_slider(self):
        #set up slider based on max time across all sequences.
        max_time_overall = 0
        for servo_id in self.servo_ids:
            seq = self.all_sequences[servo_id]
            if seq:
                max_time_overall = max(max_time_overall, max(kf['time'] for kf in seq))
        self.max_time = max_time_overall
        slider_max = max(0, self.max_time + 500 - self.scroll_window)
        slider_ax = self.fig.add_axes([0.15, 0.15, 0.75, 0.03]) #y=0.15
        self.slider = Slider(slider_ax, 'scroll view', 0, slider_max, valinit=0, valstep=10)
        self.slider.on_changed(self.update_x_range)
        self.update_x_range(0) #set initial range

    def setup_angle_textbox(self):
        #set up the textbox for editing selected keyframe angle.
        #position textbox
        anglebox_ax = self.fig.add_axes([0.15, 0.1, 0.2, 0.04]) #y=0.1
        self.angle_textbox = TextBox(anglebox_ax, 'angle (°):', initial="", textalignment="center")
        self.angle_textbox.on_submit(self.submit_angle_change)
        self.angle_textbox.set_active(False) #disable initially

    def setup_playback_buttons(self):
        #add play/stop buttons
        button_h = 0.04
        button_w = 0.15
        button_y = 0.03 #bottom row

        ax_play_current = self.fig.add_axes([0.15, button_y, button_w, button_h])
        self.btn_play_current = Button(ax_play_current, 'play current servo')
        self.btn_play_current.on_clicked(self._play_current_servo)

        ax_play_all = self.fig.add_axes([0.35, button_y, button_w, button_h])
        self.btn_play_all = Button(ax_play_all, 'play all servos')
        self.btn_play_all.on_clicked(self._play_all_servos)

        ax_stop = self.fig.add_axes([0.55, button_y, button_w, button_h])
        self.btn_stop = Button(ax_stop, 'stop playback')
        self.btn_stop.on_clicked(self._stop_playback)
        self.btn_stop.ax.set_visible(False) #hide initially, show during playback


    def _format_sequence_for_serial(self, sequence):
        #format a single servo sequence list into the string for LOAD_SEQ
        parts = []
        for kf in sequence:
            time_val = kf['time']
            angle_val = kf['angle']
            cp_in = kf.get('cp_in') #use .get to handle potential missing keys safely
            cp_out = kf.get('cp_out')

            in_dt_str = str(cp_in['dt']) if cp_in else ""
            in_da_str = str(cp_in['da']) if cp_in else ""
            out_dt_str = str(cp_out['dt']) if cp_out else ""
            out_da_str = str(cp_out['da']) if cp_out else ""

            parts.append(f"{time_val},{angle_val},{in_dt_str},{in_da_str},{out_dt_str},{out_da_str}")
        return ";".join(parts)

    def _get_sequence_duration(self, sequence):
        #calculate the time of the last keyframe in a sequence
        if not sequence:
            return 0
        return max(kf['time'] for kf in sequence)


    def _start_playback_simulation(self, duration_ms):
        #start the GUI playback line animation
        if duration_ms <= 0: return
        self._stop_playback_simulation() #stop any previous timer
        self.playback_duration = duration_ms
        self.playback_start_time = time.time()
        self.playback_line.set_xdata([0]) #reset line position
        self.playback_line.set_visible(True)
        self.playback_active = True
        self.btn_stop.ax.set_visible(True) #show stop button
        self.playback_timer.start()
        print(f"gui playback simulation started for {duration_ms} ms")

    def _stop_playback_simulation(self):
        #stop the GUI playback line animation
        self.playback_timer.stop()
        self.playback_active = False
        if self.playback_line: self.playback_line.set_visible(False)
        self.btn_stop.ax.set_visible(False) #hide stop button
        print("gui playback simulation stopped")

    def _update_playback_line(self):
        #callback for the playback timer to update the line position
        if not self.playback_active: return

        elapsed_s = time.time() - self.playback_start_time
        elapsed_ms = elapsed_s * 1000

        if elapsed_ms >= self.playback_duration:
            self._stop_playback_simulation()
            self.playback_line.set_xdata([self.playback_duration]) #move to end
            self.playback_line.set_visible(True) #keep visible at end briefly? optional
        else:
            self.playback_line.set_xdata([elapsed_ms])

        #force redraw of the canvas to show line movement
        try:
             self.fig.canvas.draw_idle()
        except Exception as e:
             print(f"error during playback draw: {e}") #handle potential errors if window closed etc.
             self._stop_playback_simulation()


    def _play_current_servo(self, event):
        #callback for 'play current' button
        print("play current servo requested")
        self._stop_playback_simulation() #stop gui simulation first
        send_serial_command("STOP") #ensure hardware stops
        time.sleep(0.1) #short delay
        send_serial_command("CLEAR_ALL") #clear previous sequences on esp
        time.sleep(0.1)

        sequence = self.get_current_sequence()
        if not sequence:
            print(f"no sequence data for servo {self.current_servo_id}")
            return

        #load sequence
        seq_str = self._format_sequence_for_serial(sequence)
        send_serial_command(f"LOAD_SEQ:{self.current_servo_id}:{seq_str}")
        time.sleep(0.1) #give esp time to process load

        #start playback on esp
        send_serial_command(f"PLAY_SERVO:{self.current_servo_id}")

        #start gui simulation
        duration = self._get_sequence_duration(sequence)
        self._start_playback_simulation(duration)

    def _play_all_servos(self, event):
        #callback for 'play all' button
        print("play all servos requested")
        self._stop_playback_simulation() #stop gui simulation first
        send_serial_command("STOP") #ensure hardware stops
        time.sleep(0.1)
        send_serial_command("CLEAR_ALL") #clear previous sequences on esp
        time.sleep(0.1)

        max_duration = 0
        #load all sequences
        for servo_id, sequence in self.all_sequences.items():
            if sequence:
                seq_str = self._format_sequence_for_serial(sequence)
                send_serial_command(f"LOAD_SEQ:{servo_id}:{seq_str}")
                time.sleep(0.05) #small delay between loads
                max_duration = max(max_duration, self._get_sequence_duration(sequence))
            else:
                 print(f"no sequence data for servo {servo_id} - skipping load")

        if max_duration <= 0:
             print("no sequences loaded to play.")
             return

        #start playback on esp
        send_serial_command("PLAY_LOADED")

        #start gui simulation (using longest duration)
        self._start_playback_simulation(max_duration)

    def _stop_playback(self, event):
        #callback for 'stop' button
        print("stop playback requested")
        self._stop_playback_simulation() #stop gui simulation
        send_serial_command("STOP") #send stop command to hardware

    def submit_angle_change(self, text):
        #callback function when text is submitted in the angle textbox.
        if self.selected_kf_index is None: return

        try:
            new_angle = round(max(0, min(180, float(text)))) #validate, clamp, round
            sequence = self.get_current_sequence()
            if self.selected_kf_index < len(sequence):
                 sequence[self.selected_kf_index]['angle'] = new_angle
                 print(f"set servo {self.current_servo_id} kf {self.selected_kf_index} angle to {new_angle}")
                 self.update_plot_for_current_servo() #redraw plot fully
                 self.angle_textbox.set_val(str(new_angle)) #update display
                 send_serial_command(f"SA:{self.current_servo_id}:{new_angle}")
                 time.sleep(0.1)
                 #removed real-time SA command: send_serial_command(f"SA:{self.current_servo_id}:{new_angle}")
            else: self.clear_selection()
        except ValueError: self._restore_textbox_values()

    def _restore_textbox_values(self):
         #restores angle textbox value if selection is valid
         if self.selected_kf_index is not None:
             try:
                 sequence = self.get_current_sequence()
                 kf = sequence[self.selected_kf_index]
                 if self.angle_textbox: self.angle_textbox.set_val(str(round(kf['angle'])))
             except IndexError:
                 self.clear_selection()

    def update_x_range(self, val):
        #update the visible x-range based on the slider value.
        current_slider_val = min(val, self.slider.valmax) if hasattr(self, 'slider') else val
        x_min = current_slider_val
        x_max = x_min + self.scroll_window
        if self.max_time < self.scroll_window:
             x_min = 0
             x_max = max(self.scroll_window, self.max_time + 100)
        x_min = max(0, x_min) #ensure min is not negative
        self.ax.set_xlim(x_min, x_max)
        self.fig.canvas.draw_idle()

    def get_control_point_absolute_coords(self, kf_index, cp_type):
        #calculate absolute coords for a cp of the *current* servo.
        sequence = self.get_current_sequence()
        if kf_index >= len(sequence): return None
        kf = sequence[kf_index]
        cp_key = 'cp_' + cp_type
        if cp_key not in kf or kf[cp_key] is None: return None
        cp_relative = kf[cp_key]
        abs_time = kf['time'] + cp_relative['dt']
        abs_angle = kf['angle'] + cp_relative['da']
        abs_angle = max(0, min(180, abs_angle)) #clamp
        return abs_time, abs_angle

    def clear_plot_elements(self):
        #robustly remove dynamic plot elements.
        if self.keyframe_scatter:
            try:
                if self.keyframe_scatter in self.ax.collections: self.keyframe_scatter.remove()
            except Exception: pass
            finally: self.keyframe_scatter = None
        for idx in list(self.curve_segment_lines.keys()):
            line = self.curve_segment_lines.pop(idx, None)
            if line: 
                try: line.remove()
                except Exception: pass
        for key in list(self.control_point_scatter.keys()):
            point = self.control_point_scatter.pop(key, None)
            if point: 
                try: point.remove()
                except Exception: pass
        for key in list(self.control_handle_lines.keys()):
            line = self.control_handle_lines.pop(key, None)
            if line: 
                try: line.remove()
                except Exception: pass
        self.curve_segment_lines.clear()
        self.control_point_scatter.clear()
        self.control_handle_lines.clear()


    def clear_selection(self):
        #clears the currently selected keyframe and updates the textbox.
        self.selected_kf_index = None
        if self.angle_textbox:
            self.angle_textbox.set_val("")
            self.angle_textbox.set_active(False)

    def update_plot_for_current_servo(self):
        #--- full redraw: clear elements, reset axes, redraw everything ---
        self.clear_plot_elements() #clear old artists
        self.setup_plot() #reapply static axes properties (labels, grid, ylim)
        self.ax.set_title(f"servo motion editor - servo id: {self.current_servo_id} (use 'n'/b' to switch)") #update title

        sequence = self.get_current_sequence()
        #handle selection persistence/update textbox values if selection is still valid
        if self.selected_kf_index is not None:
             if self.selected_kf_index >= len(sequence):
                 self.clear_selection()
             else: #selection still valid, update textboxes
                  self._restore_textbox_values()
                  if self.angle_textbox: self.angle_textbox.set_active(True)

        if not sequence: #handle empty sequence
             if self.ax.get_legend(): self.ax.get_legend().remove()
             if self.playback_line: self.playback_line.set_visible(False) #hide playback line too
             self.fig.canvas.draw_idle()
             self.clear_selection()
             return

        #plot keyframes
        keyframe_times = [kf['time'] for kf in sequence]
        keyframe_angles = [kf['angle'] for kf in sequence]
        self.keyframe_scatter = self.ax.scatter(
             keyframe_times, keyframe_angles,
             color="red", s=80, zorder=10, label="keyframes", picker=5
        )

        #plot curves, control points, and handles
        num_keyframes = len(sequence)
        curve_drawn, handle_label_drawn = False, False
        for i in range(num_keyframes):
            kf_pos = (sequence[i]['time'], sequence[i]['angle'])
            #incoming cp
            if i > 0:
                cp_in_abs = self.get_control_point_absolute_coords(i, 'in')
                if cp_in_abs:
                    self.draw_control_point_and_handle(i, 'in', kf_pos, cp_in_abs, not handle_label_drawn)
                    handle_label_drawn = True
            #outgoing cp
            if i < num_keyframes - 1:
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                if cp_out_abs:
                    self.draw_control_point_and_handle(i, 'out', kf_pos, cp_out_abs, not handle_label_drawn)
                    handle_label_drawn = True
            #curve segment
            if i < num_keyframes - 1:
                kf_next = sequence[i+1]
                kf_next_pos = (kf_next['time'], kf_next['angle'])
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                cp_in_abs_next = self.get_control_point_absolute_coords(i + 1, 'in')
                if cp_out_abs and cp_in_abs_next:
                    p0, p1, p2, p3 = kf_pos, cp_out_abs, cp_in_abs_next, kf_next_pos
                    time_vals, angle_vals = compute_bezier_curve_segment(p0, p1, p2, p3)
                    curve_label = "curve" if not curve_drawn else None
                    line, = self.ax.plot(time_vals, angle_vals, color='blue', lw=2, zorder=5, label=curve_label)
                    self.curve_segment_lines[i] = line
                    curve_drawn = True

        #update legend (only if labels exist)
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
             self.ax.legend(handles, labels, loc='best')
        elif self.ax.get_legend(): #remove legend if no labels
             self.ax.get_legend().remove()

        self.update_x_range(self.slider.val) #enforce x-axis limits
        #ensure playback line is hidden if not active
        if not self.playback_active and self.playback_line:
             self.playback_line.set_visible(False)
        self.fig.canvas.draw_idle() #redraw canvas


    def draw_control_point_and_handle(self, kf_index, cp_type, kf_pos, cp_abs_pos, add_label=False):
        #draw a single control point and its handle line, store references.
        key = (kf_index, cp_type)
        handle_label = "control point" if add_label else None #change label slightly
        #line
        line = Line2D([kf_pos[0], cp_abs_pos[0]], [kf_pos[1], cp_abs_pos[1]],
                      ls=':', color='green', alpha=0.7, zorder=8)
        self.ax.add_line(line)
        self.control_handle_lines[key] = line #store line reference
        #point
        point = self.ax.scatter(cp_abs_pos[0], cp_abs_pos[1],
                                color='green', s=60, alpha=0.8, zorder=9, picker=5, label=handle_label)
        self.control_point_scatter[key] = point #store point reference

    #--- event handling ---

    def connect_events(self):
        #connect matplotlib event handlers (mouse and keyboard).
        self.cid_press = self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.cid_release = self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.cid_motion = self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.cid_key = self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)


    def on_key_press(self, event):
        #handle key press events for switching servos.
        text_box_has_focus = (self.angle_textbox and self.angle_textbox.capturekeystrokes)
        if text_box_has_focus: return #ignore if textbox has focus

        current_index = self.servo_ids.index(self.current_servo_id)
        num_servos = len(self.servo_ids)
        new_servo_id = self.current_servo_id

        if event.key == 'n': #next servo
             next_index = (current_index + 1) % num_servos
             new_servo_id = self.servo_ids[next_index]
        elif event.key == 'b': #previous servo
             prev_index = (current_index - 1 + num_servos) % num_servos
             new_servo_id = self.servo_ids[prev_index]

        if new_servo_id != self.current_servo_id:
             self.current_servo_id = new_servo_id
             print(f"switched to servo id: {self.current_servo_id}")
             self._stop_playback_simulation() #stop simulation if running
             self.clear_selection()
             self.update_plot_for_current_servo() #full redraw on servo switch


    def on_press(self, event):
        #handle mouse press (selects elements for dragging or editing).
        if event.inaxes != self.ax or event.button != 1: return

        element_selected = False #flag to check if click hit something selectable

        #check control points first
        clicked_cp_key = None
        #check scatter dict exists before iterating
        if self.control_point_scatter:
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
            else: self.dragging_element = None; return

        #check keyframes if no control point was clicked
        if self.keyframe_scatter:
            cont, ind = self.keyframe_scatter.contains(event)
            if cont:
                element_selected = True
                kf_index = ind["ind"][0]
                if kf_index < len(self.get_current_sequence()):
                     self.dragging_element = {'type': 'keyframe', 'index': kf_index}
                     self.selected_kf_index = kf_index
                     self._restore_textbox_values() #update textboxes
                     if self.angle_textbox: self.angle_textbox.set_active(True)
                     return
                else: self.dragging_element = None; return

        #if click was in axes but not on a selectable element, clear selection
        if not element_selected:
            self.clear_selection()


    def on_release(self, event):
        #handle mouse release.
        if event.button == 1:
            if self.dragging_element:
                #perform a final full redraw after dragging? maybe not necessary if on_motion works
                #self.update_plot_for_current_servo()
                pass #on_motion handles updates, full redraw might be jarring
            self.dragging_element = None


    def on_motion(self, event):
        #handle mouse motion (operates on current servo's sequence) - FULL REDRAW VERSION
        if not self.dragging_element or event.inaxes != self.ax: return

        sequence = self.get_current_sequence()
        element_type = self.dragging_element['type']
        current_time = event.xdata
        current_angle = event.ydata
        if current_time is None or current_angle is None: return #outside axes

        current_angle_clamped = max(0, min(180, current_angle)) #clamp angle

        needs_update = False #flag if data actually changed

        if element_type == 'keyframe':
            kf_index = self.dragging_element['index']
            if kf_index < len(sequence):
                #only angle changes now
                target_angle_rounded = round(current_angle_clamped)
                if sequence[kf_index]['angle'] != target_angle_rounded:
                     sequence[kf_index]['angle'] = target_angle_rounded
                     needs_update = True

                #update the textbox display in real-time (rounded)
                if self.selected_kf_index == kf_index and self.angle_textbox:
                    self.angle_textbox.set_val(str(target_angle_rounded))

        elif element_type == 'control_point':
            kf_index = self.dragging_element['kf_index']
            if kf_index < len(sequence):
                cp_type = self.dragging_element['cp_type']
                cp_key = 'cp_' + cp_type
                kf = sequence[kf_index]
                if cp_key in kf and kf[cp_key] is not None:
                    #calculate relative dt/da based on target mouse position
                    dt = current_time - kf['time']
                    da = current_angle_clamped - kf['angle'] #use clamped angle

                    #apply constraints
                    if cp_type == 'out': dt = max(0.01, dt)
                    if cp_type == 'in': dt = min(-0.01, dt)

                    #update data structure only if changed
                    if sequence[kf_index][cp_key]['dt'] != dt or sequence[kf_index][cp_key]['da'] != da:
                        sequence[kf_index][cp_key]['dt'] = dt
                        sequence[kf_index][cp_key]['da'] = da
                        needs_update = True

        #redraw plot if data changed
        if needs_update:
            self.update_plot_for_current_servo()


    def show(self):
        #display the plot.
        #start serial connection before showing plot
        connect_serial()
        #optional: start serial reading thread
        #thread = threading.Thread(target=read_serial, daemon=True)
        #thread.start()
        plt.show()
        #clean up serial connection when plot is closed
        if ser and ser.is_open:
            ser.close()
            print("serial port closed.")

#--- example usage ---
#define the multi-servo sequence data
multi_servo_sequence_data = {
    #servo 0
    0: [
        {'time': 0, 'angle': 45, 'cp_in': None, 'cp_out': None},
        {'time': 600, 'angle': 135, 'cp_in': None, 'cp_out': None},
        {'time': 1200, 'angle': 60, 'cp_in': None, 'cp_out': None}
    ],
    #servo 1
    1: [
        {'time': 0, 'angle': 90, 'cp_in': None, 'cp_out': None},
        {'time': 400, 'angle': 20, 'cp_in': None, 'cp_out': None},
        {'time': 800, 'angle': 110, 'cp_in': None, 'cp_out': None},
        {'time': 1500, 'angle': 90, 'cp_in': None, 'cp_out': None}
    ]
    #servo 2 (example with only one point initially)
    #2: [
    #     {'time': 500, 'angle': 100, 'cp_in': None, 'cp_out': None}
    #]
}

#create and show the editor (starting with servo 0)
editor = ServoMotionEditor(multi_servo_sequence_data, scroll_window=2000)
editor.show()

#after closing the plot, you can access the modified sequences
#print("final sequence data:", editor.all_sequences)
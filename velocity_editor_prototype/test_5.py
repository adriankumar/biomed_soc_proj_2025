#import necessary libraries
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, TextBox #import textbox
from matplotlib.lines import Line2D
#import matplotlib.patches as patches #patches might not be needed now

#--- bezier calculation functions (remain the same) ---

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
        self.fig, self.ax = plt.subplots(figsize=(12, 8)) #increase height slightly for textbox
        #adjust plot to make space for slider and textbox
        plt.subplots_adjust(bottom=0.2, top=0.95) #adjust bottom and top

        #store plot elements
        self.keyframe_scatter = None
        self.curve_segment_lines = {}
        self.control_point_scatter = {}
        self.control_handle_lines = {}

        #tracking for selection and dragging
        self.dragging_element = None
        self.selected_kf_index = None #index of the keyframe selected for angle editing

        #initialise plot elements for the first servo
        self.setup_plot()

        #set up slider (calculate max_time across all servos)
        self.setup_slider()

        #set up the angle editing textbox
        self.setup_angle_textbox()

        #connect interactive events (mouse and keyboard)
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
        #note: the modifications happen directly on the list inside self.all_sequences

    def get_current_sequence(self):
        #helper to get the sequence list for the currently selected servo.
        return self.all_sequences[self.current_servo_id]

    def setup_plot(self):
        #set up the static plot elements.
        self.ax.set_ylim(0, 180)
        self.ax.set_xlabel("time (ms)")
        self.ax.set_ylabel("servo angle (°)")
        self.ax.grid(True, which='both', linestyle='--', linewidth=0.5) #add grid lines
        #title and legend are updated in update_plot_for_current_servo

    def setup_slider(self):
        #set up slider based on max time across all sequences.
        max_time_overall = 0
        for servo_id in self.servo_ids:
            seq = self.all_sequences[servo_id]
            if seq:
                 #handle sequences with only one keyframe
                max_time_overall = max(max_time_overall, max(kf['time'] for kf in seq))


        self.max_time = max_time_overall
        slider_max = max(0, self.max_time + 500 - self.scroll_window)

        #position slider at the bottom
        slider_ax = self.fig.add_axes([0.15, 0.05, 0.75, 0.03]) #x, y, width, height
        self.slider = Slider(slider_ax, 'scroll view', 0, slider_max, valinit=0, valstep=10)
        self.slider.on_changed(self.update_x_range)
        self.update_x_range(0) #set initial range

    def setup_angle_textbox(self):
         #set up the textbox for editing selected keyframe angle.
         #position textbox below the slider
         textbox_ax = self.fig.add_axes([0.15, 0.1, 0.2, 0.04]) #x, y, width, height
         self.angle_textbox = TextBox(textbox_ax, 'angle:', initial="", textalignment="center")
         self.angle_textbox.on_submit(self.submit_angle_change)
         #disable initially
         self.angle_textbox.set_active(False)

    def submit_angle_change(self, text):
        #callback function when text is submitted in the angle textbox.
        if self.selected_kf_index is None:
            print("no keyframe selected.")
            self.angle_textbox.set_val("") #clear invalid input
            return

        try:
            new_angle = float(text)
            #round to whole number and clamp
            new_angle = round(max(0, min(180, new_angle)))

            sequence = self.get_current_sequence()
            if self.selected_kf_index < len(sequence):
                 #update sequence data
                 sequence[self.selected_kf_index]['angle'] = new_angle
                 print(f"set servo {self.current_servo_id} keyframe {self.selected_kf_index} angle to {new_angle}")
                 #update plot
                 self.update_plot_for_current_servo()
                 #update textbox display to the rounded/clamped value
                 self.angle_textbox.set_val(str(new_angle))
            else:
                 print("selected keyframe index is out of bounds.")
                 self.clear_selection() #clear selection if index is bad

        except ValueError:
            print("invalid angle entered. please enter a number.")
             #restore previous value? or clear? let's clear for now.
            sequence = self.get_current_sequence()
            if self.selected_kf_index < len(sequence):
                current_angle = round(sequence[self.selected_kf_index]['angle'])
                self.angle_textbox.set_val(str(current_angle)) #restore valid text
            else:
                self.angle_textbox.set_val("")

    def update_x_range(self, val):
        #update the visible x-range based on the slider value.
        x_min = self.slider.val
        x_max = x_min + self.scroll_window
        #check if max_time is less than scroll_window, adjust max limit
        if self.max_time < self.scroll_window:
             x_max = max(self.scroll_window, self.max_time + 100)
             x_min = 0
        self.ax.set_xlim(x_min, x_max)
        self.fig.canvas.draw_idle()

    def get_control_point_absolute_coords(self, kf_index, cp_type):
        #calculate absolute coords for a cp of the *current* servo.
        sequence = self.get_current_sequence()
        if kf_index >= len(sequence): return None #index out of bounds
        kf = sequence[kf_index]
        cp_key = 'cp_' + cp_type
        if cp_key not in kf or kf[cp_key] is None:
            return None

        cp_relative = kf[cp_key]
        abs_time = kf['time'] + cp_relative['dt']
        abs_angle = kf['angle'] + cp_relative['da']
        abs_angle = max(0, min(180, abs_angle)) #clamp
        return abs_time, abs_angle

    def clear_plot_elements(self):
        #helper function to remove all dynamic plot elements.
        if self.keyframe_scatter:
            self.keyframe_scatter.remove()
            self.keyframe_scatter = None
        for idx in list(self.curve_segment_lines.keys()):
            self.curve_segment_lines.pop(idx).remove()
        for key in list(self.control_point_scatter.keys()):
             self.control_point_scatter.pop(key).remove()
        for key in list(self.control_handle_lines.keys()):
             self.control_handle_lines.pop(key).remove()
        #clear the dictionaries themselves
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
        #clear existing plot elements and draw the ones for the current servo.
        self.clear_plot_elements()
        self.ax.set_title(f"servo motion editor - servo id: {self.current_servo_id} (use 'n'/'p' to switch)") #update title

        #handle selection persistence/clearing when redrawing
        sequence = self.get_current_sequence()
        if self.selected_kf_index is not None and self.selected_kf_index >= len(sequence):
             print(f"clearing selection - index {self.selected_kf_index} out of bounds for servo {self.current_servo_id}")
             self.clear_selection() #clear selection if invalid after servo switch

        if not sequence: #handle empty sequence for a servo
             self.ax.legend().remove() #remove legend if no data
             self.fig.canvas.draw_idle()
             self.clear_selection() #ensure textbox is clear
             return

        #--- plot keyframes for current servo ---
        keyframe_times = [kf['time'] for kf in sequence]
        keyframe_angles = [kf['angle'] for kf in sequence]
        self.keyframe_scatter = self.ax.scatter(
             keyframe_times, keyframe_angles,
             color="red", s=80, zorder=10, label="keyframes", picker=5
        )

        #--- plot curves, control points, and handles for current servo ---
        num_keyframes = len(sequence)
        #track if we draw any curves to potentially add label later
        curve_drawn = False
        for i in range(num_keyframes):
            kf = sequence[i]
            kf_pos = (kf['time'], kf['angle'])

            #draw incoming cp and handle
            if i > 0:
                cp_in_abs = self.get_control_point_absolute_coords(i, 'in')
                if cp_in_abs:
                    self.draw_control_point_and_handle(i, 'in', kf_pos, cp_in_abs)

            #draw outgoing cp and handle
            if i < num_keyframes - 1:
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                if cp_out_abs:
                    self.draw_control_point_and_handle(i, 'out', kf_pos, cp_out_abs)

            #draw bezier curve segment to the next keyframe
            if i < num_keyframes - 1:
                kf_next = sequence[i+1]
                kf_next_pos = (kf_next['time'], kf_next['angle'])
                cp_out_abs = self.get_control_point_absolute_coords(i, 'out')
                cp_in_abs_next = self.get_control_point_absolute_coords(i + 1, 'in')

                if cp_out_abs and cp_in_abs_next:
                    p0, p1, p2, p3 = kf_pos, cp_out_abs, cp_in_abs_next, kf_next_pos
                    time_vals, angle_vals = compute_bezier_curve_segment(p0, p1, p2, p3)
                    #only add label to the first curve segment for the legend
                    curve_label = "curve" if not curve_drawn else None
                    line, = self.ax.plot(time_vals, angle_vals, color='blue', lw=2, zorder=5, label=curve_label)
                    self.curve_segment_lines[i] = line
                    curve_drawn = True

        #simplified legend handling: let matplotlib handle duplicates
        #only show legend if there's something labeled (keyframes always are if sequence exists)
        self.ax.legend(loc='best')

        self.fig.canvas.draw_idle()


    def draw_control_point_and_handle(self, kf_index, cp_type, kf_pos, cp_abs_pos):
        #draw a single control point and its handle line.
        key = (kf_index, cp_type)
        #handle line
        line = Line2D([kf_pos[0], cp_abs_pos[0]], [kf_pos[1], cp_abs_pos[1]],
                      ls=':', color='green', alpha=0.7, zorder=8)
        self.ax.add_line(line)
        self.control_handle_lines[key] = line
        #control point scatter
        point = self.ax.scatter(cp_abs_pos[0], cp_abs_pos[1],
                                color='green', s=60, alpha=0.8, zorder=9, picker=5) #enable picking
        self.control_point_scatter[key] = point

    #--- event handling ---

    def connect_events(self):
        #connect matplotlib event handlers (mouse and keyboard).
        self.cid_press = self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.cid_release = self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.cid_motion = self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        #add keyboard event handler
        self.cid_key = self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)


    def on_key_press(self, event):
        #handle key press events for switching servos.
        #ignore if focus is on textbox
        if self.angle_textbox and self.angle_textbox.capturekeystrokes:
             return

        current_index = self.servo_ids.index(self.current_servo_id)
        num_servos = len(self.servo_ids)

        if event.key == 'n': #next servo
             next_index = (current_index + 1) % num_servos
             self.current_servo_id = self.servo_ids[next_index]
             print(f"switched to servo id: {self.current_servo_id}") #feedback
             self.clear_selection() #clear selection when switching servo
             self.update_plot_for_current_servo() #redraw plot
        elif event.key == 'p': #previous servo
             prev_index = (current_index - 1 + num_servos) % num_servos
             self.current_servo_id = self.servo_ids[prev_index]
             print(f"switched to servo id: {self.current_servo_id}") #feedback
             self.clear_selection() #clear selection when switching servo
             self.update_plot_for_current_servo() #redraw plot


    def on_press(self, event):
        #handle mouse press (selects elements for dragging or editing).
        if event.inaxes != self.ax or event.button != 1: return

        element_selected = False #flag to check if click hit something selectable

        #check control points first
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
                 #clear keyframe selection if dragging a control point
                 self.clear_selection()
                 return
            else:
                 self.dragging_element = None
                 return

        #check keyframes if no control point was clicked
        if self.keyframe_scatter:
            cont, ind = self.keyframe_scatter.contains(event)
            if cont:
                element_selected = True
                kf_index = ind["ind"][0]
                if kf_index < len(self.get_current_sequence()):
                     self.dragging_element = {'type': 'keyframe', 'index': kf_index}
                     #set selected keyframe for angle editing
                     self.selected_kf_index = kf_index
                     sequence = self.get_current_sequence()
                     current_angle = round(sequence[kf_index]['angle'])
                     self.angle_textbox.set_val(str(current_angle))
                     self.angle_textbox.set_active(True)
                     #highlight selected keyframe? (optional enhancement)
                     return
                else:
                     self.dragging_element = None
                     return

        #if click was in axes but not on a selectable element, clear selection
        if not element_selected:
            self.clear_selection()


    def on_release(self, event):
        #handle mouse release.
        if event.button == 1:
            self.dragging_element = None
            #don't clear selection on release, only on click away or servo switch

    def on_motion(self, event):
        #handle mouse motion (operates on current servo's sequence).
        if not self.dragging_element or event.inaxes != self.ax: return

        sequence = self.get_current_sequence()
        element_type = self.dragging_element['type']
        current_time = event.xdata
        current_angle = event.ydata
        current_angle = max(0, min(180, current_angle)) #clamp

        if element_type == 'keyframe':
            kf_index = self.dragging_element['index']
            if kf_index < len(sequence):
                #update angle in data structure
                sequence[kf_index]['angle'] = current_angle
                #update the textbox display in real-time (rounded)
                if self.selected_kf_index == kf_index and self.angle_textbox:
                    self.angle_textbox.set_val(str(round(current_angle)))
                #redraw everything to show updated curve/positions
                self.update_plot_for_current_servo()

        elif element_type == 'control_point':
            kf_index = self.dragging_element['kf_index']
            if kf_index < len(sequence):
                cp_type = self.dragging_element['cp_type']
                cp_key = 'cp_' + cp_type
                kf = sequence[kf_index]
                if cp_key in kf and kf[cp_key] is not None:
                    dt = current_time - kf['time']
                    da = current_angle - kf['angle']
                    #constraints
                    if cp_type == 'out': dt = max(0.01, dt)
                    if cp_type == 'in': dt = min(-0.01, dt)
                    #update data structure
                    sequence[kf_index][cp_key]['dt'] = dt
                    sequence[kf_index][cp_key]['da'] = da
                    #redraw everything
                    self.update_plot_for_current_servo()

    def show(self):
        #display the plot.
        plt.show()

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
    ],
}

#create and show the editor (starting with servo 0)
editor = ServoMotionEditor(multi_servo_sequence_data, scroll_window=2000)
editor.show()

#after closing the plot, you can access the modified sequences
#print("final sequence data:", editor.all_sequences)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
import random

class ServoSequencePlot:
    #constants for the plot
    SMOOTHING_FACTOR = 0.02 #match ESP32's smoothing factor (0.02 = 2% of new value, 98% of old value)
    UPDATE_INTERVAL = 0.01 #10ms update interval in seconds (100Hz)
    
    def __init__(self, parent, model):
        #store references
        self.model = model
        self.parent = parent
        self.window = None
        self.fig = None
        self.ax = None
        self.canvas = None
        
        #generate random colors for each servo
        self.colors = self._generate_colors(len(model.SERVO_CONFIG))
    
    #random colours
    def _generate_colors(self, num_colors):
        colors = []
        for _ in range(num_colors):
            r = random.random()
            g = random.random()
            b = random.random()
            colors.append((r, g, b))
        return colors
    
    #shoq sequence plot window
    def show(self):
        if not self.model.sequence:
            return  #no sequence to plot
        
        if self.window is None or not tk.Toplevel.winfo_exists(self.window):
            #create new window
            self.window = tk.Toplevel(self.parent)
            self.window.title("Servo Sequence Plot")
            self.window.geometry("800x600")
            self.window.minsize(600, 400)
            
            #create matplotlib figure and canvas
            self.fig = Figure(figsize=(8, 6), dpi=100)
            self.ax = self.fig.add_subplot(111)
            
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.window)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            #update the plot
            self._update_plot()
            
            #bind close event
            self.window.protocol("WM_DELETE_WINDOW", self.close)
        else:
            #window already exists, bring to front
            self.window.lift()
            self._update_plot()  #refresh the plot
    
    #handle close
    def close(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self.window.destroy()
            self.window = None
    
    #update plot with current sequence data
    def _update_plot(self):
        if not self.model.sequence:
            if self.ax:
                self.ax.clear()
                self.ax.text(0.5, 0.5, "No sequence data available", 
                            horizontalalignment='center', verticalalignment='center')
                self.canvas.draw()
            return
        
        #clear the plot
        self.ax.clear()
        
        #calculate time points for each step
        time_points = [0]
        total_time = 0
        for step in self.model.sequence:
            total_time += step["delay"] / 1000.0  #convert ms to seconds
            time_points.append(total_time)
        
        #for each servo, plot the angles over time
        for servo_idx, servo_config in enumerate(self.model.SERVO_CONFIG):
            servo_id = servo_config["id"]
            servo_name = servo_config["name"]
            
            #extract angles for this servo from each step
            angles = []
            for step in self.model.sequence:
                for servo in step["servos"]:
                    if servo["id"] == servo_id:
                        angles.append(servo["position"])
                        break
            
            if not angles: #skip if no angles for this servo
                continue
                
            #generate smoothed curve using the ESP32 smoothing algorithm
            smooth_times, smooth_angles = self._generate_smoothed_curve(time_points[:-1], angles)
            
            #plot the smoothed curve
            color = self.colors[servo_idx]
            self.ax.plot(smooth_times, smooth_angles, '-', color=color, label=servo_name)
            
            #mark the actual sequence points
            self.ax.plot(time_points[:-1], angles, 'o', color=color, markersize=5)
        
        #set labels and title
        self.ax.set_xlabel('Time (seconds)')
        self.ax.set_ylabel('Angle (degrees)')
        self.ax.set_title('Servo Sequence Plot')
        self.ax.set_ylim(0, 180)
        self.ax.grid(True)
        self.ax.legend()
        
        #update the canvas
        self.fig.tight_layout()
        self.canvas.draw()
    
    #generate smooth curve estimation to reflect true transition of sequence steps
    def _generate_smoothed_curve(self, time_points, angles):
        if not angles or len(angles) < 2 or not time_points:
            return time_points, angles
        
        smooth_times = []
        smooth_angles = []
        
        #start with the first point
        smooth_times.append(time_points[0])
        smooth_angles.append(angles[0])
        
        for i in range(len(angles) - 1):
            start_time = time_points[i]
            end_time = time_points[i+1] if i+1 < len(time_points) else start_time + 0.5
            start_angle = angles[i]
            target_angle = angles[i+1]
            
            #calculate how many update steps would occur during this interval
            duration = end_time - start_time
            num_steps = max(1, int(duration / self.UPDATE_INTERVAL))
            
            #generate intermediate points using smoothing algorithm
            current_angle = start_angle
            
            for step in range(1, num_steps + 1):
                t = start_time + step * duration / num_steps
                
                #apply ESP32 smoothing formula
                current_angle = (target_angle * self.SMOOTHING_FACTOR) + (current_angle * (1.0 - self.SMOOTHING_FACTOR))
                
                smooth_times.append(t)
                smooth_angles.append(current_angle)
        
        return smooth_times, smooth_angles
    
    #update plot if window is open
    def update(self):
        if self.window and tk.Toplevel.winfo_exists(self.window):
            self._update_plot()
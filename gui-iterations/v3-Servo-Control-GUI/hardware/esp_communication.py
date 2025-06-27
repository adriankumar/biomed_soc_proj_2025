import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import threading
import psutil
import os
from hardware.servo_config import BAUD_RATE, SERIAL_TIMEOUT, MAX_SERVOS
from core.event_system import publish, Events

class CPUMonitor:
    #monitors cpu usage for gui application process only
    def __init__(self, gui_callback):
        self.gui_callback = gui_callback
        self.monitoring_active = False
        self.monitor_thread = None
        self.current_process = None
        self.cpu_percentage = 0.0
        
        #initialise process monitoring
        try:
            self.current_process = psutil.Process(os.getpid())
            self.monitoring_active = True
        except Exception:
            self.monitoring_active = False
    
    #start cpu monitoring in background thread
    def start_monitoring(self):
        if self.monitoring_active and not (self.monitor_thread and self.monitor_thread.is_alive()):
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    #stop cpu monitoring
    def stop_monitoring(self):
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
    
    #background monitoring loop for cpu usage
    def _monitor_loop(self):
        while self.monitoring_active:
            try:
                if self.current_process and self.current_process.is_running():
                    #get cpu percentage for gui process only
                    cpu_percent = self.current_process.cpu_percent(interval=1.0)
                    self.cpu_percentage = round(cpu_percent, 1)
                    
                    #thread-safe gui update
                    if self.gui_callback:
                        self.gui_callback(self.cpu_percentage)
                else:
                    self.cpu_percentage = 0.0
                    
                #wait before next measurement
                time.sleep(2.0)
                
            except Exception:
                #continue monitoring even if individual measurement fails
                self.cpu_percentage = 0.0
                time.sleep(3.0)
    
    #get current cpu usage
    def get_cpu_usage(self):
        return self.cpu_percentage
    
    #check if monitoring is available
    def is_monitoring_available(self):
        return self.monitoring_active


class SerialConnection:
    #manages direct serial communication with esp32 and cpu monitoring
    def __init__(self, parent, log_callback):
        self.frame = ttk.LabelFrame(parent, text="serial connection & system monitor")
        self.log_callback = log_callback
        
        #connection state
        self.serial_connection = None
        self.servo_config_sent = False
        
        #gui variables
        self.port_var = tk.StringVar()
        self.baudrate_var = tk.IntVar(value=BAUD_RATE)
        
        #cpu monitoring
        self.cpu_monitor = CPUMonitor(self._on_cpu_update)
        self.cpu_usage_text = "CPU: --"
        
        self._create_ui()
        
        #start cpu monitoring
        self.cpu_monitor.start_monitoring()
    
    #thread-safe callback for cpu usage updates
    def _on_cpu_update(self, cpu_percent):
        #schedule gui update on main thread
        self.frame.after(0, self._update_cpu_display, cpu_percent)
    
    #update cpu display on main thread
    def _update_cpu_display(self, cpu_percent):
        if cpu_percent > 0:
            self.cpu_usage_text = f"CPU: {cpu_percent}%"
        else:
            self.cpu_usage_text = "CPU: --"
        
        #update status display with current connection and cpu info
        self._update_status_display()
    
    #create connection interface with cpu monitoring
    def _create_ui(self):
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="x", padx=10, pady=10)
        
        #port selection
        ttk.Label(main_frame, text="port:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.port_combo = ttk.Combobox(main_frame, textvariable=self.port_var, width=12)
        self.port_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Button(main_frame, text="refresh", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=2)
        
        #baud rate
        ttk.Label(main_frame, text="baud rate:").grid(row=0, column=3, padx=5, pady=2, sticky="w")
        
        self.baud_combo = ttk.Combobox(main_frame, values=[9600, 19200, 38400, 57600, 115200], 
                                     textvariable=self.baudrate_var, width=8)
        self.baud_combo.grid(row=0, column=4, padx=5, pady=2)
        
        #connection button
        self.connect_button = ttk.Button(main_frame, text="connect", command=self.toggle_connection)
        self.connect_button.grid(row=0, column=5, padx=10, pady=2)
        
        #status display with cpu monitoring
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(status_frame, text="status:").pack(side="left", padx=5)
        
        self.status_label = ttk.Label(status_frame, text="disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)
        
        #cpu usage display
        self.cpu_label = ttk.Label(status_frame, text=self.cpu_usage_text, foreground="blue")
        self.cpu_label.pack(side="right", padx=5)
        
        self.refresh_ports()
    
    #update combined status display
    def _update_status_display(self):
        #update cpu label separately
        if hasattr(self, 'cpu_label'):
            self.cpu_label.config(text=self.cpu_usage_text)
    
    #refresh available serial ports
    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo["values"] = ports
        
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])
        
        self.log_callback(f"found {len(ports)} available port(s)" if ports else "no serial ports found")
    
    #toggle connection state
    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()
    
    #establish serial connection
    def connect(self):
        selected_port = self.port_var.get()
        if not selected_port:
            messagebox.showwarning("warning", "no port selected")
            return False
        
        try:
            self.serial_connection = serial.Serial(
                port=selected_port, 
                baudrate=self.baudrate_var.get(), 
                timeout=SERIAL_TIMEOUT
            )
            time.sleep(2)  #connection stabilisation
            
            self._update_ui_connected(selected_port)
            publish(Events.CONNECTION_CHANGED, True)
            
            #send servo configuration
            if not self.servo_config_sent:
                if self.send_command(f"NUM_SERVOS:{MAX_SERVOS}"):
                    self.servo_config_sent = True
                    self.log_callback(f"sent servo configuration: {MAX_SERVOS} servos")
            
            return True
            
        except Exception as e:
            messagebox.showerror("connection error", str(e))
            self.log_callback(f"connection error: {str(e)}")
            return False
    
    #close serial connection
    def disconnect(self):
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
        
        self._update_ui_disconnected()
        publish(Events.CONNECTION_CHANGED, False)
        self.log_callback("disconnected from serial port")
        return True
    
    #send command directly to esp32
    def send_command(self, command):
        if not self.is_connected or not self.serial_connection:
            return False
        
        try:
            if not command.endswith('\n'):
                command += '\n'
            
            self.serial_connection.write(command.encode('utf-8'))
            self.log_callback(f"sent: {command.strip()}")
            return True
            
        except Exception as e:
            self.log_callback(f"error sending command: {str(e)}")
            return False
    
    #send multiple commands with timing
    def send_batch_commands(self, commands, delay_between=0.005):
        if not commands or not self.is_connected:
            return 0
        
        success_count = 0
        for command in commands:
            if self.send_command(command):
                success_count += 1
                time.sleep(delay_between)
            else:
                break
        
        return success_count
    
    #update ui for connected state
    def _update_ui_connected(self, port):
        self.status_label.config(text=f"connected to {port}", foreground="green")
        self.connect_button.config(text="disconnect")
        self.log_callback(f"connected to {port}")
    
    #update ui for disconnected state
    def _update_ui_disconnected(self):
        self.status_label.config(text="disconnected", foreground="red")
        self.connect_button.config(text="connect")
    
    #check connection status
    @property
    def is_connected(self):
        return self.serial_connection is not None and self.serial_connection.is_open
    
    #cleanup resources including cpu monitoring
    def cleanup(self):
        #stop cpu monitoring
        self.cpu_monitor.stop_monitoring()
        
        #close serial connection
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
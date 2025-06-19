import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time

class SerialConnection:
    def __init__(self, parent, send_callback=None, num_servos=5):
        #create the main frame
        self.frame = ttk.LabelFrame(parent, text="Serial Connection")
        
        #callback for logging - all serial connection stuff will be logged in the console i.e connections, error etc.
        self.send_callback = send_callback

        self.num_servos = num_servos
        
        #connection state
        self.serial_connection = None #serial object that communicates to actual port
        self.is_connected = False #connect button will change to disconnect if is_connected = True and back to connect if False
        
        #serial port settings
        self.port_var = tk.StringVar()
        self.baudrate_var = tk.IntVar(value=115200)
        
        #create ui elements
        self._create_ui()
    
    #-----------------------------------------------------------------------
    #ui creation and setup
    #-----------------------------------------------------------------------
    def _create_ui(self):
        #port selection row
        port_frame = ttk.Frame(self.frame)
        port_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(port_frame, text="Port:").grid(row=0, column=0, padx=5, pady=5)
        
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, padx=5, pady=5)
        
        self.refresh_button = ttk.Button(port_frame, text="Refresh", 
                                       command=self.refresh_ports)
        self.refresh_button.grid(row=0, column=2, padx=5, pady=5)
        
        #baud rate selection
        ttk.Label(port_frame, text="Baud Rate:").grid(row=0, column=3, padx=5, pady=5)
        
        baud_rates = [9600, 19200, 38400, 57600, 115200] #add more here if we find specific rate used in our microcontroller
        self.baud_combo = ttk.Combobox(port_frame, values=baud_rates, 
                                     textvariable=self.baudrate_var, width=8)
        self.baud_combo.grid(row=0, column=4, padx=5, pady=5)
        
        #connect/disconnect button
        self.connect_button = ttk.Button(port_frame, text="Connect", 
                                       command=self.toggle_connection)
        self.connect_button.grid(row=0, column=5, padx=5, pady=5)
        
        #status display
        status_frame = ttk.Frame(self.frame)
        status_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(status_frame, text="Status:").pack(side="left", padx=5)
        
        self.status_label = ttk.Label(status_frame, text="Disconnected", foreground="red")
        self.status_label.pack(side="left", padx=5)
        
        #refresh port list on startup
        self.refresh_ports()
    
    #-----------------------------------------------------------------------
    #port management functions
    #-----------------------------------------------------------------------
    def refresh_ports(self):
        #find available serial ports
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        self.port_combo["values"] = ports
        
        if ports and not self.port_var.get():
            self.port_var.set(ports[0]) #initally set to first port in the list
            
        #log message
        if self.send_callback:
            if ports:
                self.send_callback(f"Found {len(ports)} available port(s)")
            else:
                self.send_callback("No serial ports found")
    
    #connect/disconnect to serial
    def toggle_connection(self):
        if not self.is_connected:
            self.connect()
        else:
            self.disconnect()
    
    def connect(self):
        selected_port = self.port_var.get()
        
        if not selected_port:
            messagebox.showwarning("Warning", "No port selected")
            return False
        
        try:
            #create serial connection
            self.serial_connection = serial.Serial(
                port=selected_port,
                baudrate=self.baudrate_var.get(),
                timeout=1
            )
            
            #allow time for connection to stabilise
            time.sleep(2)
            
            self.is_connected = True
            
            #update ui
            self.status_label.config(text=f"Connected to {selected_port}", foreground="green")
            self.connect_button.config(text="Disconnect")
            
            #notify callback if provided
            if self.send_callback:
                self.send_callback(f"Connected to {selected_port}")

            self.send_command(f"NUM_SERVOS:{self.num_servos}") #send num servos everytime we connect to serial
            
            return True
            
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.is_connected = False
            self.serial_connection = None
            
            if self.send_callback:
                self.send_callback(f"Connection error: {str(e)}")
                
            return False
    
    def disconnect(self):
        if self.serial_connection:
            #close the connection
            self.serial_connection.close()
            self.serial_connection = None
            
        self.is_connected = False
        
        #update ui
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_button.config(text="Connect")
        
        #notify callback
        if self.send_callback:
            self.send_callback("Disconnected from serial port")
            
        return True
    
    #-----------------------------------------------------------------------
    #serial command processing
    #-----------------------------------------------------------------------
    def send_command(self, command):
        if not self.is_connected or not self.serial_connection:
            return False
            
        try:
            #add newline to command if needed
            if not command.endswith('\n'):
                command += '\n'
                
            #write to serial port
            self.serial_connection.write(command.encode('utf-8'))
            
            if self.send_callback:
                self.send_callback(f"Sent: {command.strip()}") #log on console
                
            return True
                
        except Exception as e:
            if self.send_callback:
                self.send_callback(f"Error sending command: {str(e)}")
                
            return False
    
    def get_connection(self):
        #return the serial connection object if needed externally
        return self.serial_connection if self.is_connected else None
import tkinter as tk
from servo_controller import ServoController

#run this file to open GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = ServoController(root)
    root.mainloop()
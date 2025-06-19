#main entry point for servo control system

from config_dialog import ConfigDialog
from gui.main_window import ServoControlGUI

def main():
    #show configuration dialog
    config_dialog = ConfigDialog()
    config_data = config_dialog.show_dialog()
    
    #start main application
    app = ServoControlGUI(config_data)
    app.run()

if __name__ == "__main__":
    main()
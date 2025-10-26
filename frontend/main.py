import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from modules.greephouse import GreenhouseDesktop, setup_logging
import logging

def main():
    setup_logging()
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = GreenhouseDesktop()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
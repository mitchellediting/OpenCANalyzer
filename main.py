import sys
import os

# Ensure the current directory is in the path so imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ui_main import MainWindow, QApplication

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

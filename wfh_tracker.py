import time
import sys
import sqlite3
import PyQt5.QtCore as QtCore
import os
import ctypes
from pywifi import PyWiFi
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QPushButton
from PyQt5.QtCore import Qt, QTimer
from datetime import datetime,  timedelta


ctypes.windll.shcore.SetProcessDpiAwareness(2)

# Improved DPI handling
if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

current_month = datetime.now().strftime('%Y-%m')  # Format as YYYY-MM
str_month = datetime.now().strftime(r'%b')

# SQLite Database Setup
DB_FILE = os.getenv("SQLITE_DB_PATH")
OFFICE_WIFI_SSID = os.getenv('OFFICE_WIFI_SSID')

def setup_database():
    """Create the SQLite database and table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            action TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_action(action):
    """Log the action (WFH or Office) for the current day in the database."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Insert or update the log for today
    cursor.execute("""
        INSERT INTO work_log (date, action) VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET action = excluded.action
    """, (today, action))
    conn.commit()
    conn.close()
 

def get_today_action():
    """Retrieve today's action from the database."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT action FROM work_log WHERE date = ?", (today,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_wfh_count():
    query = f"SELECT COUNT(*) FROM work_log WHERE action = 'WFH' AND strftime('%Y-%m', date) = '{current_month}'"
    
    # Connect to the SQLite database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(query)
    count = cursor.fetchone()[0]
    conn.close()
    
    return count

def get_wfh_dates_for_month(year, month):
    """Fetch WFH dates from the database for a specific month."""
    conn = sqlite3.connect("work_log.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date 
        FROM work_log 
        WHERE action = 'WFH' AND strftime('%Y-%m', date) = ?
    """, (f"{year}-{month:02}",))
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return [datetime.strptime(date, '%Y-%m-%d').day for date in dates]  # Extract day of the month

def get_wfh_dates_for_previous_month():
    """Fetch WFH dates for the previous month."""
    today = datetime.today()
    first_day_this_month = today.replace(day=1)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    return last_day_previous_month.year, last_day_previous_month.month, get_wfh_dates_for_month(last_day_previous_month.year, last_day_previous_month.month)



# Widget Class
class WorkTrackerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.old_pos = None 
        self.scale_factor = self.get_scale_factor()
        self.initUI()
        # Initialize the database
        setup_database()
        # Start WiFi check timer (every 10 minutes)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scan_wifi_windows)
        self.timer.start(30 * 60 * 1000)  # 10 minutes in milliseconds
        # Highlight today's selection
        self.highlight_today_action()



    def initUI(self):
        # Set up the window
        self.setWindowFlags(Qt.BypassWindowManagerHint | Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnBottomHint)
        self.setWindowTitle("WFH Tracker")

        # Add a close button to the top-right corner
        self.close_button = QPushButton("✕", self)
        button_size = int(30 * self.scale_factor)
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: red;
                color: white;
                font-size: {int(14 * self.scale_factor)}px;
                border: none;
                border-radius: {int(10 * self.scale_factor)}px;
                padding: {int(2 * self.scale_factor)}px;
            }}
            QPushButton:hover {{
                background-color: darkred;
            }}
        """)

        self.close_button.setFixedSize(button_size, button_size)  # Small fixed size for the button
        self.close_button.move(self.width() - button_size, 10)  # Position it at the top-right corner (adjust as needed)
        self.close_button.clicked.connect(lambda: sys.exit(0))  # Connect the button to the close() method

        # Get the screen geometry and position the widget in the top-right corner
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        widget_width =  int(200 * self.scale_factor)  # Adjust based on your widget size
        widget_height = int( 300 * self.scale_factor)
        xy_padding_from_top_right = int(30 * self.scale_factor)
        self.setGeometry(screen_geometry.width() - widget_width - xy_padding_from_top_right,
                        xy_padding_from_top_right,  
                        widget_width,  # Widget width
                        widget_height)  # Widget he8ight
        screen = QApplication.primaryScreen()
        screen.geometryChanged.connect(self.position_widget)
        
        self.setStyleSheet("""
            WorkTrackerWidget {
                background-color: rgba(0, 210, 252, 0);  
                border-radius: 50px;                  /* Rounded corners */
            }
        """)
        # Layout
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        bottom_layout = QVBoxLayout()
        
        # Create labels for WFH dates
        self.wfh_count_label = QLabel("")  # Default text
        self.current_month_label = QLabel("")
        self.previous_month_label = QLabel("")

        self.current_month_label.setStyleSheet(f"font-size: {int(12 * self.scale_factor)}px; color: white;")
        self.previous_month_label.setStyleSheet(f"font-size: {int(12 * self.scale_factor)}px; color: white;")

        bottom_layout.addWidget(self.current_month_label)
        bottom_layout.addWidget(self.previous_month_label)


        self.update_wfh_count()
        self.wfh_count_label.setAlignment(Qt.AlignLeft)  # Center the text
        self.wfh_count_label.setStyleSheet(f"""font-size: {int(20 * self.scale_factor)}px; 
                                           color: white;
                                            background-color: rgba(0, 210, 252, 0);  /* Set a solid background color */
                                           """)  
        # self.wfh_count_label.setStyleSheet("color: white;")  # Customize font and color
        self.wfh_count_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.wfh_count_label.setWordWrap(True)  # Enable text wrapping if needed
        self.wfh_count_label.adjustSize() 

        # Top layout for close button and label
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.wfh_count_label, alignment=Qt.AlignLeft)  # Center the label
        top_layout.addWidget(self.close_button, alignment=Qt.AlignRight)  # Right-align the close button


        # Buttons
        self.wfh_button = QPushButton("Home")
        self.office_button = QPushButton("Office")

        button_width = int(200 * self.scale_factor)
        button_height = int(50 * self.scale_factor)
        self.wfh_button.setMinimumSize(button_width, button_height)
        self.office_button.setMinimumSize(button_width, button_height)

        font = self.font()
        font.setPointSize(int(16 * self.scale_factor / 1.5))  # Scale font size but not linearly
        # font.setPointSize(16)  # Set font size (e.g., 16 points)

        self.wfh_button.setFont(font)
        self.office_button.setFont(font)

        self.wfh_button.clicked.connect(lambda: self.log_and_highlight("WFH"))
        self.office_button.clicked.connect(lambda: self.log_and_highlight("Office"))

        layout.addLayout(top_layout)  # Add the top layout to the main layout
        # layout.addWidget(self.wfh_count_label)  # Add the label to the layout
        layout.addWidget(self.wfh_button)
        layout.addWidget(self.office_button)

        layout.setSpacing(int(20* self.scale_factor))  # Add space between buttons
        layout.setAlignment(Qt.AlignCenter)  # Center the layout
        layout.addLayout(bottom_layout)



    def scan_wifi_windows(self):
        """Scans available WiFi networks on Windows"""
        # get action for today and skip the rest of this function if office is already marked, else continue
        if 'Office' in  get_today_action():
            print('office already in db')
            return
        else:
            wifi = PyWiFi()
            iface = wifi.interfaces()[0]  # Get first wireless interface
            iface.scan()  # Trigger scan
            time.sleep(5)  # Give time for scan to complete

            results = iface.scan_results()
            networks = [network.ssid.lower() for network in results if network.ssid]  # Get SSIDs

            if OFFICE_WIFI_SSID in networks:
                # office has been on todays map
                print('found office wifi')
                self.log_and_highlight('Office')
            else:
                print('not found office')
                # self.log_and_highlight("WFH")


    def get_scale_factor(self):
        """Determine the appropriate scale factor based on screen resolution"""
        screen = QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch()
        
        # Default scale factor is 1.0
        if dpi <= 96:  # Standard DPI
            return 1.0
        elif dpi <= 120:
            return 1.25
        elif dpi <= 144:
            return 1.5
        elif dpi <= 192:
            return 2.0
        else:  # 4K and higher
            return 2.5


    def update_wfh_count(self):
        count = get_wfh_count()
        self.wfh_count_label.setText(f"WFH days \n{str_month}:{count}")
        self.wfh_count_label.adjustSize() 
        self.update_wfh_date_labels()

    def position_widget(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        widget_width = self.width()
        # widget_height = self.height()
        padding = int(100 * self.scale_factor)
        self.move(screen_geometry.width() - widget_width - padding, padding)
        # self.move(screen_geometry.width() - widget_width - 10, 10)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None and event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
    
    def changeEvent(self, event):
        if (event.type() == QtCore.QEvent.WindowStateChange and 
            event.spontaneous() and 
            self.windowState() == QtCore.Qt.WindowMinimized):
                self.showNormal()
    
    def hideEvent(self, event):
        if event.spontaneous():
            self.showNormal()


    def log_and_highlight(self, action):
        """Log the action and update button highlight."""
        log_action(action)
        self.update_wfh_count()
        self.highlight_action(action)


    def highlight_today_action(self):
        """Highlight today's action based on the database entry."""
        today_action = get_today_action()
        self.highlight_action(today_action)


    def highlight_action(self, action):
        """Set the button background for the selected action."""
        # Reset button styles
        self.wfh_button.setStyleSheet("")
        self.office_button.setStyleSheet("")

        # Apply highlight to the selected button
        if action == "WFH":
            self.wfh_button.setStyleSheet("background-color: rgba(0, 255, 0, 0.3);")
            # self.wfh_button.setStyleSheet("background-color: rgba(0, 255, 0, 0.3); border: none;")
        elif action == "Office":
            self.office_button.setStyleSheet("background-color: rgba(0, 255, 0, 0.3);")
            # self.office_button.setStyleSheet("background-color: rgba(0, 255, 0, 0.3); border: none;")
        self.update_wfh_count()

    # Update the labels with WFH dates
    def update_wfh_date_labels(self):
        today = datetime.today()
        current_month_dates = get_wfh_dates_for_month(today.year, today.month)
        prev_year, prev_month, previous_month_dates = get_wfh_dates_for_previous_month()
        
        current_month_str = today.strftime('%b')
        prev_month_str = datetime(year=prev_year, month=prev_month, day=1).strftime('%b')
        # Format dates as comma-separated days
        self.current_month_label.setText(f"{current_month_str}: {', '.join(map(str, current_month_dates))}")
        self.previous_month_label.setText(f"{prev_month_str}: {', '.join(map(str, previous_month_dates))}")



# Main Function
def main():
    app = QApplication(sys.argv)
    widget = WorkTrackerWidget()
    widget.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
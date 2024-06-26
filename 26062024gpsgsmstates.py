import sys
import paramiko
import csv
import threading
import matplotlib.pyplot as plt
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# Global variables
stop_thread = False
data_lock = threading.Lock()

def ssh_command(host, port, username, password, csv_filename, data_dict):
    global stop_thread
    try:
        # Create SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=host, port=port, username=username, password=password)
        channel = client.invoke_shell()

        # Wait for the prompt indicating readiness for commands
        while True:
            output = channel.recv(65535).decode('utf-8').strip()
            if output.endswith('#'):
                break

        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['TIME_STAMP', 'LATITUDE', 'LONGITUDE', 'ACCURACY', 'TX', 'RX', 'RSSI', 'RSRP', 'SINR', 'RSRQ'])
            while not stop_thread:
                channel.send('gpsctl -t -i -x -u; gsmctl -e eth0 -r eth0 -q\n')
                output_all = channel.recv(65535).decode('utf-8').strip()
                parsed_data_all = parse_output_gpsctl_t(output_all)

                if parsed_data_all and "root@RUTX50" not in parsed_data_all.values():
                    writer.writerow([
                        parsed_data_all.get('TIME_STAMP', ''), parsed_data_all.get('LATITUDE', ''), parsed_data_all.get('LONGITUDE', ''),
                        parsed_data_all.get('ACCURACY', ''), parsed_data_all.get('TX', ''), parsed_data_all.get('RX', ''),
                        parsed_data_all.get('RSSI', ''), parsed_data_all.get('RSRP', ''), parsed_data_all.get('SINR', ''), parsed_data_all.get('RSRQ', '')
                    ])
                    csvfile.flush()

                    with data_lock:
                        for key in ['RSSI', 'RSRP', 'SINR', 'RSRQ']:
                            if key in parsed_data_all:
                                try:
                                    data_dict[key].append(float(parsed_data_all[key]))
                                except ValueError:
                                    data_dict[key].append(None)
                            else:
                                data_dict[key].append(None)

                        # Trim data_dict to the last 1000 entries
                        for key in data_dict:
                            if len(data_dict[key]) > 1000:
                                data_dict[key] = data_dict[key][-1000:]

                    # After updating data_dict, trigger immediate update of graphs
                    update_graphs()

    except Exception as e:
        print(f"Error: {e}")

def parse_output_gpsctl_t(output_all):
    parsed_data = {}
    lines = output_all.split('\n')

    if len(lines) >= 7:
        parsed_data["TIME_STAMP"] = lines[1].strip()
        parsed_data["LATITUDE"] = lines[2].strip()
        parsed_data["LONGITUDE"] = lines[3].strip()
        parsed_data["ACCURACY"] = lines[4].strip()
        parsed_data["TX"] = lines[5].strip()
        parsed_data["RX"] = lines[6].strip()
    else:
        return None

    for line in lines:
        if line.startswith("RSSI:") or line.startswith("RSRP:") or line.startswith("SINR:") or line.startswith("RSRQ:"):
            key, value = line.strip().split(": ", 1)
            parsed_data[key.strip()] = value.strip()
    return parsed_data

def start_ssh_command():
    global stop_thread
    stop_thread = False
    csv_filename = f"PHY_TEST_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    thread = threading.Thread(target=ssh_command, args=(host, port, username, password, csv_filename, data_dict))
    thread.start()

def stop_ssh_command():
    global stop_thread
    stop_thread = True

def update_graphs():
    with data_lock:
        for ax in axes:
            ax.clear()

        # Plot RSSI, RSRP, and RSRQ on the same subplot
        axes[0].plot(data_dict['RSSI'], label='RSSI')
        axes[0].plot(data_dict['RSRP'], label='RSRP')
        axes[0].plot(data_dict['RSRQ'], label='RSRQ')
        axes[0].set_xlabel('Time (Sec)')
        axes[0].set_ylabel('dBm')
        axes[0].legend()
        axes[0].grid(True)  # Enable grid on the first subplot

        # Plot SINR on a separate subplot
        axes[1].plot(data_dict['SINR'], label='SINR')
        axes[1].set_xlabel('Time (Sec)')
        axes[1].set_ylabel('SINR (dB)')
        axes[1].legend()
        axes[1].grid(True)  # Enable grid on the first subplot

        # Refresh canvas
        canvas.draw()

class App(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        global host, port, username, password, data_dict, axes, canvas

        data_dict = {'RSSI': [], 'RSRP': [], 'SINR': [], 'RSRQ': []}

        host = '192.168.1.1'
        port = 22
        username = 'root'
        password = 'Firecell123456'

        self.setWindowTitle("OAI-GUI-BY-WASEEM")

        # Layouts
        main_layout = QVBoxLayout()
        title_layout = QHBoxLayout()  # Changed to QHBoxLayout for logo and title alignment
        button_layout = QHBoxLayout()
        graph_layout = QVBoxLayout()

        # University logo
        logo_label = QLabel()
        pixmap = QPixmap('miun_logo.png')
        logo_label.setPixmap(pixmap.scaledToWidth(200))  # Adjust width as needed
        logo_label.setAlignment(Qt.AlignLeft)  # Align left

        # Title
        title_label = QLabel("OAI Research & Development - Communication Systems and Networks (CSN) \n Mid Sweden University (MIUN)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("background-color: lightblue; font-weight: bold; font-size: 16pt;")

        # Add logo and title to title_layout with stretch factors
        title_layout.addWidget(logo_label, 1)  # 20% width
        title_layout.addWidget(title_label, 4)  # 80% width

        # Set the title_layout widget
        title_widget = QWidget()
        title_widget.setLayout(title_layout)
        title_widget.setStyleSheet("background-color: white; border: 1px solid black;")

        # Buttons
        start_button = QPushButton("Start")
        start_button.setStyleSheet("background-color: green; color: white;")
        start_button.clicked.connect(start_ssh_command)
        stop_button = QPushButton("Stop")
        stop_button.setStyleSheet("background-color: yellow; color: black;")
        stop_button.clicked.connect(stop_ssh_command)
        terminate_button = QPushButton("Terminate")
        terminate_button.setStyleSheet("background-color: red; color: white;")
        terminate_button.clicked.connect(self.close)

        button_layout.addWidget(start_button)
        button_layout.addWidget(stop_button)
        button_layout.addWidget(terminate_button)

        # Graph
        fig, axes = plt.subplots(2, 1, figsize=(10, 10))  # Create a 2x1 grid of subplots
        fig.subplots_adjust(hspace=0.5)  # Adjust space between subplots
        axes = axes.flatten()

        canvas = FigureCanvas(fig)
        graph_layout.addWidget(canvas)

        # Set layouts
        main_layout.addWidget(title_widget)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(graph_layout)

        self.setLayout(main_layout)

        # Adjust window size
        self.showMaximized()  # Maximize the main window

def main():
    app = QApplication(sys.argv)
    ex = App()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()


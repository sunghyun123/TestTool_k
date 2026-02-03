import ast
import subprocess
import threading
import queue
import time
import json
import re
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from tkinter.scrolledtext import ScrolledText
import atexit
import os
import sys

class PrintRedirector:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        self.widget.insert(tk.END, text)
        self.widget.yview(tk.END)

    def flush(self):
        pass

class DataCollector:
    def __init__(self):
        self.cpu_mem_queue = queue.Queue()
        self.temperature_queue = queue.Queue()
        self.fps_queue = queue.Queue()

        self.version = 0
        self.run_sever = False

        self.data = {
            'cpu_usage': 'N/A',
            'phys_footprint': 'N/A',
            'temperature': 'N/A',
            'fps': 'N/A'
        }

        self.collecting = False

    def get_major_version(self):
        result = subprocess.run(["pyidevice", "deviceinfo"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            print("Failed to execute pyidevice deviceinfo")
            print(result.stderr)
            return None

        device_info = eval(result.stdout.strip())
        product_version = device_info.get('ProductVersion', None)
        if not product_version:
            print("ProductVersion not found in deviceinfo")
            return None

        major_version_match = re.match(r"(\d+)", product_version)
        if major_version_match:
            major_version = int(major_version_match.group(1))
            print(major_version)
            if (major_version >= 17):
                print("Das")
                self.start_tunnel_background()
            self.version = major_version
            return major_version
        else:
            print("Failed to parse ProductVersion")
            return None

    def enqueue_output(self, out, q):
        for line in iter(out.readline, ''):
            q.put(line)
        out.close()

    def process_queue(self, q, process_line):
        while not q.empty():
            line = q.get_nowait()
            process_line(line)

    def get_cpu_mem_info(self):
        if self.version < 17:
            command = "pyidevice instruments sysmontap -b com.kakaogames.aaw --proc_filter physFootprint,cpuUsage --processes --sort cpuUsage"
            self.run_subprocess(command, self.cpu_mem_queue)

        else:
            joined_string = ' '.join(self.rsd_info)
            td = 30
            start_time = time.time()
            while not self.run_sever and time.time() - start_time < 5:
                time.sleep(0.1)
            if self.run_sever:
                command = f"python3 -m pymobiledevice3 developer dvt sysmon process monitor {td} {joined_string}"
                self.run_subprocess3(command, self.cpu_mem_queue)
            else:
                print("Error: Server did not start within the maximum wait time.")

    def get_temperature_info(self):
        while self.collecting:
            command = "pyidevice battery"
            self.run_subprocess(command, self.temperature_queue)
            time.sleep(1)

    def get_fps_info(self):
        if self.version < 17:
            command = "pyidevice instruments fps"
            self.run_subprocess(command, self.fps_queue)
        else:
            start_time = time.time()
            while not self.run_sever and time.time() - start_time < 5:
                time.sleep(0.1)
            if self.run_sever:
                command = ["python3", "-m", "pymobiledevice3", "developer", "dvt", "graphics"] + self.rsd_info
                self.run_subprocess2(command, self.fps_queue)
            else:
                print("Error: Server did not start within the maximum wait time.")

    def run_subprocess(self, command, queue):
        try:
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       universal_newlines=True)
            threading.Thread(target=self.enqueue_output, args=(process.stdout, queue)).start()
        except Exception as e:
            print(f"Error running subprocess: {e}")

    def run_subprocess2(self, command, queue):
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       universal_newlines=True)
            threading.Thread(target=self.enqueue_output, args=(process.stdout, queue)).start()
        except Exception as e:
            print(f"Error running subprocess: {e}")

    def run_subprocess3(self, command, queue):
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       universal_newlines=True)
            threading.Thread(target=self.enqueue_output, args=(process.stdout, queue)).start()
        except Exception as e:
            print(f"Error running subprocess: {e}")

    def process_cpu_mem_line(self, line):
        if self.version < 17:
            if "[INFO]" in line:
                return
            if line.startswith("[('Q7'"):
                data_line = line.strip()
                try:
                    parsed_output = ast.literal_eval(data_line)
                    process_info = parsed_output[0][1]
                    self.data['cpu_usage'] = process_info.get('cpuUsage', 'N/A')
                    self.data['phys_footprint'] = process_info.get('physFootprint', 'N/A')
                except (SyntaxError, ValueError) as e:
                    print(f"Error parsing the data line: {e}")
        else:
            if "[INFO]" in line and "process(" in line:
                data_line = line.strip().split("INFO")[1].strip()
                try:
                    parsed_output = ast.literal_eval(data_line)
                    process_info = parsed_output[0]
                    self.data['cpu_usage'] = process_info.get('cpuUsage', 'N/A')
                    self.data['phys_footprint'] = process_info.get('physFootprint', 'N/A')
                except (SyntaxError, ValueError) as e:
                    print(f"Error parsing the data line: {e}")

    def process_temperature_line(self, line):
        if "[INFO]" in line:
            return
        try:
            if line.strip().startswith("{") and line.strip().endswith("}"):
                battery_info = ast.literal_eval(line.strip())
                if 'Temperature' in battery_info:
                    temperature = battery_info['Temperature']
                    self.data['temperature'] = temperature / 100.0
        except (SyntaxError, ValueError) as e:
            print(f"Error parsing temperature data: {e}")

    def process_fps_line(self, line):
        if self.version < 17:
            try:
                fps_info = ast.literal_eval(line.strip())
                if 'fps' in fps_info:
                    self.data['fps'] = fps_info['fps']
            except (SyntaxError, ValueError) as e:
                print(f"Error parsing the fps data line: {e}")
        else:
            try:
                json_str_match = re.search(r'\{.*\}', line.strip())
                if json_str_match:
                    json_str = json_str_match.group(0).replace("'", "\"")
                    fps_info = json.loads(json_str)
                    if 'CoreAnimationFramesPerSecond' in fps_info:
                        self.data['fps'] = fps_info['CoreAnimationFramesPerSecond']
            except (json.JSONDecodeError, AttributeError) as e:
                print("JSON 파싱 오류:", e)

    def start_tunnel_background(self):
        try:
            password = input("Enter sudo password: ")  # getpass 대신 input 사용
            command = ["sudo", "-S", "python3", "-m", "pymobiledevice3", "remote", "tunneld"]
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            stdin=subprocess.PIPE, text=True)
            print("Starting tunneld process with command:", command)

            self.process.stdin.write(password + '\n')
            self.process.stdin.flush()

            q = queue.Queue()
            t = threading.Thread(target=self.enqueue_output, args=(self.process.stdout, q))
            t.daemon = True
            t.start()

            while True:
                try:
                    output = q.get_nowait()
                    print("Tunneld output:", output)
                except queue.Empty:
                    if self.process.poll() is not None:
                        break
                    continue

                if output:
                    match = re.search(r"--rsd (\S+) (\d+)", output.strip())
                    if match:
                        self.rsd = f"'{match.group(1)}'"
                        self.port = match.group(2)
                        self.rsd_info = ["--rsd", match.group(1), match.group(2)]
                        print("RSD Info found:", self.rsd_info)
                        self.run_sever = True
                        return 0

            self.process.stdout.close()
            self.process.wait()
        except Exception as e:
            print(f"Error starting tunneld: {e}")

    def stop_tunnel(self):
        if self.process and self.process.poll() is None:
            print(f"Stopping tunneld process with PID: {self.process.pid}")
            os.kill(self.process.pid, 9)

    def start_collecting(self):
        self.collecting = True
        self.get_major_version()
        threading.Thread(target=self.get_cpu_mem_info).start()
        threading.Thread(target=self.get_temperature_info).start()
        threading.Thread(target=self.get_fps_info).start()

    def stop_collecting(self):
        self.collecting = False
        try:
            subprocess.run(["sudo", "pkill", "-f", "pymobiledevice3"], check=True)
            print("Successfully stopped pymobiledevice3 processes.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to stop pymobiledevice3 processes: {e}")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time System Monitor")

        self.collector = DataCollector()

        self.start_button = ttk.Button(root, text="Start", command=self.start_collecting)
        self.start_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.stop_button = ttk.Button(root, text="Stop", command=self.stop_collecting)
        self.stop_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.save_log_button = ttk.Button(root, text="Save Log", command=self.save_log)
        self.save_log_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.save_graph_button = ttk.Button(root, text="Save Graph", command=self.save_graph)
        self.save_graph_button.pack(side=tk.LEFT, padx=10, pady=10)

        self.log_text = ScrolledText(root, width=40, height=60)
        self.log_text.pack(side=tk.LEFT, padx=10, pady=10)

        self.log_text2 = ScrolledText(root, width=60, height=60)
        self.log_text2.pack(side=tk.LEFT, padx=10, pady=10)

        plt.rcParams.update({'font.size': 6})
        self.fig, self.axs = plt.subplots(4, 1, figsize=(5, 4))
        plt.subplots_adjust(hspace=1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)

        self.timestamps = []
        self.cpu_data = []
        self.mem_data = []
        self.temp_data = []
        self.fps_data = []

        self.ani = animation.FuncAnimation(self.fig, self.update_graphs, interval=1000, cache_frame_data=False)

        self.print_redirector = PrintRedirector(self.log_text2)
        sys.stdout = self.print_redirector
        sys.stderr = self.print_redirector

    def start_collecting(self):
        self.collector.start_collecting()
        self.update_labels()

    def stop_collecting(self):
        self.collector.stop_collecting()

    def save_log(self):
        with open("system_monitor_log.txt", "w") as log_file:
            log_file.write(self.log_text.get(1.0, tk.END))

    def save_graph(self):
        self.fig.savefig("system_monitor_graph.png")

    def update_labels(self):
        self.collector.process_queue(self.collector.cpu_mem_queue, self.collector.process_cpu_mem_line)
        self.collector.process_queue(self.collector.temperature_queue, self.collector.process_temperature_line)
        self.collector.process_queue(self.collector.fps_queue, self.collector.process_fps_line)

        current_time = time.strftime('%Y.%m.%d - %H:%M:%S')

        cpu_usage = self.format_data(self.collector.data['cpu_usage'], '{:.1f}%')
        phys_footprint = self.format_data(self.collector.data['phys_footprint'], '{:.2f} GB', divisor=1024 ** 3)
        temperature = self.format_data(self.collector.data['temperature'], '{:.1f}°C')
        fps = self.format_data(self.collector.data['fps'], '{}')

        log_entry = (f"{current_time}\n"
                     f"CPU Usage: {cpu_usage}\n"
                     f"Memory: {phys_footprint}\n"
                     f"Temperature: {temperature}\n"
                     f"FPS: {fps}\n")

        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.yview(tk.END)

        self.root.after(1000, self.update_labels)

    def format_data(self, data, fmt, divisor=1):
        if data != 'N/A' and data is not None:
            return fmt.format(float(data) / divisor)
        return "N/A"

    def update_graphs(self, i):
        current_time = datetime.now().strftime('%H:%M:%S')

        self.timestamps.append(current_time)
        self.cpu_data.append(self.get_data_value(self.collector.data['cpu_usage']))
        self.mem_data.append(self.get_data_value(self.collector.data['phys_footprint'], divisor=1024 ** 3))
        self.temp_data.append(self.get_data_value(self.collector.data['temperature']))
        self.fps_data.append(self.get_data_value(self.collector.data['fps']))

        self.limit_data_length(7200)

        self.axs[0].cla()
        self.axs[1].cla()
        self.axs[2].cla()
        self.axs[3].cla()

        self.plot_graph(self.axs[0], self.timestamps, self.cpu_data, 'CPU Usage (%)', 'blue')
        self.plot_graph(self.axs[1], self.timestamps, self.mem_data, 'Memory (GB)', 'green')
        self.plot_graph(self.axs[2], self.timestamps, self.temp_data, 'Temperature (°C)', 'red')
        self.plot_graph(self.axs[3], self.timestamps, self.fps_data, 'FPS', 'purple')

        self.canvas.draw()

    def get_data_value(self, data, divisor=1):
        if data not in ['N/A', None]:
            return float(data) / divisor
        return 0

    def limit_data_length(self, length):
        self.timestamps = self.timestamps[-length:]
        self.cpu_data = self.cpu_data[-length:]
        self.mem_data = self.mem_data[-length:]
        self.temp_data = self.temp_data[-length:]
        self.fps_data = self.fps_data[-length:]

    def plot_graph(self, ax, x_data, y_data, label, color):
        ax.plot(x_data, y_data, label=label, color=color)
        ax.legend(loc='upper right')
        ax.tick_params(axis='x', rotation=45)
        ax.set_xticks(x_data[::max(300, len(x_data) // 10)])

def run_as_admin(command):
    script = f"""
     do shell script "{command}" with administrator privileges
     """
    proc = subprocess.Popen(['osascript', '-e', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = proc.communicate()
    return output, error

if __name__ == "__main__":
    import sys

    command = "touch /private/var/tmp/testfile"
    output, error = run_as_admin(command)

    root = tk.Tk()
    app = App(root)
    root.mainloop()

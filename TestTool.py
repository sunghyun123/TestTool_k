import tkinter as tk  # tkinter의 전체 모듈
from tkinter import ttk  # tkinter의 서브모듈 ttk, 디자인 부분을 개선한 장점이 있다
import tkinter.messagebox as messagebox
import subprocess
import threading
import time
import re
import json



# 변수 모음 클래스
class Config:
    def __init__(self):
        self.selected_device = None  # 선택된 장치 ID를 저장할 글로벌 변수
        self.selected_package_name = None  # 선택된 패키지 이름을 저장할 글로벌 변수
        self.selected_device_type = "none"  # "android" 또는 "ios"
        self.android_data = {}  # 각 Android 디바이스의 데이터를 저장할 딕셔너리
        self.ios_data = {}  # 각 iOS 디바이스의 데이터를 저장할 딕셔너리
        self.ios17_threads = {}
        # 스레드 관리를 위한 딕셔너리
        self.android_threads = {}
        self.ios_threads = {}
        # 전체 CPU 및 메모리를 저장하는 변수
        self.cpu_cores = None
        self.max_mem = None
        self.is_collecting = False  # 성능 수집 중인 상태를 추적하는 변수
        self.stop_event = threading.Event()  # 모든 스레드가 공유하는 stop_event
        self.tram = None

        self.MAX_DATA_POINTS = 10
        self.last_valid_fps = -1
        self.last_valid_cpu = -1
        self.last_valid_gpu = -1
        self.last_valid_memory = -1
        self.last_valid_temperature = -1

        # 로그 파일 경로 설정
        self.log_file_path = None


# GUI 클래스, 루트 권한 부여 및 성능 수집 시작 메서드가 포함되어 있다
class PerfGUI:
    def __init__(self, root, config, perf):

        self.root = root

        self.config = config
        self.perf = perf

        self.pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        self.pane.pack(fill=tk.BOTH, expand=True)

        # 왼쪽 프레임, 디바이스 정보 출력 및 패키지 선택, 성능 수집 시작과 프로그램 종료 버튼이 포함됨
        left_frame = ttk.Frame(self.pane, width=200, height=600)
        left_frame.pack(fill=tk.BOTH, expand=True)
        self.pane.add(left_frame)

        # 오른쪽 프레임, 성능 로그를 실시간으로 보여줌
        right_frame = ttk.Frame(self.pane, width=200, height=300)
        right_frame.pack_propagate(False)
        self.pane.add(right_frame)

        # 디바이스 모델 라벨과 리스트박스
        device_label = ttk.Label(left_frame, text="연결된 디바이스 모델")
        device_label.pack()
        self.device_listbox = tk.Listbox(left_frame, height=3)
        self.device_listbox.pack(fill=tk.BOTH, expand=True)
        self.device_listbox.insert(tk.END, "디바이스 정보 업데이트 버튼을 눌러주세요")

        # 패키지 목록이 출력되는 콤보박스
        self.package_combobox = ttk.Combobox(left_frame, width=50, height=6)  # height 매개변수로 드롭다운 목록의 높이 조정
        self.package_combobox.pack(fill=tk.BOTH, expand=True, pady=(0, 20))  # pady로 패딩 추가하여 위치 조정
        self.package_combobox.bind('<<ComboboxSelected>>', self.on_package_selected)  # 사용자가 패키지를 선택했을때 발생하는 이벤트

        # 디바이스 정보 업데이트 버튼
        self.update_button = ttk.Button(left_frame, text="디바이스 정보 업데이트", command=self.update_device_list)
        self.update_button.pack()

        # 성능 수집 시작 버튼
        self.start_collection_button = ttk.Button(left_frame, text="성능 수집 시작",
                                                  command=self.start_performance_collection)
        self.start_collection_button.pack(fill=tk.X, pady=2)

        # 오른쪽 프레임에 출력되는 성능 로그
        self.log_text = tk.Text(right_frame, height=400, width=400)
        self.log_text.pack()


        # 종료버튼, 편의성을 위해 추가
        exit_button = ttk.Button(left_frame, text="프로그램 종료", command=self.on_exit)  # root.destroy를 호출하여 프로그램 종료
        exit_button.pack(fill=tk.X, pady=2)

    # 디바이스 업데이트 함수, 디바이스 정보 및 설치되어있는 패키지 목록을 가져온다
    def update_device_list(self):

        self.device_listbox.delete(0, tk.END)
        self.package_combobox['values'] = []
        self.package_combobox.set('')  # 패키지 콤보박스 선택 초기화
        android_devices = self.get_android_devices()
        ios_devices = self.get_ios_devices() if not android_devices else []  # Android 기기가 연결되어 있으면 iOS 목록을 비웁니다.

        if not android_devices and not ios_devices:
            self.device_listbox.insert(tk.END, "디바이스 정보 업데이트 버튼을 눌러주세요")

        #연결된 디바이스 정보를 화면에 노출시키는 부분
        for device_id in android_devices + ios_devices:
            model = self.get_device_model(device_id, device_id in android_devices) # 디바이스 모델병 ex)Ipad 14.5
            self.device_listbox.insert(tk.END,
                                       f'{"AOS" if device_id in android_devices else "iOS"}: {model} ({device_id})')


        # 패키지를 출력하는 부분
        if self.device_listbox.size() > 0:
            self.device_listbox.select_set(0)
            self.config.selected_device = self.device_listbox.get(self.device_listbox.curselection()).split(' ')[
                -1].strip('()')
            self.update_package_list()

            # 선택된 디바이스의 CPU 코어 수와 최대 메모리 업데이트
            if 'aos' in self.config.selected_device_type:
                self.config.cpu_cores = self.perf.get_cpu_cores()  # CPU 코어 수 업데이트
                self.config.max_mem = self.perf.get_max_mem()  # 최대 메모리 업데이트

    # 디바이스 모델명을 가져오는 함수, ex) Ipad14.5
    def get_device_model(self, device_id, is_android=True):
        if is_android:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                                    stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
            if result.stdout.strip():
                self.config.selected_device_type = "aos"
                return result.stdout.strip()
            else:
                return None
        else:
            result = subprocess.run(['tidevice', 'info', '-k', 'ProductType'], stdout=subprocess.PIPE,
                                    text=True, stderr=subprocess.DEVNULL, encoding='utf-8')
            model = result.stdout.strip().replace("'", "")  # 작은 따옴표를 제거
            if model:
                self.config.selected_device_type = "ios"
                return model
            else:
                return ''

    # 선택된 패키지를 현재 화면에 노출되는 패키지로 바꾸는 함수
    def on_package_selected(self, event):
        self.config.selected_package_name = self.package_combobox.get()

    # 현재 ios 기기에 설치된 패키지 명을 가져오는 함수
    def get_ios_installed_packages(self, device_id):
        cmd = ['tidevice', '-u', device_id, 'applist']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        packages = result.stdout.splitlines()
        # 패키지 이름만 추출
        package_names = [line.split(' ')[0] for line in packages if line]
        self.config.selected_package_name = package_names
        return package_names


    def update_package_list(self):
        # 현재 선택된 항목이 있는지 확인
        if not self.device_listbox.curselection():
            return
        selected_device = self.device_listbox.get(self.device_listbox.curselection())
        selected_device_id = selected_device.split(' ')[-1].strip('()')  # 디바이스 ID 추출 수정

        # 콤보박스 초기화
        self.package_combobox['values'] = []
        self.package_combobox.set('')

        if 'AOS' in selected_device:
            # Android 디바이스의 패키지 목록 가져오기
            packages = self.get_installed_packages(selected_device_id)
            # 'com.kakaogames'를 포함하는 패키지만 필터링
            filtered_packages = [pkg for pkg in packages if 'com' in pkg]
            package_names = [pkg.split(':')[-1] for pkg in filtered_packages]  # 패키지 이름만 추출
            self.package_combobox['values'] = package_names  # 드롭다운 목록 업데이트

        elif 'iOS' in selected_device:
            # iOS 디바이스의 패키지 목록 가져오기
            packages = self.get_ios_installed_packages(selected_device_id)
            self.package_combobox['values'] = packages  # 드롭다운 목록 업데이트


    # 성능 수집 시작 함수,
    def start_performance_collection(self):
        device_id = self.config.selected_device
        package_name = self.config.selected_package_name
        ios_version = self.get_ios_version()
        print(self.config.selected_device_type)

        # 스레드 중복 시작 방지
        if self.config.selected_device in self.config.android_threads:
            existing_thread = self.config.android_threads[self.config.selected_device]
            if existing_thread.is_alive():
                self.stop_performance_collection()  # 기존 스레드 중단
                existing_thread.join()  # 기존 스레드 종료 대기
            del self.config.android_threads[self.config.selected_device]  # 기존 스레드 정보 삭제

        # iOS 17.0 이상 기기의 성능 수집 중단
        if 'ios' in self.config.selected_device_type and self.config.selected_device in self.config.ios17_threads:
            ios17_thread = self.config.ios17_threads[self.config.selected_device]
            if ios17_thread.is_alive():
                ios17_thread.join()
                del self.config.ios17_threads[self.config.selected_device]

        # iOS 기기의 성능 수집 중단
        elif 'ios' in self.config.selected_device_type and self.config.selected_device in self.config.ios_threads:
            ios_thread = self.config.ios_threads[self.config.selected_device]
            if ios_thread.is_alive():
                ios_thread.join()
                del self.config.ios_threads[self.config.selected_device]

        # 연결된 기기가 aos일 경우
        if 'aos' in self.config.selected_device_type:
            self.config.stop_event.clear()

            thread = threading.Thread(target=self.collect_android_performance_data,
                                      args=(device_id, package_name, self.config.stop_event))
            thread.daemon = True
            thread.start()
            self.config.android_threads[device_id] = thread
            print("성능 수집 시작..")

        # 연결된 기기가 ios17이상을 사용하는 ios 기기일 경우
        if 'ios' in self.config.selected_device_type and ios_version >= 17:
            self.config.stop_event.clear()
            thread = threading.Thread(target=self.collect_ios17_performance_data,
                                      args=(device_id, self.config.stop_event))
            thread.daemon = True
            thread.start()
            self.config.ios17_threads[device_id] = thread
            print("성능 수집 시작..")

        # 연결된 기기가 ios17 미만을 사용하는 기기일 경우
        elif 'ios' in self.config.selected_device_type:
            self.config.stop_event.clear()
            thread = threading.Thread(target=self.collect_ios_performance_data,
                                      args=(device_id, self.config.stop_event))
            thread.daemon = True
            thread.start()
            self.config.ios_threads[device_id] = thread
            print("성능 수집 시작..")

    # 성능 수집 중단 함수
    def stop_performance_collection(self):

        # 중단 이벤트 설정
        self.config.stop_event.set()

        # 연결된 기기가 없는 경우 메시지 출력
        if not self.config.selected_device:
            messagebox.showinfo("중단 오류", "연결된 기기가 없습니다.")
            return

        self.config.is_collecting = False
        #    messagebox.showinfo("성능 수집", "성능 수집이 중단되었습니다.")
        print("성능 수집 종료..")

    # 프로그램 종료 함수
    def on_exit(self):
        # 종료 이벤트 설정
        self.stop_performance_collection()  # 성능 수집 중단

        # Tkinter 윈도우 종료
        self.root.destroy()


    # aos 성능 수집 함수, aos 관련 기능 함수 호출 및 수집한 성능 출력 담당
    def collect_android_performance_data(self, device_id, package_name, stop_event):

        while not self.config.stop_event.is_set():
            fps = self.perf.get_android_fps(device_id, package_name)
            cpu = self.perf.get_android_cpu_usage(device_id)
            gpu = self.perf.get_android_gpu_usage(device_id)
            memory = self.perf.get_android_memory_usage(device_id)
            temperature = self.perf.get_android_temperature(device_id)

            log_message = (
                f"FPS: {fps}\n"
                f"CPU: {cpu}%\n"
                f"GPU: {gpu}%\n"
                f"Memory: {memory}%\n"
                f"Temperature: {temperature}°C"
            )

            self.log_text.insert(tk.END, log_message + "\n")
            self.log_text.see(tk.END)

            if self.config.stop_event.is_set():
                break

            time.sleep(1)

    # ios17 성능 수집 함수, ios17 관련 기능 함수 호출 및 수집한 성능 출력 담당
    def collect_ios17_performance_data(self, device_id, stop_event):
        model = self.perf.get_ios_device_model()

        if model:
            self.config.tram = self.perf.get_ram_for_model(model)
        else:
            print("기기를 연결해주세요.")

        # exe 실행파일
        # app 실행파일

        # 터널 서버 시작 및 RSD 정보 추출
        rsd_info = self.perf.start_tunnel_background()
        if not rsd_info:
            print("RSD 정보를 찾을 수 없습니다.")
            return

        name = self.get_app_name_from_package(self.config.selected_package_name)

        time.sleep(3)

        command1 = ["python3", "-m", "pymobiledevice3", "developer", "dvt", "graphics"] + rsd_info

        process1 = subprocess.Popen(command1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=0,
                                    encoding='utf-8')

        try:

            while not self.config.stop_event.is_set():
                if process1.poll() is not None:
                    break

                output1 = process1.stdout.readline()

                if output1:
                    # 성능 지표 추출
                    fps = self.perf.get_ios_data(output1)

                    if fps:
                        temperature = self.perf.get_ios_temperature()
                        ios_perf = self.perf.get_ios17_cpu_mem(name, rsd_info)
                        cpu = round(ios_perf[0], 1) if ios_perf[0] is not None else 0
                        ram = ios_perf[1] / (1024 * 1024)
                        temperature = temperature / 10

                        if self.config.tram is not None:
                            mem = round((ram / self.config.tram) * 100, 1)
                        else:
                            mem = 0
                            print("디바이스 Ram 등록 필요.")

                        log_message = (
                            f"FPS: {fps['CoreAnimationFramesPerSecond']}\n"
                            f"CPU: {cpu}%\n"
                            f"Memory: {mem}%\n"
                            f"Temperature: {temperature}°C"
                        )

                        self.log_text.insert(tk.END, log_message + "\n")
                        self.log_text.see(tk.END)

                else:

                    break
        finally:
            process1.terminate()

    # ios(17이하) 성능 수집 함수, ios 관련 기능 함수 호출 및 수집한 성능 출력 담당
    def collect_ios_performance_data(self, device_id, stop_event):
        model = self.perf.get_ios_device_model()

        if model:
            self.config.tram = self.perf.get_ram_for_model(model)
        else:
            print("기기를 연결해주세요.")

        name = self.get_app_name_from_package(self.config.selected_package_name)
        time.sleep(3)

        command1 = ["python3", "-m", "pymobiledevice3", "developer", "dvt", "graphics"]

        process1 = subprocess.Popen(command1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                    bufsize=0, encoding='utf-8')

        try:

            while not self.config.stop_event.is_set():
                if process1.poll() is not None:
                    break

                output1 = process1.stdout.readline()

                if output1:
                    # 성능 지표 추출
                    fps = self.perf.get_ios_data(output1)

                    if fps:
                        temperature = self.perf.get_ios_temperature()
                        ios_perf = self.perf.get_ios_cpu_mem(name)
                        cpu = round(ios_perf[0], 1) if ios_perf[0] is not None else 0
                        ram = ios_perf[1] / (1024 * 1024)
                        temperature = temperature / 10

                        if self.config.tram is not None:
                            mem = round((ram / self.config.tram) * 100, 1)
                        else:
                            mem = 0
                            print("디바이스 Ram 등록 필요.")

                        log_message = (
                            f"FPS: {fps['CoreAnimationFramesPerSecond']}\n"
                            f"CPU: {cpu}%\n"
                            f"Memory: {mem}%\n"
                            f"Temperature: {temperature}°C"
                        )

                        self.log_text.insert(tk.END, log_message + "\n")
                        self.log_text.see(tk.END)

                else:

                    break
        finally:
            process1.terminate()
        # 각 성능 지표의 최근 값을 저장할 임시 변수 초기화

    # 안드로이드 디바이스 정보 가져오기, adb 명령어 사용
    def get_android_devices(self):
        try:
            result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
            devices = result.stdout.partition('\n')[2].replace('\tdevice\n', '').split('\n')
            return [device for device in devices if device]
        except FileNotFoundError:
            return "none"

    def get_ios_devices(self):
        try:
            # tidevice info 명령어 실행
            result = subprocess.run(['tidevice', 'info'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL,
                                    encoding='utf-8')

            # 출력된 내용에서 UniqueDeviceID 찾기
            match = re.search(r'UniqueDeviceID:\s+(\S+)', result.stdout)
            return [match.group(1)] if match else []
        except FileNotFoundError:
            print("tidevice 명령을 찾을 수 없습니다. iOS 장치 정보를 가져올 수 없습니다.")
            return []

    ##############################################

    def get_app_name_from_package(self, package_name):  # ios에서 패키지 이름으로 부터 앱 이름을 얻어오는 함수.
        # 명령어 실행
        command = f"tidevice appinfo {package_name} | grep 'CFBundleExecutable'"
        result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # 실행 오류 처리
        if result.returncode != 0:
            raise Exception(f"Command failed with error: {result.stderr}")

        # 출력 결과에서 실행 파일 이름 추출
        match = re.search(r"'CFBundleExecutable': '(\w+)'", result.stdout)
        if match:
            return match.group(1)

        return "Executable not found"

    ############### 패키지 출력 ###################

    # Android 기기에서 설치된 애플리케이션의 패키지 목록을 가져오는 함수
    def get_installed_packages(self, device_id):
        cmd = ['adb', '-s', device_id, 'shell', 'pm', 'list', 'packages']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        packages = result.stdout.splitlines()

        # "kakaogames"를 포함하는 패키지만 필터링
        filtered_packages = [pkg.partition(':')[2] for pkg in packages if 'kakaogames' in pkg]
        return filtered_packages

    #################################################

    # 현재 패키지가 실행중인지 확인하는 메서드
    def is_package_running(self, device_id, package_name):
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'pidof', package_name], stdout=subprocess.PIPE,
                                    text=True, stderr=subprocess.DEVNULL)
            return result.stdout.strip() != ""
        except subprocess.CalledProcessError:
            return False

    # ios 버전을 가져오는 메서드
    def get_ios_version(self):
        try:
            result = subprocess.run(['tidevice', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    encoding='utf-8')
            output = result.stdout

            match = re.search(r'ProductVersion:\s+(\d+\.\d+)(?:\.\d+)?', output)
            if match:
                version_str = match.group(1).replace('.', '')  # '.' 제거
                if len(version_str) >= 2:
                    version_int = int(version_str[:2])  # 앞의 두 자리만 추출하여 정수로 변환
                    return version_int

                else:
                    return 0
            else:
                return 0
        except subprocess.CalledProcessError:
            return 0


# 성능 수집 함수 모음 클래스
class Perf:
    def __init__(self, config):

        self.config = config

    # 게임화면(윈도우) 를 얻어내는 메서드
    def get_window_name(self, package_name):
        # adb 명령어를 통해 윈도우 목록을 가져옵니다.
        cmd = "adb shell dumpsys SurfaceFlinger --list"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        window_list = result.stdout.splitlines()

        for line in window_list:
            if package_name in line and "SurfaceView" in line:
                if "BLAST" in line or not any("BLAST" in l for l in window_list):
                    #                print(line)
                    return line
        return None

    # get_window_name에서 추출한 윈도우 이름을 식별자로 하여 타임스탬프 값을 얻는 메서드
    def get_timestamps(self, window_name):
        # 특수 문자 처리
        window_name_escaped = re.sub(r"([()])", r"\\\1", window_name)
        cmd = f"adb shell dumpsys SurfaceFlinger --latency '{window_name_escaped}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
        timestamps = [int(line.split()[1]) for line in result.stdout.splitlines()[1:] if line.strip()]
        return timestamps

    # 추출한 FPS 값을 연산하는 메서드
    def calculate_fps(self, timestamps):

        if not timestamps:
            return 0

        deltas = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        average_frame_time_ns = sum(deltas) / len(deltas)
        fps = 1e9 / average_frame_time_ns

        # 소수점 부분 제거
        fps = round(fps)

        # 0이 아닌 경우에만 최근 유효한 FPS 값으로 저장
        if fps > 0:
            self.config.last_valid_fps = fps
            return self.config.last_valid_fps
        else:
            # 현재 FPS가 0인 경우, 이전에 저장된 값을 사용
            return self.config.last_valid_fps if self.config.last_valid_fps is not None else "0"

    # AOS FPS 리턴 함수, 나머지 FPS 관련 함수는 여기서 호출된다
    def get_android_fps(self, device_id, package_name):
        if package_name is not None:
            window_name = self.get_window_name(package_name)
        else:
            print("패키지를 선택해주세요")
            return -1
        if not window_name:
            return -1

        timestamps = self.get_timestamps(window_name)
        fps = self.calculate_fps(timestamps)

        if fps is not None:
            return fps

    # AOS 전체 CPU 코어 갯수를 구하는 함수
    def get_cpu_cores(self):
        try:
            command = "adb shell cat /proc/cpuinfo"
            output = subprocess.check_output(command, shell=True).decode('utf-8')
            cpu_cores = output.count('processor')
            return cpu_cores
        except subprocess.CalledProcessError as e:
            print("Error fetching CPU cores:", e)
            return 0

    # AOS CPU 추출 및 계산 함수
    def get_android_cpu_usage(self, device_id):

        if self.config.cpu_cores == 0:
            print("CPU 정보를 찾을 수 없습니다.")
            return 0
        # ADB 명령어 구성
        adb_command = f"adb -s {device_id} shell top -n 1 | grep com.kakaogames.+"
        try:
            # ADB 명령어 실행
            result = subprocess.run(adb_command, shell=True, text=True, capture_output=True, encoding='utf-8')
            output = result.stdout

            # CPU 사용률 추출 및 파싱
            if output:
                cpu_usage_str = output.split()[8]  # 9번째 필드(인덱스 8)가 CPU 사용률
                try:
                    cpu_usage = float(cpu_usage_str.strip('%'))
                except ValueError:
                    cpu_usage = float(cpu_usage_str)
                total_cpu_usage_percentage = (cpu_usage / (self.config.cpu_cores * 100)) * 100
                if (total_cpu_usage_percentage == 0 or total_cpu_usage_percentage > 100):
                    total_cpu_usage_percentage = self.config.last_valid_cpu
                else:
                    self.config.last_valid_cpu = total_cpu_usage_percentage
                return int(total_cpu_usage_percentage)
            else:
                return 0
        except subprocess.CalledProcessError as e:
            print(f"Error executing ADB command: {e}")
            return 0

    # AOS GPU 추출 및 계산 함수
    def get_android_gpu_usage(self, device_id):

        # 첫 번째 명령어 설정
        command1 = f"adb -s {device_id} shell cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage"
        # 두 번째 명령어 설정
        command2 = "adb shell cat /sys/class/misc/mali0/device/utilization"

        try:
            output = subprocess.check_output(command1, shell=True, text=True, encoding='utf-8')
            gpu_usage = round(float(output.strip().replace('%', '').strip()), 1)
        except subprocess.CalledProcessError:
            # 첫 번째 명령어 실패 시, 두 번째 명령어 시도
            try:
                output = subprocess.check_output(command2, shell=True, text=True, encoding='utf-8')
                gpu_usage = round(float(output.strip()), 1)
            except subprocess.CalledProcessError as e:
                print(f"Error fetching GPU usage: {e}")
                return 0
            except ValueError as e:
                print(f"Error processing GPU usage output: {e}")
                return 0

        return gpu_usage

    # AOS 전체 메모리 용량을 구하는 함수
    def get_max_mem(self):
        try:
            command = "adb shell cat /proc/meminfo"
            output = subprocess.check_output(command, shell=True).decode('utf-8')

            # 정규 표현식을 사용하여 MemTotal 값을 추출합니다.
            match = re.search(r'MemTotal:\s+(\d+)', output)
            if match:
                max_mem = int(match.group(1))  # KB 단위로 추출된 값
                return max_mem
            else:
                print("MemTotal not found in output")
                return 0
        except subprocess.CalledProcessError as e:
            print("Error fetching max memory:", e)
            return 0

    # AOS 메모리 추출 및 계산 함수
    def get_android_memory_usage(self, device_id):
        adb_command = f"adb -s {device_id} shell top -n 1 | grep com.kakaogames.+"
        try:
            result = subprocess.run(adb_command, shell=True, text=True, capture_output=True, encoding='utf-8')
            output = result.stdout

            if output:
                mem_usage_str = output.split()[5]  # 메모리 사용량 필드 추출
                mem_usage_value = float(mem_usage_str[:-1])  # 숫자 부분 추출

                # 단위에 따라 KB 단위로 변환
                if 'M' in mem_usage_str:
                    mem_usage_kb = mem_usage_value * 1024  # MB -> KB
                elif 'G' in mem_usage_str:
                    mem_usage_kb = mem_usage_value * 1024 * 1024  # GB -> KB
                elif 'K' in mem_usage_str:
                    mem_usage_kb = mem_usage_value  # 이미 KB 단위
                else:
                    mem_usage_kb = 0  # 알 수 없는 단위

                # 전체 메모리 대비 사용량 비율을 계산합니다.
                mem_usage_percentage = (mem_usage_kb / self.config.max_mem) * 100
                return int(mem_usage_percentage)
            else:
                return 0
        except subprocess.CalledProcessError as e:
            print(f"Error executing ADB command: {e}")
            return 0

    # AOS 온도 추출 및 계산 함수
    def get_android_temperature(self, device_id):
        adb_command = f"adb -s {device_id} shell dumpsys battery | grep 'temperature'"
        try:
            result = subprocess.run(adb_command, shell=True, text=True, capture_output=True, encoding='utf-8')
            output = result.stdout
            if output:
                temperature = output.split()[1]  # 'temperature' 라인의 2번째 필드
                return int(temperature) / 10.0  # 배터리 온도는 1/10도 단위로 제공됨
            else:
                return 0
        except subprocess.CalledProcessError as e:
            print(f"Error executing ADB command: {e}")
            return 0

    ################ ios 성능 수집 시작 #################

    # GB 단위로 되어있는 RAM 값을 MB 값으로 바꿔주는 메서드
    def convert_gb_to_mb(self, ram_gb):
        # Converts GB value to MB and returns it as an integer
        return int(ram_gb.split()[0]) * 1024


    # 기기의 전체 RAM값을 기록해둔 데이터 메서드, 신규 기기가 추가될때마다 업데이트 해주어야 한다.
    def get_ram_for_model(self, model):
        # 모델별 RAM 정보를 저장한 딕셔너리
        model_ram_map = {
            "iPad14,5": "6 GB",  # iPhone 14 Pro Max
            "iPhone14,6": "6 GB",  # iPhone 14
            "iPhone14,3": "6 GB",  # iPhone 14 Pro Max
            "iPhone14,2": "6 GB",  # iPhone 14 Pro
            "iPhone14,1": "6 GB",  # iPhone 14
            "iPhone14,4": "6 GB",  # iPhone 14 Plus
            "iPhone13,4": "6 GB",  # iPhone 13 Pro Max
            "iPhone13,3": "6 GB",  # iPhone 13 Pro
            "iPhone13,2": "4 GB",  # iPhone 13
            "iPhone13,1": "4 GB",  # iPhone 13 Mini
            "iPhone12,5": "6 GB",  # iPhone 12 Pro Max
            "iPhone12,3": "6 GB",  # iPhone 12 Pro
            "iPhone12,1": "4 GB",  # iPhone 12
            "iPhone12,8": "4 GB",  # iPhone 12 Mini
            "iPhone13,8": "4 GB",  # iPhone SE (2022)
            "iPhone11,6": "4 GB",  # iPhone XS Max
            "iPhone11,2": "4 GB",  # iPhone XS
            "iPhone11,8": "3 GB",  # iPhone XR
            "iPhone10,6": "3 GB",  # iPhone X
            "iPhone10,5": "3 GB",  # iPhone 8 Plus
            "iPhone10,4": "2 GB",  # iPhone 8
            "iPhone9,4": "3 GB",  # iPhone 7 Plus
            "iPhone9,3": "2 GB",  # iPhone 7
            "iPhone8,4": "2 GB",  # iPhone SE (2016)
            "iPhone8,2": "2 GB",  # iPhone 6s Plus
            "iPhone8,1": "2 GB",  # iPhone 6s
            "iPhone7,1": "1 GB",  # iPhone 6 Plus
            "iPhone7,2": "1 GB",  # iPhone 6
            "iPhone6,2": "1 GB",  # iPhone 5s
            "iPhone5,4": "1 GB",  # iPhone 5c
            "iPhone5,1": "1 GB",  # iPhone 5
            # 추가 모델을 여기에 포함시켜야 합니다.
        }

        ram_gb = model_ram_map.get(model, None)
        if ram_gb:
            return self.convert_gb_to_mb(ram_gb)  # 이제 정수 값을 반환합니다.
        else:
            return None

    #IOS 기기의 전체 RAM 값을 알기 위해 식별자로 쓰기 위한 기기의 모델 번호를 추출하는 메서드
    def get_ios_device_model(self):
        # 이 명령은 연결된 iOS 기기의 모델 식별 번호를 반환합니다.
        result = subprocess.run(['tidevice', 'info', '-k', 'ProductType'], capture_output=True, text=True)
        model = result.stdout.strip().replace("'", "")
        if model:
            return model
        else:
            return ''


    # cpu와 mem를 수집하여 리턴하는 메서드
    def get_ios17_cpu_mem(self, name, rsd_info):
        joined_string = ' '.join(rsd_info)
        command = f"python3 -m pymobiledevice3 developer dvt sysmon process single --attributes name={name} --no-color {joined_string}"

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   encoding='utf-8')

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Command failed with error: {stderr.decode()}")
            return 0, 0  # 기본값으로 0 반환

        try:
            data = json.loads(stdout)
            if not data:  # 데이터가 비어 있을 경우 처리
                print("Output data is empty")
                return 0, 0  # 기본값으로 0 반환
        except json.JSONDecodeError:
            print("Failed to parse JSON from command output")
            return 0, 0  # 기본값으로 0 반환

        # 값 추출
        cpuUsage = data[0].get("cpuUsage", 0)  # 기본값 0 설정
        physFootprint = data[0].get("physFootprint", 0)  # 기본값 0 설정

        return cpuUsage, physFootprint


    # ios FPS(원본, 문자열) 값을 파싱하여 숫자값만 반환하는 메서드
    def get_ios_data(self, output):
        try:
            # JSON 데이터 부분만 추출
            json_str = re.search(r"\{.*\}", output).group()

            # Python 딕셔너리 형태를 JSON 형식으로 변환
            json_str = json_str.replace("'", '"')

            data = json.loads(json_str)

            # 필요한 성능 지표 추출
            return {
                "CoreAnimationFramesPerSecond": data.get('CoreAnimationFramesPerSecond', 0),
            }
        except (json.JSONDecodeError, AttributeError) as e:
            # 오류 로깅
            #        print("JSON 파싱 오류:", e)
            return None

    ############ ios 17 버전 이상일 때, 서버를 켬 #################

    # cpu와 mem를 수집하여 리턴하는 메서드, 17과 동일(터널 부분만 제거)
    def get_ios_cpu_mem(self, name):
        command = f"python3 -m pymobiledevice3 developer dvt sysmon process single --attributes name={name} --no-color"

        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   encoding='utf-8')

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            print(f"Command failed with error: {stderr.decode()}")
            return 0, 0  # 기본값으로 0 반환

        try:
            data = json.loads(stdout)
            if not data:  # 데이터가 비어 있을 경우 처리
                print("Output data is empty")
                return 0, 0  # 기본값으로 0 반환
        except json.JSONDecodeError:
            print("Failed to parse JSON from command output")
            return 0, 0  # 기본값으로 0 반환

        # 값 추출
        cpuUsage = data[0].get("cpuUsage", 0)  # 기본값 0 설정
        physFootprint = data[0].get("physFootprint", 0)  # 기본값 0 설정

        return cpuUsage, physFootprint

    # ios 온도값을 추출 및 리턴하는 메서드, 17과 17미만 에서 동시에 사용함
    def get_ios_temperature(self):
        # pymobiledevice3 명령어 실행
        command = f"pymobiledevice3 diagnostics battery single --no-color"
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   encoding='utf-8')
        stdout, stderr = process.communicate()
        temperature = None  # 초기 온도를 None으로 설정

        if process.returncode != 0:
            return 0  # 기본값으로 0 반환

        try:
            data1 = json.loads(stdout)
            if not data1:  # 데이터가 비어 있을 경우 처리
                print("Output data is empty")
                return 0  # 기본값으로 0 반환
        except json.JSONDecodeError:
            print("Failed to parse JSON from command output")
            return 0  # 기본값으로 0 반환

        # 값 추출
        temperature = data1["Temperature"]  # 기본값 0 설정

        if temperature is not None:
            # 온도를 10으로 나누고, 정수로 변환
            temp_celsius = int(temperature / 10)
            return temp_celsius

        print("적합한 온도 정보를 찾지 못했습니다.")
        return None

    # ios 17 의 터널 생성 메서드, 이 메서드로 인하여 터미널에서 사용자에 의한 비밀번호 입력이 불가피하다
    def start_tunnel_background(self):
        # 서버를 백그라운드에서 시작
        process = subprocess.Popen(["sudo", "python3", "-m", "pymobiledevice3", "remote", "start-tunnel"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # 출력에서 RSD 정보 추출
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                match = re.search(r"--rsd (\S+) (\d+)", output.strip())
                if match:
                    rsd_info = ["--rsd", match.group(1), match.group(2)]
                    return rsd_info

###################################################################

def main():
    # 메인 애플리케이션 윈도우
    root = tk.Tk()
    config = Config()
    perf = Perf(config)
    app = PerfGUI(root, config, perf)
    root.title("디바이스 성능 모니터링")

    root.eval('tk::PlaceWindow . center')
    # GUI 루프 시작
    root.mainloop()


if __name__ == "__main__":
    main()

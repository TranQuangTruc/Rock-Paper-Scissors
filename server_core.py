"""
Phần 1: rps_server_part1_core.py
Chức năng: Phần lõi của server, quản lý kết nối socket, đăng ký người chơi, gửi/nhận JSON, và ghi log.
Các phần sau (phần 2, 3) sẽ kế thừa hoặc nhập khẩu từ phần này.
"""

import socket
import threading
import json
import time
from datetime import datetime
import os
import queue

HOST = '0.0.0.0'
PORT = 9999
BUFFER_SIZE = 4096
LOGFILE = 'server_log.txt'

# Danh sách client đang online
clients_lock = threading.Lock()
clients = {}  # name -> {'conn': socket, 'addr': addr, 'queue': Queue}

# Hàng đợi chia sẻ cho GUI (phần 3)
gui_queue = queue.Queue()

# Tạo thư mục lưu lịch sử nếu chưa có
os.makedirs('history', exist_ok=True)

# --- GHI LOG ---
log_lock = threading.Lock()

def server_log(msg):
    """Ghi log ra file và gửi thông báo đến GUI"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{timestamp}] {msg}'
    with log_lock:
        with open(LOGFILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    try:
        gui_queue.put(('log', line))
    except Exception:
        pass

# --- HÀM GỬI JSON ---
def send_json(conn, obj):
    try:
        data = json.dumps(obj) + '\n'
        conn.sendall(data.encode('utf-8'))
    except Exception as e:
        server_log(f'Lỗi gửi dữ liệu đến client: {e}')

# --- LỚP SERVER CORE ---
class ServerCore:
    """Lớp server cơ bản, quản lý socket và kết nối client."""
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.stop_event = threading.Event()
        self._server_sock = None

    def start(self):
        t = threading.Thread(target=self._serve_forever, daemon=True)
        t.start()
        server_log(f'ServerCore khởi động tại {self.host}:{self.port}')
        return t

    def _serve_forever(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            s.listen()
            self._server_sock = s
            s.settimeout(1.0)
            while not self.stop_event.is_set():
                try:
                    conn, addr = s.accept()
                    server_log(f'Kết nối mới từ {addr}')
                    threading.Thread(target=self._client_worker, args=(conn, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    server_log(f'Lỗi khi chấp nhận kết nối: {e}')
                    break

    def stop(self):
        self.stop_event.set()
        try:
            if self._server_sock:
                self._server_sock.close()
        except:
            pass
        server_log('ServerCore đã dừng')

    def _client_worker(self, conn, addr):
        name = None
        buff = ''
        try:
            while True:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                buff += data.decode('utf-8')
                while '\n' in buff:
                    line, buff = buff.split('\n', 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.strip())
                    except Exception:
                        server_log(f'JSON không hợp lệ từ {addr}: {line}')
                        continue

                    # --- Đăng ký tên người chơi ---
                    if msg.get('action') == 'register' and msg.get('name'):
                        name = msg.get('name')
                        with clients_lock:
                            if name in clients:
                                send_json(conn, {'type': 'error', 'note': 'name_taken'})
                                server_log(f'Đăng ký thất bại: tên đã tồn tại ({name}) từ {addr}')
                                continue
                            clients[name] = {'conn': conn, 'addr': addr, 'queue': queue.Queue()}
                        send_json(conn, {'type': 'ok', 'note': 'registered'})
                        server_log(f'{name} đã đăng ký từ {addr}')
                        self.on_register(name)

                    # --- Gọi xử lý riêng ---
                    self.process_message(msg, conn, addr)
        except Exception as e:
            server_log(f'Lỗi kết nối {addr}: {e}')
        finally:
            if name:
                server_log(f'Client {name} đã ngắt kết nối')
                self.on_disconnect(name)
                with clients_lock:
                    if name in clients:
                        try:
                            clients[name]['conn'].close()
                        except:
                            pass
                        del clients[name]
            try:
                conn.close()
            except:
                pass

    # --- Các hàm có thể ghi đè ---
    def process_message(self, msg, conn, addr):
        """Xử lý các thông điệp từ client (ghi đè ở phần sau)"""
        try:
            if msg.get('action') not in (None, 'register'):
                send_json(conn, {'type': 'error', 'note': 'unknown_action'})
        except Exception:
            pass

    def on_register(self, name):
        try:
            gui_queue.put(('players', list(clients.keys())))
        except Exception:
            pass

    def on_disconnect(self, name):
        try:
            gui_queue.put(('players', list(clients.keys())))
        except Exception:
            pass

if __name__ == '__main__':
    core = ServerCore()
    core.start()
    print('ServerCore đang chạy. Nhấn Ctrl+C để dừng.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        core.stop()

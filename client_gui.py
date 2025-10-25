# client_gui.py
import socket
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from json_helper import send_json, recv_json
import time
import os
from datetime import datetime

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999

# ---------------------------
# Helper: lưu lịch sử trận đấu
# ---------------------------
def append_history(player, opponent, result, score_str):
    fname = f"history_{player}.txt"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'[{timestamp}] vs {opponent} — {result} ({score_str})\n'
    try:
        with open(fname, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print("Lỗi ghi lịch sử:", e)

# ---------------------------
# Client logic (socket + JSON)
# ---------------------------
class RPSGuiClient:
    def __init__(self, gui_queue):
        self.sock = None
        self.name = None
        self.match_id = None
        self.opponent = None
        self.running = False
        self.gui_queue = gui_queue
        self.recv_thread = None
        self.recv_buffer = b''

    def connect(self, host, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.running = True
            self.recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.recv_thread.start()
            return True, "Kết nối thành công"
        except Exception as e:
            self.running = False
            return False, str(e)

    def close(self):
        try:
            if self.sock:
                try:
                    # If in match, inform quit
                    if self.name:
                        send_json(self.sock, {'action': 'quit', 'player': self.name})
                except:
                    pass
                self.sock.close()
        except:
            pass
        self.running = False

    def send(self, obj):
        try:
            send_json(self.sock, obj)
        except Exception as e:
            self.gui_queue.put(('error', f'Lỗi gửi dữ liệu: {e}'))

    def receive_loop(self):
        """Luồng nhận dữ liệu: đọc JSON terminated bằng newline"""
        try:
            while self.running:
                msg = recv_json(self.sock)
                if not msg:
                    self.gui_queue.put(('disconnected', None))
                    self.running = False
                    break
                # đẩy message về GUI để xử lý
                self.gui_queue.put(('msg', msg))
        except Exception as e:
            self.gui_queue.put(('error', f'Lỗi nhận dữ liệu: {e}'))
            self.running = False

# ---------------------------
# Tkinter GUI
# ---------------------------
class RPSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RPS - Client GUI")
        self.geometry("480x420")
        self.resizable(False, False)
        # Dark gaming theme (D)
        self.configure(bg='#111218')  # very dark background
        self.style = ttk.Style(self)
        # ttk theme tweaks
        try:
            self.style.theme_use('clam')
        except:
            pass
        self.style.configure('TLabel', background='#111218', foreground='#E6E6E6', font=('Segoe UI', 10))
        self.style.configure('TButton', background='#1f2937', foreground='#E6E6E6', font=('Segoe UI', 10), padding=6)
        self.style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#FFFFFF', background='#111218')

        # Queue for communication from socket thread
        self.gui_queue = queue.Queue()

        # client logic
        self.client = RPSGuiClient(self.gui_queue)

        # UI components
        self.create_widgets()

        # schedule GUI queue checking
        self.after(100, self.process_gui_queue)

    def create_widgets(self):
        pad = 10

        header = ttk.Label(self, text="Rock - Paper - Scissors (GUI)", style='Header.TLabel')
        header.place(x=16, y=12)

        # Connection frame
        frm_conn = tk.Frame(self, bg='#121216', bd=0)
        frm_conn.place(x=16, y=48, width=448, height=84)

        ttk.Label(frm_conn, text="Server:").place(x=8, y=8)
        self.ent_host = ttk.Entry(frm_conn)
        self.ent_host.insert(0, SERVER_HOST)
        self.ent_host.place(x=70, y=8, width=140)

        ttk.Label(frm_conn, text="Port:").place(x=230, y=8)
        self.ent_port = ttk.Entry(frm_conn)
        self.ent_port.insert(0, str(SERVER_PORT))
        self.ent_port.place(x=280, y=8, width=60)

        ttk.Label(frm_conn, text="Tên bạn:").place(x=8, y=40)
        self.ent_name = ttk.Entry(frm_conn)
        self.ent_name.place(x=70, y=40, width=160)

        self.btn_connect = ttk.Button(frm_conn, text="Kết nối & Đăng ký", command=self.on_connect)
        self.btn_connect.place(x=260, y=40, width=160)

        # Players / Match frame
        frm_players = tk.Frame(self, bg='#111218')
        frm_players.place(x=16, y=144, width=448, height=120)

        ttk.Label(frm_players, text="Đối thủ (nhập tên):").place(x=8, y=6)
        self.ent_opponent = ttk.Entry(frm_players)
        self.ent_opponent.place(x=150, y=6, width=160)

        self.btn_challenge = ttk.Button(frm_players, text="Thách đấu", command=self.on_challenge, state='disabled')
        self.btn_challenge.place(x=320, y=4, width=110)

        ttk.Label(frm_players, text="Thông tin trò chơi:").place(x=8, y=40)
        self.lbl_status = ttk.Label(frm_players, text="Chưa kết nối", wraplength=320)
        self.lbl_status.place(x=8, y=64)

        # Gameplay frame
        frm_game = tk.Frame(self, bg='#0f1113')
        frm_game.place(x=16, y=276, width=448, height=120)

        ttk.Label(frm_game, text="Lựa chọn của bạn:", background='#0f1113').place(x=8, y=8)
        self.btn_rock = ttk.Button(frm_game, text="Rock", command=lambda: self.send_move('rock'), state='disabled')
        self.btn_rock.place(x=20, y=36, width=110)

        self.btn_paper = ttk.Button(frm_game, text="Paper", command=lambda: self.send_move('paper'), state='disabled')
        self.btn_paper.place(x=150, y=36, width=110)

        self.btn_scissors = ttk.Button(frm_game, text="Scissors", command=lambda: self.send_move('scissors'), state='disabled')
        self.btn_scissors.place(x=280, y=36, width=110)

        ttk.Label(frm_game, text="Log:").place(x=8, y=72)
        self.txt_log = tk.Text(frm_game, height=12, width=62, bg='#0b0b0c', fg='#dcdcdc', bd=0)

        self.txt_log.place(x=8, y=88)

        # Close handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------
    # UI actions
    # ---------------------------
    def on_connect(self):
        host = self.ent_host.get().strip()
        try:
            port = int(self.ent_port.get().strip())
        except:
            messagebox.showerror("Lỗi", "Port phải là số")
            return
        if not host:
            messagebox.showerror("Lỗi", "Nhập host")
            return
        ok, msg = self.client.connect(host, port)
        if not ok:
            messagebox.showerror("Lỗi kết nối", msg)
            return
        # register
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Nhập tên trước khi đăng ký")
            return
        self.client.name = name
        self.client.send({'action': 'register', 'name': name})
        self.set_status(f'Kết nối tới {host}:{port} — Đã đăng ký là "{name}"')
        self.btn_connect.config(state='disabled')
        self.btn_challenge.config(state='normal')
        # enable later when match starts: move buttons controlled by events

    def on_challenge(self):
        opp = self.ent_opponent.get().strip()
        if not opp:
            messagebox.showwarning("Cảnh báo", "Nhập tên đối thủ để thách đấu")
            return
        if not self.client.running:
            messagebox.showerror("Lỗi", "Chưa kết nối server")
            return
        self.client.send({'action': 'challenge', 'from': self.client.name, 'to': opp})
        self.append_log(f"Đã gửi thách đấu tới {opp} — chờ phản hồi...")

    def on_accept(self, challenger):
        # gửi accept
        if not self.client.running:
            return
        self.client.send({'action': 'accept', 'from': self.client.name, 'to': challenger})
        self.append_log(f"Đã chấp nhận thách đấu từ {challenger}")

    def send_move(self, move):
        if not self.client.running or not self.client.match_id:
            messagebox.showwarning("Không có trận", "Bạn chưa trong trận đấu")
            return
        self.append_log(f"Bạn đã chọn: {move}")
        obj = {'action': 'move', 'player': self.client.name, 'move': move, 'match_id': self.client.match_id}
        self.client.send(obj)
        # disable move buttons until next round
        self.set_move_buttons(False)

    def set_move_buttons(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.btn_rock.config(state=state)
        self.btn_paper.config(state=state)
        self.btn_scissors.config(state=state)

    def set_status(self, text):
        self.lbl_status.config(text=text)

    def append_log(self, text):
        ts = datetime.now().strftime('%H:%M:%S')
        self.txt_log.insert('end', f'[{ts}] {text}\n')
        self.txt_log.see('end')

    # ---------------------------
    # Process messages from socket thread
    # ---------------------------
    def process_gui_queue(self):
        try:
            while True:
                item = self.gui_queue.get_nowait()
                tag, payload = item
                if tag == 'msg':
                    self.handle_server_message(payload)
                elif tag == 'error':
                    messagebox.showerror("Lỗi", payload)
                elif tag == 'disconnected':
                    messagebox.showwarning("Đã mất kết nối", "Server đã ngắt kết nối")
                    self.set_status("Đã mất kết nối")
                    self.btn_challenge.config(state='disabled')
                    self.set_move_buttons(False)
                else:
                    print("Unknown queue tag:", tag, payload)
        except queue.Empty:
            pass
        # schedule again
        self.after(100, self.process_gui_queue)

    def handle_server_message(self, msg):
        # Server có thể gửi: 'type': 'challenge', 'match_start', 'round_result', 'match_end'
        try:
            # For debug:
            # self.append_log(f"RECV: {msg}")
            mtype = msg.get('type') or msg.get('action') or None

            # Challenge received
            if msg.get('type') == 'challenge' or mtype == 'challenge':
                fr = msg.get('from') or msg.get('from_name') or msg.get('challenger')
                if fr:
                    # hỏi user có chấp nhận không
                    ans = messagebox.askyesno("Thách đấu", f"Bạn được thách đấu từ {fr}. Chấp nhận?")
                    if ans:
                        self.on_accept(fr)
                    else:
                        self.append_log(f"Từ chối thách đấu từ {fr}")
                else:
                    self.append_log("Nhận thách đấu (không rõ tên)")

            # Match start
            elif msg.get('type') == 'match_start' or mtype == 'match_start':
                opp = msg.get('opponent')
                mid = msg.get('match_id') or msg.get('id')
                self.client.match_id = mid
                self.client.opponent = opp
                self.set_status(f"Đang chơi với {opp} (match {mid})")
                self.append_log(f"Trận bắt đầu với {opp}")
                # enable move buttons
                self.set_move_buttons(True)

            # Round result
            elif msg.get('type') == 'round_result' or mtype == 'round_result':
                you = msg.get('you')
                score = msg.get('score')
                if you == 'win':
                    self.append_log(f"Bạn thắng round này — {score}")
                elif you == 'lose':
                    self.append_log(f"Bạn thua round này — {score}")
                elif you == 'draw':
                    self.append_log(f"Hòa round này — {score}")
                # allow next move (unless match finished)
                self.set_move_buttons(True)

            # Match end
            elif msg.get('type') == 'match_end' or mtype == 'match_end':
                result = msg.get('result')
                score = msg.get('score') or msg.get('score_str') or ""
                reason = msg.get('reason')
                opp = self.client.opponent or msg.get('opponent')
                if result == 'win':
                    self.append_log(f"Bạn thắng trận! ({score})")
                    append_history(self.client.name, opp or "unknown", "Win", score)
                elif result == 'lose':
                    self.append_log(f"Bạn thua trận! ({score})")
                    append_history(self.client.name, opp or "unknown", "Lose", score)
                else:
                    # maybe reason or other format
                    self.append_log(f"Trận kết thúc: {result} {reason or ''}")
                    append_history(self.client.name, opp or "unknown", f"End({result})", score)
                # reset match state
                self.client.match_id = None
                self.client.opponent = None
                self.set_status("Trong trạng thái chờ")
                self.set_move_buttons(False)

            # Online list (optional if server supports)
            elif msg.get('type') == 'online_list':
                players = msg.get('players', [])
                self.append_log("Online: " + ", ".join(players))

            # generic error
            elif msg.get('type') == 'error':
                note = msg.get('note') or msg.get('message') or str(msg)
                self.append_log("Error: " + note)

            else:
                # Unknown message -> log it
                self.append_log("Tin nhắn server: " + str(msg))

        except Exception as e:
            print("Lỗi xử lý message:", e)
            self.append_log("Lỗi xử lý message: " + str(e))

    def on_close(self):
        if messagebox.askokcancel("Thoát", "Bạn có chắc muốn thoát?"):
            try:
                self.client.close()
            except:
                pass
            self.destroy()

# ---------------------------
# Run app
# ---------------------------
if __name__ == "__main__":
    # ensure history dir (optional)
    os.makedirs('.', exist_ok=True)
    app = RPSApp()
    app.mainloop()
# client_gui.py
import socket
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from json_helper import send_json, recv_json
import time
import os
from datetime import datetime

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 9999

# ---------------------------
# Helper: lưu / đọc / xóa lịch sử trận đấu
# ---------------------------
def history_filename(player_name):
    return f"history_{player_name}.txt"

def append_history(player, opponent, result, score_str):
    fname = history_filename(player)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'[{timestamp}] vs {opponent} — {result} ({score_str})\n'
    try:
        with open(fname, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        print("Lỗi ghi lịch sử:", e)

def read_history(player):
    fname = history_filename(player)
    if not os.path.exists(fname):
        return []
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            lines = [line.rstrip('\n') for line in f.readlines()]
        return lines
    except Exception as e:
        print("Lỗi đọc lịch sử:", e)
        return []

def delete_history_file(player):
    fname = history_filename(player)
    try:
        if os.path.exists(fname):
            os.remove(fname)
            return True
        return False
    except Exception as e:
        print("Lỗi xóa lịch sử:", e)
        return False

# ---------------------------
# Client logic (socket + JSON)
# ---------------------------
class RPSGuiClient:
    def __init__(self, gui_queue):
        self.sock = None
        self.name = None
        self.match_id = None
        self.opponent = None
        self.running = False
        self.gui_queue = gui_queue
        self.recv_thread = None

    def connect(self, host, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.running = True
            self.recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.recv_thread.start()
            return True, "Kết nối thành công"
        except Exception as e:
            self.running = False
            return False, str(e)

    def close(self):
        try:
            if self.sock:
                try:
                    if self.name:
                        send_json(self.sock, {'action': 'quit', 'player': self.name})
                except:
                    pass
                self.sock.close()
        except:
            pass
        self.running = False

    def send(self, obj):
        try:
            send_json(self.sock, obj)
        except Exception as e:
            self.gui_queue.put(('error', f'Lỗi gửi dữ liệu: {e}'))

    def receive_loop(self):
        try:
            while self.running:
                msg = recv_json(self.sock)
                if not msg:
                    self.gui_queue.put(('disconnected', None))
                    self.running = False
                    break
                self.gui_queue.put(('msg', msg))
        except Exception as e:
            self.gui_queue.put(('error', f'Lỗi nhận dữ liệu: {e}'))
            self.running = False

# ---------------------------
# Tkinter GUI
# ---------------------------
class RPSApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RPS - Client GUI")
        self.geometry("520x460")
        self.resizable(False, False)
        # Dark gaming theme
        self.configure(bg='#111218')
        self.style = ttk.Style(self)
        try:
            self.style.theme_use('clam')
        except:
            pass
        self.style.configure('TLabel', background='#111218', foreground='#E6E6E6', font=('Segoe UI', 10))
        self.style.configure('TButton', background='#1f2937', foreground='#E6E6E6', font=('Segoe UI', 10), padding=6)
        self.style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#FFFFFF', background='#111218')

        # Queue for communication from socket thread
        self.gui_queue = queue.Queue()

        # client logic
        self.client = RPSGuiClient(self.gui_queue)

        # UI components
        self.create_widgets()

        # schedule GUI queue checking
        self.after(100, self.process_gui_queue)

    def create_widgets(self):
        pad = 10

        header = ttk.Label(self, text="Rock - Paper - Scissors (GUI)", style='Header.TLabel')
        header.place(x=16, y=12)

        # Connection frame
        frm_conn = tk.Frame(self, bg='#121216', bd=0)
        frm_conn.place(x=16, y=48, width=488, height=84)

        ttk.Label(frm_conn, text="Server:").place(x=8, y=8)
        self.ent_host = ttk.Entry(frm_conn)
        self.ent_host.insert(0, SERVER_HOST)
        self.ent_host.place(x=70, y=8, width=160)

        ttk.Label(frm_conn, text="Port:").place(x=240, y=8)
        self.ent_port = ttk.Entry(frm_conn)
        self.ent_port.insert(0, str(SERVER_PORT))
        self.ent_port.place(x=280, y=8, width=60)

        ttk.Label(frm_conn, text="Your name:").place(x=8, y=40)
        self.ent_name = ttk.Entry(frm_conn)
        self.ent_name.place(x=90, y=40, width=180)

        self.btn_connect = ttk.Button(frm_conn, text="Connect & Register", command=self.on_connect)
        self.btn_connect.place(x=290, y=40, width=180)

        # Players / Match frame
        frm_players = tk.Frame(self, bg='#111218')
        frm_players.place(x=16, y=144, width=488, height=120)

        ttk.Label(frm_players, text="Opponent (enter name):").place(x=8, y=6)
        self.ent_opponent = ttk.Entry(frm_players)
        self.ent_opponent.place(x=170, y=6, width=180)

        self.btn_challenge = ttk.Button(frm_players, text="Challenge", command=self.on_challenge, state='disabled')
        self.btn_challenge.place(x=360, y=4, width=110)

        # Add View History button (auto placed nicely)
        self.btn_history = ttk.Button(frm_players, text="View History", command=self.on_view_history, state='disabled')
        self.btn_history.place(x=360, y=38, width=110)

        ttk.Label(frm_players, text="Game info:").place(x=8, y=40)
        self.lbl_status = ttk.Label(frm_players, text="Not connected", wraplength=340)
        self.lbl_status.place(x=8, y=64)

        # Gameplay frame
        frm_game = tk.Frame(self, bg='#0f1113')
        frm_game.place(x=16, y=276, width=488, height=160)

        ttk.Label(frm_game, text="Your choice:", background='#0f1113').place(x=8, y=8)
        self.btn_rock = ttk.Button(frm_game, text="Rock", command=lambda: self.send_move('rock'), state='disabled')
        self.btn_rock.place(x=20, y=36, width=120)

        self.btn_paper = ttk.Button(frm_game, text="Paper", command=lambda: self.send_move('paper'), state='disabled')
        self.btn_paper.place(x=176, y=36, width=120)

        self.btn_scissors = ttk.Button(frm_game, text="Scissors", command=lambda: self.send_move('scissors'), state='disabled')
        self.btn_scissors.place(x=332, y=36, width=120)

        ttk.Label(frm_game, text="Log:").place(x=8, y=80)
        self.txt_log = tk.Text(frm_game, height=14, width=62, bg='#0b0b0c', fg='#dcdcdc', bd=0)
        self.txt_log.place(x=8, y=100)

        # Close handler
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------------------------
    # UI actions
    # ---------------------------
    def on_connect(self):
        host = self.ent_host.get().strip()
        try:
            port = int(self.ent_port.get().strip())
        except:
            messagebox.showerror("Error", "Port must be a number")
            return
        if not host:
            messagebox.showerror("Error", "Enter host")
            return
        ok, msg = self.client.connect(host, port)
        if not ok:
            messagebox.showerror("Connection error", msg)
            return
        # register
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Enter a name before registering")
            return
        self.client.name = name
        self.client.send({'action': 'register', 'name': name})
        self.set_status(f'Connected to {host}:{port} — Registered as "{name}"')
        self.btn_connect.config(state='disabled')
        self.btn_challenge.config(state='normal')
        self.btn_history.config(state='normal')

    def on_challenge(self):
        opp = self.ent_opponent.get().strip()
        if not opp:
            messagebox.showwarning("Warning", "Enter opponent name to challenge")
            return
        if not self.client.running:
            messagebox.showerror("Error", "Not connected to server")
            return
        self.client.send({'action': 'challenge', 'from': self.client.name, 'to': opp})
        self.append_log(f"Sent challenge to {opp} — waiting...")

    def on_accept(self, challenger):
        if not self.client.running:
            return
        self.client.send({'action': 'accept', 'from': self.client.name, 'to': challenger})
        self.append_log(f"Accepted challenge from {challenger}")

    def send_move(self, move):
        if not self.client.running or not self.client.match_id:
            messagebox.showwarning("No match", "You are not in a match")
            return
        self.append_log(f"You chose: {move}")
        obj = {'action': 'move', 'player': self.client.name, 'move': move, 'match_id': self.client.match_id}
        self.client.send(obj)
        # disable move buttons until next round/result
        self.set_move_buttons(False)

    def set_move_buttons(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.btn_rock.config(state=state)
        self.btn_paper.config(state=state)
        self.btn_scissors.config(state=state)

    def set_status(self, text):
        self.lbl_status.config(text=text)

    def append_log(self, text):
        ts = datetime.now().strftime('%H:%M:%S')
        self.txt_log.insert('end', f'[{ts}] {text}\n')
        self.txt_log.see('end')

    # ---------------------------
    # History UI
    # ---------------------------
    def on_view_history(self):
        """Open a popup showing history and allow deleting it."""
        if not self.client.name:
            messagebox.showwarning("Warning", "You must register a name first")
            return

        hist_lines = read_history(self.client.name)

        popup = tk.Toplevel(self)
        popup.title(f"History - {self.client.name}")
        popup.geometry("520x360")
        popup.configure(bg='#111218')

        lbl = ttk.Label(popup, text=f"History for {self.client.name}", style='Header.TLabel')
        lbl.pack(pady=(10, 6))

        txt = tk.Text(popup, height=14, width=64, bg='#0b0b0c', fg='#dcdcdc', bd=0)
        txt.pack(padx=8, pady=(0, 6))
        if hist_lines:
            for line in hist_lines:
                txt.insert('end', line + '\n')
        else:
            txt.insert('end', 'No history found.\n')
        txt.config(state='disabled')

        frm_btn = tk.Frame(popup, bg='#111218')
        frm_btn.pack(pady=6)

        def on_delete_history():
            if messagebox.askyesno("Confirm", "Delete history file permanently?"):
                ok = delete_history_file(self.client.name)
                if ok:
                    messagebox.showinfo("Deleted", "History deleted.")
                    txt.config(state='normal')
                    txt.delete('1.0', 'end')
                    txt.insert('end', 'No history found.\n')
                    txt.config(state='disabled')
                else:
                    messagebox.showwarning("Warning", "No history file to delete.")

        btn_del = ttk.Button(frm_btn, text="Delete History", command=on_delete_history)
        btn_del.pack(side='left', padx=6)

        btn_close = ttk.Button(frm_btn, text="Close", command=popup.destroy)
        btn_close.pack(side='left', padx=6)

    # ---------------------------
    # Process messages from socket thread
    # ---------------------------
    def process_gui_queue(self):
        try:
            while True:
                item = self.gui_queue.get_nowait()
                tag, payload = item
                if tag == 'msg':
                    self.handle_server_message(payload)
                elif tag == 'error':
                    messagebox.showerror("Error", payload)
                elif tag == 'disconnected':
                    messagebox.showwarning("Disconnected", "Server disconnected")
                    self.set_status("Disconnected")
                    self.btn_challenge.config(state='disabled')
                    self.btn_history.config(state='disabled')
                    self.set_move_buttons(False)
                else:
                    print("Unknown queue tag:", tag, payload)
        except queue.Empty:
            pass
        self.after(100, self.process_gui_queue)

    def handle_server_message(self, msg):
        try:
            mtype = msg.get('type') or msg.get('action') or None

            # Challenge received
            if msg.get('type') == 'challenge' or mtype == 'challenge':
                fr = msg.get('from') or msg.get('from_name') or msg.get('challenger')
                if fr:
                    ans = messagebox.askyesno("Challenge", f"You have been challenged by {fr}. Accept?")
                    if ans:
                        self.on_accept(fr)
                    else:
                        self.append_log(f"Declined challenge from {fr}")
                else:
                    self.append_log("Received challenge (unknown name)")

            # Match start
            elif msg.get('type') == 'match_start' or mtype == 'match_start':
                opp = msg.get('opponent')
                mid = msg.get('match_id') or msg.get('id')
                self.client.match_id = mid
                self.client.opponent = opp
                self.set_status(f"In match vs {opp} (match {mid})")
                self.append_log(f"Match started with {opp}")
                # enable move buttons
                self.set_move_buttons(True)

            # Round result
            elif msg.get('type') == 'round_result' or mtype == 'round_result':
                you = msg.get('you')
                score = msg.get('score')
                if you == 'win':
                    self.append_log(f"You win this round — {score}")
                elif you == 'lose':
                    self.append_log(f"You lose this round — {score}")
                elif you == 'draw':
                    self.append_log(f"Draw this round — {score}")
                # allow next move (unless match finished)
                self.set_move_buttons(True)

            # Match end
            elif msg.get('type') == 'match_end' or mtype == 'match_end':
                result = msg.get('result')
                score = msg.get('score') or msg.get('score_str') or ""
                reason = msg.get('reason')
                opp = self.client.opponent or msg.get('opponent') or "unknown"
                if result == 'win':
                    self.append_log(f"You won the match! ({score})")
                    append_history(self.client.name, opp, "Win", score)
                elif result == 'lose':
                    self.append_log(f"You lost the match. ({score})")
                    append_history(self.client.name, opp, "Lose", score)
                else:
                    self.append_log(f"Match ended: {result} {reason or ''}")
                    append_history(self.client.name, opp, f"End({result})", score)
                # reset match state
                self.client.match_id = None
                self.client.opponent = None
                self.set_status("Waiting")
                self.set_move_buttons(False)

            # Online list (optional)
            elif msg.get('type') == 'online_list':
                players = msg.get('players', [])
                self.append_log("Online: " + ", ".join(players))

            # generic error
            elif msg.get('type') == 'error':
                note = msg.get('note') or msg.get('message') or str(msg)
                self.append_log("Error: " + note)

            else:
                self.append_log("Server message: " + str(msg))

        except Exception as e:
            print("Error handling message:", e)
            self.append_log("Error handling message: " + str(e))

    def on_close(self):
        if messagebox.askokcancel("Quit", "Are you sure you want to quit?"):
            try:
                self.client.close()
            except:
                pass
            self.destroy()

# ---------------------------
# Run app
# ---------------------------
if __name__ == "__main__":
    os.makedirs('.', exist_ok=True)
    app = RPSApp()
    app.mainloop()

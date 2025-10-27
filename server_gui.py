"""
Phần 3: server_gui.py
Chức năng: Tạo giao diện Tkinter cho server để hiển thị danh sách người chơi online, các trận đấu đang diễn ra, và log hoạt động.
Tích hợp với server_core và server_match để nhận thông tin cập nhật qua hàng đợi (queue).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
from server_match import MatchServer, gui_queue

class ServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('Rock–Paper–Scissors Server')
        self.root.geometry('900x600')
        self.root.resizable(False, False)

        # --- FRAME CHÍNH ---
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill='both', expand=True)

        # --- DANH SÁCH NGƯỜI CHƠI ---
        frame_players = ttk.LabelFrame(main_frame, text='Người chơi Online')
        frame_players.place(x=10, y=10, width=280, height=250)

        self.list_players = tk.Listbox(frame_players, font=('Consolas', 11))
        self.list_players.pack(fill='both', expand=True, padx=5, pady=5)

        # --- DANH SÁCH TRẬN ---
        frame_matches = ttk.LabelFrame(main_frame, text='Trận đang diễn ra')
        frame_matches.place(x=310, y=10, width=570, height=250)

        self.tree_matches = ttk.Treeview(frame_matches, columns=('id', 'p1', 'p2', 'state'), show='headings')
        self.tree_matches.heading('id', text='ID trận')
        self.tree_matches.heading('p1', text='Người chơi 1')
        self.tree_matches.heading('p2', text='Người chơi 2')
        self.tree_matches.heading('state', text='Trạng thái')
        self.tree_matches.pack(fill='both', expand=True, padx=5, pady=5)

        # --- KHU VỰC LOG ---
        frame_log = ttk.LabelFrame(main_frame, text='Nhật ký Server')
        frame_log.place(x=10, y=270, width=870, height=320)

        self.text_log = scrolledtext.ScrolledText(frame_log, font=('Consolas', 11), wrap='word')
        self.text_log.pack(fill='both', expand=True, padx=5, pady=5)

        # --- NÚT DỪNG SERVER ---
        self.btn_stop = ttk.Button(main_frame, text='Dừng Server', command=self.stop_server)
        self.btn_stop.place(x=780, y=10, width=100, height=30)

        self.server = None
        self.running = True

        # Tạo luồng đọc dữ liệu từ hàng đợi
        self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
        self.update_thread.start()

    def log(self, msg):
        self.text_log.insert('end', msg + '\n')
        self.text_log.see('end')

    def update_loop(self):
        while self.running:
            try:
                item = gui_queue.get(timeout=0.5)
                if not item:
                    continue
                if item[0] == 'log':
                    self.log(item[1])
                elif item[0] == 'players':
                    self.update_players(item[1])
                elif item[0] == 'matches':
                    self.update_matches(item[1])
            except queue.Empty:
                continue

    def update_players(self, players):
        self.list_players.delete(0, 'end')
        for p in players:
            self.list_players.insert('end', p)

    def update_matches(self, match_list):
        for i in self.tree_matches.get_children():
            self.tree_matches.delete(i)
        for mid, p1, p2, st in match_list:
            self.tree_matches.insert('', 'end', values=(mid, p1, p2, st))

    def start_server(self):
        self.server = MatchServer()
        self.server_thread = threading.Thread(target=self.server.start, daemon=True)
        self.server_thread.start()
        self.log('✅ Server đã khởi động...')

    def stop_server(self):
        self.running = False
        if self.server:
            self.server.stop()
        self.log('🛑 Server đã dừng.')
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    gui = ServerGUI(root)
    gui.start_server()
    root.mainloop()

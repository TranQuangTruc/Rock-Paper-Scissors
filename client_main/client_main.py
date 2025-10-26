import socket
import threading
from json_helper import send_json, recv_json
from history import save_history

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

class RPSClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name = None
        self.opponent = None
        self.running = True
        self.in_match = False

    def connect(self):
        try:
            self.sock.connect((SERVER_HOST, SERVER_PORT))
            print("✅ Connected to server.")
        except Exception as e:
            print("❌ Cannot connect to server:", e)
            self.running = False

    def send(self, data):
        send_json(self.sock, data)

    def receive_loop(self):
        while self.running:
            msg = recv_json(self.sock)
            if not msg:
                print("❌ Server disconnected.")
                self.running = False
                break
            self.handle_message(msg)

    def handle_message(self, msg):
        msg_type = msg.get("type")

        if msg_type == "online_list":
            print("\n🟢 Online:", ", ".join(msg["players"]))

        elif msg_type == "match_start":
            self.opponent = msg["opponent"]
            self.in_match = True
            print(f"\n🎮 Trận đấu bắt đầu với {self.opponent} (best of 3)!")

        elif msg_type == "round_result":
            print(f"Round {msg['round']}: {msg['result']}")

        elif msg_type == "match_end":
            print(f"\n🏁 Kết thúc trận: {msg['result']} ({msg['score']})")
            save_history(self.name, self.opponent, msg["result"], msg["score"])
            self.opponent = None
            self.in_match = False

        elif msg_type == "error":
            print(f"⚠️ Lỗi: {msg['message']}")
            self.in_match = False
            self.opponent = None

        else:
            print("📩 Tin nhắn khác:", msg)

    def start(self):
        self.connect()
        if not self.running:
            return

        self.name = input("Nhập tên của bạn: ").strip()
        self.send({"type": "register", "name": self.name})

        threading.Thread(target=self.receive_loop, daemon=True).start()

        while self.running:
            if not self.in_match:
                print("\n== MENU ==")
                print("1. Xem danh sách online")
                print("2. Chọn đối thủ")
                print("3. Thoát game")
                choice = input("Chọn: ")

                if choice == "1":
                    self.send({"type": "get_online"})
                elif choice == "2":
                    opp = input("Nhập tên đối thủ: ").strip()
                    self.send({"type": "request_match", "opponent": opp})
                elif choice == "3":
                    self.send({"type": "quit"})
                    self.running = False
                    break
                else:
                    print("❌ Lựa chọn không hợp lệ.")
            else:
                move = input("\nChọn (rock/paper/scissors): ").lower()
                if move not in ["rock", "paper", "scissors"]:
                    print("⚠️ Nhập sai, vui lòng chọn rock/paper/scissors.")
                    continue
                self.send({"type": "play_move", "move": move})

        self.sock.close()
        print("👋 Đã thoát game.")

if __name__ == "__main__":
    client = RPSClient()
    client.start()

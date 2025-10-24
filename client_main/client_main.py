import socket
import threading
from json_helper import send_json, recv_json

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

class RPSClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.name = None
        self.opponent = None
        self.running = True

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
        """Luồng lắng nghe dữ liệu từ server."""
        while self.running:
            msg = recv_json(self.sock)
            if not msg:
                print("❌ Mất kết nối tới server.")
                self.running = False
                break
            self.handle_message(msg)

    def handle_message(self, msg):
        """Xử lý tin nhắn từ server."""
        msg_type = msg.get("type")

        if msg_type == "online_list":
            print("\n🟢 Danh sách người chơi online:")
            for p in msg["players"]:
                print("-", p)

        elif msg_type == "match_start":
            self.opponent = msg["opponent"]
            print(f"\n🎮 Trận đấu bắt đầu với {self.opponent}!")

        elif msg_type == "error":
            print(f"⚠️ Lỗi: {msg['message']}")

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
            if not self.opponent:
                print("\n== MENU ==")
                print("1. Xem danh sách online")
                print("2. Chọn đối thủ để đấu")
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
                print(f"⏳ Đang trong trận với {self.opponent}, chờ lượt...")

        self.sock.close()
        print("👋 Đã thoát game.")

if __name__ == "__main__":
    client = RPSClient()
    client.start()

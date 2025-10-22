import socket
from json_helper import send_json, recv_json

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5555

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("✅ Connected to server.")
    except Exception as e:
        print("❌ Cannot connect to server:", e)
        return

    name = input("Nhập tên của bạn: ").strip()
    send_json(sock, {"type": "register", "name": name})
    print(f"Đã gửi yêu cầu đăng ký tên: {name}")

    msg = recv_json(sock)
    if msg:
        print("Nhận phản hồi từ server:", msg)
    else:
        print("Không nhận được phản hồi (server có thể đã ngắt kết nối).")

    sock.close()
    print("👋 Đã ngắt kết nối.")

if __name__ == "__main__":
    main()

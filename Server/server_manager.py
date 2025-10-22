import socket
import threading
import json

HOST = '127.0.0.1'
PORT = 12345

players = {}  # name -> conn
lock = threading.Lock()

def broadcast(msg):
    with lock:
        for conn in players.values():
            conn.sendall(json.dumps({"type": "system", "msg": msg}).encode())

def handle_client(conn, addr):
    try:
        conn.sendall(json.dumps({"type": "ask_name", "msg": "Enter your name:"}).encode())
        name = conn.recv(1024).decode().strip()

        with lock:
            players[name] = conn

        print(f"✅ {name} joined from {addr}")
        broadcast(f"{name} has joined the game!")

        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode()
            print(f"💬 [{name}] says: {msg}")
            if msg.lower() == "exit":
                break

        print(f"🚪 {name} disconnected")
        broadcast(f"{name} has left the game!")

    except Exception as e:
        print("⚠️ Error with client:", e)
    finally:
        with lock:
            if name in players:
                del players[name]
        conn.close()

def start_server():
    print(f"🔹 Server running on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print("✅ Waiting for players...")

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()

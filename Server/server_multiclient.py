import socket
import threading

HOST = '127.0.0.1'
PORT = 12345
clients = []

def handle_client(conn, addr):
    print(f"👤 New client connected: {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break
            msg = data.decode()
            print(f"💬 From {addr}: {msg}")
            conn.sendall(f"Echo: {msg}".encode())
    except:
        pass
    finally:
        print(f"⚠️ Client disconnected: {addr}")
        conn.close()
        clients.remove(conn)

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"✅ Server listening on {HOST}:{PORT}")

        while True:
            conn, addr = server_socket.accept()
            clients.append(conn)
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    start_server()

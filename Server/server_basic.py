import socket

HOST = '127.0.0.1'
PORT = 12345

print("🔹 Server starting on port", PORT)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print("✅ Server is running. Waiting for client...")

    conn, addr = server_socket.accept()
    print(f"👤 Client connected: {addr}")

    with conn:
        data = conn.recv(1024).decode()
        print("📩 Client says:", data)
        conn.sendall("Hi from server!".encode())

    print("❌ Client disconnected.")

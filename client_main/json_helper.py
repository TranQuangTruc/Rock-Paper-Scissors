import json

def send_json(sock, data):
    """
    Gửi dữ liệu JSON qua socket.
    Mỗi gói kết thúc bằng newline để phân tách giữa các message.
    """
    message = json.dumps(data).encode('utf-8')
    sock.sendall(message + b'\n')


def recv_json(sock):
    """
    Nhận dữ liệu JSON từ socket (đọc đến newline).
    Trả về dict sau khi decode.
    """
    buffer = b''
    while True:
        part = sock.recv(1024)
        if not part:
            return None
        buffer += part
        if b'\n' in buffer:
            msg, _, buffer = buffer.partition(b'\n')
            return json.loads(msg.decode('utf-8'))

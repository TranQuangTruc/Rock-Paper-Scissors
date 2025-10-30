# client_main.py
import socket, json, threading

HOST = '127.0.0.1'
PORT = 5555

class Client:
    def __init__(self, name):
        self.name = name
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        self.sock.send(json.dumps({"name": self.name}).encode())
        threading.Thread(target=self.listen, daemon=True).start()

    def listen(self):
        while True:
            try:
                raw = self.sock.recv(4096).decode()
                if not raw:
                    break
                msg = json.loads(raw)
                self.handle(msg)
            except:
                break

    def handle(self, msg):
        t = msg.get("type")
        if t == "online_list":
            print("Online:", msg.get("players"))
        elif t == "challenge_request":
            frm = msg.get("from")
            print(f"{frm} challenged you. Type 'accept {frm}' or 'decline {frm}'")
        elif t == "challenge_start":
            print("Match started vs", msg.get("opponent"))
        elif t == "round_result":
            print("ROUND:", msg.get("message"), "SCORE:", msg.get("score"))
        elif t == "match_result":
            print("MATCH:", msg.get("message"))
        elif t == "error":
            print("ERROR:", msg.get("message"))
        elif t == "system":
            print("SYSTEM:", msg.get("message"))
        else:
            print("MSG:", msg)

    def send(self, obj):
        try:
            self.sock.send(json.dumps(obj).encode())
        except:
            pass

if __name__ == "__main__":
    name = input("Your name: ").strip()
    c = Client(name)
    while True:
        cmd = input("> ").strip().split()
        if not cmd: continue
        if cmd[0]=="quit":
            break
        if cmd[0]=="list":
            # just wait, server will push online_list
            continue
        if cmd[0]=="challenge" and len(cmd)>=2:
            c.send({"type":"challenge","to":cmd[1]})
        if cmd[0]=="accept" and len(cmd)>=2:
            c.send({"type":"challenge_response","to":cmd[1],"accept":True})
        if cmd[0]=="decline" and len(cmd)>=2:
            c.send({"type":"challenge_response","to":cmd[1],"accept":False})
        if cmd[0]=="move" and len(cmd)>=3:
            opp = cmd[1]; mv = cmd[2]
            c.send({"type":"move","to":opp,"move":mv})

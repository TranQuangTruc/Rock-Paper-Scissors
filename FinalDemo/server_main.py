# server_main.py
# Simple console server version with same logic (useful for quick tests)
import socket, threading, json, traceback

HOST = '127.0.0.1'
PORT = 5555

clients = {}  # name -> conn
lock = threading.Lock()
games = {}

def safe_send(conn, obj):
    try:
        conn.sendall(json.dumps(obj).encode())
    except:
        pass

def judge(a,b):
    a = a.lower() if a else ""
    b = b.lower() if b else ""
    if a == b: return 0
    wins = {"rock":"scissors","scissors":"paper","paper":"rock"}
    if wins.get(a) == b: return 1
    if wins.get(b) == a: return 2
    return 0

def handle_disconnect(name):
    with lock:
        to_remove = []
        for pair, game in list(games.items()):
            if name in pair:
                p1, p2 = pair
                other = p2 if p1 == name else p1
                if other in clients:
                    safe_send(clients[other], {"type":"match_result","message":"Opponent disconnected. You win."})
                to_remove.append(pair)
        for pair in to_remove:
            del games[pair]

def process_message(name, msg):
    t = msg.get("type")
    if t == "challenge":
        opponent = msg.get("to")
        with lock:
            if opponent not in clients:
                safe_send(clients[name], {"type":"error","message":"Opponent not found."})
                return
            safe_send(clients[opponent], {"type":"challenge_request","from":name})
    elif t == "challenge_response":
        opponent = msg.get("to")
        accept = msg.get("accept", False)
        pair = tuple(sorted([name, opponent]))
        with lock:
            if accept:
                games[pair] = {"players":list(pair),"score":{pair[0]:0,pair[1]:0},"round":1,"moves":{}}
                safe_send(clients[name], {"type":"challenge_start","opponent":opponent})
                safe_send(clients[opponent], {"type":"challenge_start","opponent":name})
            else:
                safe_send(clients[opponent], {"type":"challenge_declined","from":name})
    elif t == "move":
        to = msg.get("to"); mv = msg.get("move")
        pair = tuple(sorted([name, to]))
        with lock:
            game = games.get(pair)
            if not game:
                safe_send(clients[name], {"type":"error","message":"No active game."})
                return
            game["moves"][name] = mv
            if len(game["moves"])==2:
                p1,p2 = pair
                m1 = game["moves"].get(p1); m2 = game["moves"].get(p2)
                winner = judge(m1,m2)
                if winner==1:
                    game["score"][p1]+=1
                elif winner==2:
                    game["score"][p2]+=1
                # notify round_result
                for p in pair:
                    safe_send(clients[p], {"type":"round_result","score":game["score"], "message": f"Round {game['round']} result: {m1} vs {m2}"})
                if game["score"][p1]==2 or game["score"][p2]==2:
                    if game["score"][p1]>game["score"][p2]:
                        safe_send(clients[p1], {"type":"match_result","message":"You win the match."})
                        safe_send(clients[p2], {"type":"match_result","message":"You lose the match."})
                    else:
                        safe_send(clients[p2], {"type":"match_result","message":"You win the match."})
                        safe_send(clients[p1], {"type":"match_result","message":"You lose the match."})
                    del games[pair]
                else:
                    game["round"]+=1
                    game["moves"]={}
    else:
        safe_send(clients[name], {"type":"error","message":"Unknown type."})

def client_thread(conn, addr):
    name=None
    try:
        data=conn.recv(4096).decode()
        obj=json.loads(data); name=obj.get("name")
        with lock:
            if name in clients:
                safe_send(conn, {"type":"error","message":"Name taken"}); conn.close(); return
            clients[name]=conn
        print(f"{name} connected")
        while True:
            raw=conn.recv(4096).decode()
            if not raw: break
            msg=json.loads(raw)
            process_message(name,msg)
    except Exception:
        print("error",traceback.format_exc())
    finally:
        with lock:
            if name and name in clients: del clients[name]
        handle_disconnect(name)
        conn.close()
        print(f"{name} disconnected")

def main():
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST,PORT))
    s.listen()
    print("Server console running on",HOST,PORT)
    while True:
        conn,addr=s.accept()
        threading.Thread(target=client_thread,args=(conn,addr),daemon=True).start()

if __name__=="__main__":
    main()

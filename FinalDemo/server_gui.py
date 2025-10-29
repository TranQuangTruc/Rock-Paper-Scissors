# server_gui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import socket
import json
import traceback

HOST = '127.0.0.1'
PORT = 5555

def safe_send(conn, obj):
    try:
        conn.sendall(json.dumps(obj).encode())
    except Exception:
        pass

class ServerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Rock-Paper-Scissors Server")
        self.master.geometry("700x500")

        # UI
        frame_top = ttk.Frame(master)
        frame_top.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame_top, text="🟢 Online Players:").pack(side=tk.LEFT)
        self.online_list = tk.Listbox(master, height=6)
        self.online_list.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(master, text="⚔️ Ongoing Matches:").pack(anchor="w", padx=10)
        self.match_list = tk.Listbox(master, height=6)
        self.match_list.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(master, text="📜 Server Log:").pack(anchor="w", padx=10)
        self.log_box = scrolledtext.ScrolledText(master, height=12, state="disabled")
        self.log_box.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)

        # Data
        self.lock = threading.Lock()
        self.clients = {}   # name -> conn
        self.addr_map = {}  # conn -> addr
        # games: key = tuple(sorted([p1,p2])) -> value dict {players:[p1,p2], score:{p1:0,p2:0}, round:1, moves:{}}
        self.games = {}
        self.matches_history = {}  # pair_str -> result

        # Start server thread
        threading.Thread(target=self.start_server, daemon=True).start()

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.yview(tk.END)

    def refresh_ui(self):
        self.online_list.delete(0, tk.END)
        for name in sorted(self.clients.keys()):
            self.online_list.insert(tk.END, name)

        self.match_list.delete(0, tk.END)
        for pair, info in self.games.items():
            p1, p2 = pair
            score = info["score"]
            self.match_list.insert(tk.END, f"{p1} vs {p2} — {score[p1]}-{score[p2]} (R{info['round']})")

    def broadcast_online(self):
        with self.lock:
            players = list(self.clients.keys())
            for conn in self.clients.values():
                safe_send(conn, {"type": "online_list", "players": players})

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        self.log(f"🚀 Server running on {HOST}:{PORT}")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        name = None
        try:
            data = conn.recv(4096).decode()
            if not data:
                conn.close()
                return
            obj = json.loads(data)
            name = obj.get("name")
            if not name:
                safe_send(conn, {"type": "error", "message": "Name required."})
                conn.close()
                return

            with self.lock:
                if name in self.clients:
                    # name collision
                    safe_send(conn, {"type": "error", "message": "Name already taken."})
                    conn.close()
                    return
                self.clients[name] = conn
                self.addr_map[conn] = addr

            self.log(f"✅ {name} connected from {addr}")
            self.broadcast_system(f"{name} has joined.")
            self.broadcast_online()
            self.refresh_ui()

            # Listen loop
            while True:
                raw = conn.recv(4096).decode()
                if not raw:
                    break
                msg = json.loads(raw)
                self.process_message(name, msg)
        except Exception as e:
            self.log("⚠️ Error in client handler:\n" + traceback.format_exc())
        finally:
            # cleanup
            with self.lock:
                if name and name in self.clients:
                    del self.clients[name]
                if conn in self.addr_map:
                    del self.addr_map[conn]
            self.log(f"🚪 {name or addr} disconnected")
            self.broadcast_system(f"{name} has left.")
            # if player was in a game -> opponent wins
            if name:
                self.handle_disconnect_in_games(name)
            self.broadcast_online()
            self.refresh_ui()
            try:
                conn.close()
            except:
                pass

    def broadcast_system(self, text):
        with self.lock:
            for conn in self.clients.values():
                safe_send(conn, {"type": "system", "message": text})

    def process_message(self, name, msg):
        t = msg.get("type")
        if t == "challenge":
            opponent = msg.get("to")
            if not opponent:
                safe_send(self.clients[name], {"type": "error", "message": "No opponent specified."})
                return
            with self.lock:
                if opponent not in self.clients:
                    safe_send(self.clients[name], {"type": "error", "message": f"{opponent} not found."})
                    return
                # forward request to opponent
                safe_send(self.clients[opponent], {"type": "challenge_request", "from": name})
                self.log(f"{name} challenged {opponent}")

        elif t == "challenge_response":
            opponent = msg.get("to")  # opponent is the original challenger
            accepted = msg.get("accept", False)
            if not opponent or opponent not in self.clients:
                safe_send(self.clients[name], {"type": "error", "message": f"{opponent} not found."})
                return
            if accepted:
                # create game
                pair = tuple(sorted([name, opponent]))
                with self.lock:
                    if pair in self.games:
                        safe_send(self.clients[name], {"type": "error", "message": "Game already exists."})
                        return
                    self.games[pair] = {
                        "players": list(pair),
                        "score": {pair[0]: 0, pair[1]: 0},
                        "round": 1,
                        "moves": {}  # player -> move for current round
                    }
                # notify both players
                safe_send(self.clients[name], {"type": "challenge_start", "opponent": opponent})
                safe_send(self.clients[opponent], {"type": "challenge_start", "opponent": name})
                self.log(f"Match started: {pair[0]} vs {pair[1]}")
                self.refresh_ui()
            else:
                # notify challenger that it's declined
                if opponent in self.clients:
                    safe_send(self.clients[opponent], {"type": "challenge_declined", "from": name})
                self.log(f"{name} declined challenge from {opponent}")

        elif t == "move":
            to = msg.get("to")
            mv = msg.get("move")
            if not to or to not in self.clients:
                safe_send(self.clients[name], {"type": "error", "message": f"{to} not available."})
                return
            pair = tuple(sorted([name, to]))
            with self.lock:
                game = self.games.get(pair)
                if not game:
                    safe_send(self.clients[name], {"type": "error", "message": "No active game with that opponent."})
                    return
                # record move
                game["moves"][name] = mv
                self.log(f"Round {game['round']}: {name} -> {mv}")
                # if both moved, evaluate round
                if len(game["moves"]) == 2:
                    p1, p2 = pair
                    m1 = game["moves"].get(p1)
                    m2 = game["moves"].get(p2)
                    winner = self.judge(m1, m2)
                    if winner == 0:
                        # draw
                        round_msg_p1 = f"Round {game['round']} is a draw ({m1} vs {m2}). Score {game['score'][p1]}-{game['score'][p2]}"
                        round_msg_p2 = round_msg_p1
                        self.log(f"Round {game['round']} draw for {p1} vs {p2}")
                    elif winner == 1:
                        # p1 wins
                        game["score"][p1] += 1
                        round_msg_p1 = f"You win round {game['round']} ({m1} vs {m2}). Score {game['score'][p1]}-{game['score'][p2]}"
                        round_msg_p2 = f"You lose round {game['round']} ({m2} vs {m1}). Score {game['score'][p2]}-{game['score'][p1]}"
                        self.log(f"Round {game['round']} winner: {p1}")
                    else:
                        # p2 wins
                        game["score"][p2] += 1
                        round_msg_p2 = f"You win round {game['round']} ({m2} vs {m1}). Score {game['score'][p2]}-{game['score'][p1]}"
                        round_msg_p1 = f"You lose round {game['round']} ({m1} vs {m2}). Score {game['score'][p1]}-{game['score'][p2]}"
                        self.log(f"Round {game['round']} winner: {p2}")

                    # send round results
                    if p1 in self.clients:
                        safe_send(self.clients[p1], {"type": "round_result", "message": round_msg_p1, "score": game["score"]})
                    if p2 in self.clients:
                        safe_send(self.clients[p2], {"type": "round_result", "message": round_msg_p2, "score": game["score"]})

                    # check for match end (first to 2)
                    if game["score"][p1] == 2 or game["score"][p2] == 2:
                        # finalize
                        if game["score"][p1] > game["score"][p2]:
                            final_p1 = f"You win the match ({game['score'][p1]}-{game['score'][p2]})"
                            final_p2 = f"You lose the match ({game['score'][p2]}-{game['score'][p1]})"
                            result_text = f"{p1} beat {p2} ({game['score'][p1]}-{game['score'][p2]})"
                        else:
                            final_p2 = f"You win the match ({game['score'][p2]}-{game['score'][p1]})"
                            final_p1 = f"You lose the match ({game['score'][p1]}-{game['score'][p2]})"
                            result_text = f"{p2} beat {p1} ({game['score'][p2]}-{game['score'][p1]})"

                        if p1 in self.clients:
                            safe_send(self.clients[p1], {"type": "match_result", "message": final_p1, "result_text": result_text})
                        if p2 in self.clients:
                            safe_send(self.clients[p2], {"type": "match_result", "message": final_p2, "result_text": result_text})

                        # save match in server history
                        pair_str = f"{p1}_vs_{p2}"
                        self.matches_history[pair_str] = result_text
                        self.log(f"Match finished: {result_text}")

                        # remove game
                        del self.games[pair]
                        self.refresh_ui()
                        # broadcast matches changed (optional)
                    else:
                        # continue to next round
                        game["round"] += 1
                        game["moves"] = {}
        else:
            self.log(f"Unknown message type from {name}: {msg}")

        # update online list to all clients whenever there's activity (safe)
        self.broadcast_online()
        self.refresh_ui()

    def judge(self, a, b):
        # returns 0 draw, 1 winner is a, 2 winner is b
        a = a.lower() if a else ""
        b = b.lower() if b else ""
        if a == b:
            return 0
        wins = {
            "rock": "scissors",
            "scissors": "paper",
            "paper": "rock"
        }
        if wins.get(a) == b:
            return 1
        if wins.get(b) == a:
            return 2
        return 0

    def handle_disconnect_in_games(self, name):
        # if name is in any active game, award win to opponent
        to_remove = []
        with self.lock:
            for pair, game in list(self.games.items()):
                if name in pair:
                    p1, p2 = pair
                    other = p2 if p1 == name else p1
                    if other in self.clients:
                        safe_send(self.clients[other], {"type": "match_result", "message": "Opponent disconnected. You win by default.", "result_text": f"{other} wins (opponent disconnected)"})
                        self.log(f"{other} wins because {name} disconnected.")
                    to_remove.append(pair)
            for pair in to_remove:
                if pair in self.games:
                    del self.games[pair]
        self.refresh_ui()

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerGUI(root)
    root.mainloop()

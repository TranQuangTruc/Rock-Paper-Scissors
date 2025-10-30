# client_gui.py
import tkinter as tk
from tkinter import ttk, messagebox
import socket, threading, json, datetime

HOST = '127.0.0.1'
PORT = 5555

def safe_send(sock, obj):
    try:
        sock.sendall(json.dumps(obj).encode())
    except:
        pass

class GameClient:
    def __init__(self, root):
        self.root = root
        self.root.title("RPS Client")
        self.root.geometry("420x520")

        self.name_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Disconnected")
        self.online_var = tk.StringVar(value="")
        self.opponent_var = tk.StringVar()

        self.sock = None

        frame = ttk.Frame(root)
        frame.pack(padx=10, pady=10, fill=tk.X)

        ttk.Label(frame, text="Your name:").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.name_var).pack(fill=tk.X)

        ttk.Button(frame, text="Connect", command=self.connect).pack(pady=6)

        ttk.Label(frame, text="Online players:").pack(anchor="w", pady=(8,0))
        self.players_listbox = tk.Listbox(frame, height=6)
        self.players_listbox.pack(fill=tk.X)
        ttk.Button(frame, text="Select as opponent", command=self.select_opponent).pack(pady=4)

        ttk.Label(frame, text="Chosen opponent:").pack(anchor="w")
        ttk.Label(frame, textvariable=self.opponent_var).pack(anchor="w")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=8)
        for mv in ["rock", "paper", "scissors"]:
            ttk.Button(btn_frame, text=mv.title(), command=lambda m=mv: self.send_move(m)).pack(side=tk.LEFT, padx=6)

        ttk.Button(frame, text="Challenge selected", command=self.send_challenge).pack(pady=6)
        ttk.Button(frame, text="Show history", command=self.show_history).pack(pady=4)
        ttk.Button(frame, text="Quit", command=self.quit_app).pack(pady=4)

        ttk.Label(frame, textvariable=self.status_var).pack(pady=8)

        self.log_box = tk.Text(root, height=10, state="disabled")
        self.log_box.pack(fill=tk.BOTH, padx=10, pady=6, expand=True)

    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.yview(tk.END)

    def connect(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Name required", "Enter your name first.")
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            safe_send(self.sock, {"name": name})
            threading.Thread(target=self.listen, daemon=True).start()
            self.status_var.set("Connected")
            self.log("Connected to server.")
        except Exception as e:
            messagebox.showerror("Connection error", str(e))

    def listen(self):
        while True:
            try:
                raw = self.sock.recv(4096).decode()
                if not raw:
                    break
                msg = json.loads(raw)
                self.handle_message(msg)
            except Exception:
                break
        self.status_var.set("Disconnected")
        self.log("Disconnected from server.")

    def handle_message(self, msg):
        t = msg.get("type")
        if t == "online_list":
            players = msg.get("players", [])
            # remove self
            name = self.name_var.get().strip()
            players = [p for p in players if p != name]
            self.players_listbox.delete(0, tk.END)
            for p in players:
                self.players_listbox.insert(tk.END, p)
            self.log("Online list updated.")
        elif t == "challenge_request":
            frm = msg.get("from")
            ans = messagebox.askyesno("Challenge", f"{frm} challenged you. Accept?")
            if ans:
                self.opponent_var.set(frm)
                safe_send(self.sock, {"type":"challenge_response", "to": frm, "accept": True})
                self.status_var.set(f"Playing with {frm}")
            else:
                safe_send(self.sock, {"type":"challenge_response", "to": frm, "accept": False})
        elif t == "challenge_start":
            opp = msg.get("opponent")
            self.opponent_var.set(opp)
            self.status_var.set(f"Match started with {opp}")
            self.log(f"Match started with {opp}")
        elif t == "challenge_declined":
            frm = msg.get("from")
            messagebox.showinfo("Declined", f"{frm} declined your challenge.")
            self.log(f"{frm} declined your challenge.")
            self.status_var.set("Connected")
        elif t == "round_result":
            self.log("ROUND: " + msg.get("message", ""))
        elif t == "match_result":
            res = msg.get("message", "")
            self.log("MATCH: " + res)
            # save history
            result_text = msg.get("result_text", res)
            self.save_history(result_text)
            # After match, clear opponent
            self.opponent_var.set("")
            self.status_var.set("Connected")
            messagebox.showinfo("Match finished", res)
        elif t == "system":
            self.log("SYSTEM: " + msg.get("message", ""))
        elif t == "error":
            self.log("ERROR: " + msg.get("message", ""))
            messagebox.showwarning("Error", msg.get("message", ""))
        else:
            self.log(f"MSG: {msg}")

    def select_opponent(self):
        sel = self.players_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Choose a player from list.")
            return
        opp = self.players_listbox.get(sel[0])
        self.opponent_var.set(opp)

    def send_challenge(self):
        opp = self.opponent_var.get().strip()
        if not opp:
            messagebox.showwarning("No opponent", "Select an opponent first.")
            return
        safe_send(self.sock, {"type":"challenge", "to": opp})
        self.status_var.set(f"Challenged {opp}")
        self.log(f"Challenged {opp}")

    def send_move(self, move):
        opp = self.opponent_var.get().strip()
        if not opp:
            messagebox.showwarning("No opponent", "Select/accept an opponent first.")
            return
        safe_send(self.sock, {"type":"move", "to": opp, "move": move})
        self.log(f"You -> {move}")

    def save_history(self, result_text):
        name = self.name_var.get().strip()
        if not name: return
        fn = f"history_{name}.txt"
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(fn, "a") as f:
            f.write(f"[{now}] {result_text}\n")
        self.log(f"Saved history to {fn}")

    def show_history(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("No name", "Set your name first.")
            return
        fn = f"history_{name}.txt"
        try:
            with open(fn) as f:
                txt = f.read()
        except FileNotFoundError:
            txt = "No history yet."
        messagebox.showinfo("History", txt)

    def quit_app(self):
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GameClient(root)
    root.mainloop()

from datetime import datetime

def save_history(player_name, opponent, result, score):
    """
    Ghi lịch sử đấu ra file riêng cho từng người chơi.
    Format: [YYYY-MM-DD HH:MM] vs <opponent> — <result> (<score>)
    """
    filename = f"history_{player_name}.txt"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{now}] vs {opponent} — {result} ({score})\n"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(line)

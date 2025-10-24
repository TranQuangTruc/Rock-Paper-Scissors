"""
Phần 2: rps_server_part2_match_logic.py
Chức năng: Kế thừa từ phần 1, thêm logic ghép cặp, xử lý chơi game (thách đấu, chấp nhận, ra chiêu, thoát trận), tính kết quả best-of-3, và lưu lịch sử trận đấu.
"""

from rps_server_part1_core import ServerCore, send_json, clients, clients_lock, gui_queue, server_log
import threading
import time
import os
from datetime import datetime

# Danh sách trận đấu đang diễn ra
matches_lock = threading.Lock()
matches = {}  # match_id -> thông tin trận

HISTORY_DIR = 'history'
os.makedirs(HISTORY_DIR, exist_ok=True)

# --- HÀM XỬ LÝ KẾT QUẢ MỖI ROUND ---
def decide_round(move1, move2):
    order = { 'rock': 0, 'paper': 1, 'scissors': 2 }
    if move1 == move2:
        return 'draw'
    a = order.get(move1)
    b = order.get(move2)
    if a is None or b is None:
        return 'draw'
    if (a - b) % 3 == 1:
        return 'p1'
    else:
        return 'p2'

# --- GHI LỊCH SỬ TRẬN ---
def append_history(player, opponent, result, score_str):
    fname = os.path.join(HISTORY_DIR, f'history_{player}.txt')
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'[{timestamp}] vs {opponent} — {result} ({score_str})\n'
    try:
        with open(fname, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception as e:
        server_log(f'Lỗi ghi lịch sử cho {player}: {e}')

# --- TẠO MÃ TRẬN ---
def mk_match_id(p1, p2):
    return f'{p1}__vs__{p2}__{int(time.time())}'

# --- LỚP MATCH SERVER ---
class MatchServer(ServerCore):
    def __init__(self, host='0.0.0.0', port=9999):
        super().__init__(host, port)

    def process_message(self, msg, conn, addr):
        action = msg.get('action')
        try:
            # --- GỬI LỜI THÁCH ĐẤU ---
            if action == 'challenge':
                fr = msg.get('from')
                to = msg.get('to')
                with clients_lock:
                    if to not in clients:
                        send_json(conn, {'type': 'error', 'note': 'opponent_not_found'})
                        return
                    send_json(clients[to]['conn'], {'type': 'challenge', 'from': fr})
                server_log(f'{fr} đã thách đấu {to}')
                return

            # --- NGƯỜI CHƠI NHẬN LỜI THÁCH ĐẤU ---
            if action == 'accept':
                fr = msg.get('from')
                to = msg.get('to')
                with clients_lock:
                    if fr not in clients or to not in clients:
                        send_json(conn, {'type': 'error', 'note': 'one_player_offline'})
                        return
                mid = mk_match_id(to, fr)
                match = {
                    'p1': to,
                    'p2': fr,
                    'scores': {to: 0, fr: 0},
                    'round': 1,
                    'moves': {},
                    'finished': False
                }
                with matches_lock:
                    matches[mid] = match
                with clients_lock:
                    send_json(clients[to]['conn'], {'type': 'match_start', 'opponent': fr, 'match_id': mid})
                    send_json(clients[fr]['conn'], {'type': 'match_start', 'opponent': to, 'match_id': mid})
                server_log(f'Trận {mid} bắt đầu giữa {to} và {fr}')
                gui_queue.put(('matches', [(mid, match['p1'], match['p2'], f'R1 0-0')]))
                return

            # --- NGƯỜI CHƠI RA CHIÊU ---
            if action == 'move':
                player = msg.get('player')
                mv = msg.get('move')
                match_id = msg.get('match_id')
                if not match_id:
                    send_json(conn, {'type': 'error', 'note': 'missing match_id'})
                    return
                with matches_lock:
                    if match_id not in matches:
                        send_json(conn, {'type': 'error', 'note': 'match_not_found'})
                        return
                    m = matches[match_id]
                    if m.get('finished'):
                        send_json(conn, {'type': 'error', 'note': 'match_finished'})
                        return
                    m['moves'][player] = mv
                    server_log(f'{player} ra chiêu {mv} (round {m["round"]})')
                    p1 = m['p1']
                    p2 = m['p2']
                    # Nếu cả 2 đã ra chiêu -> tính kết quả
                    if p1 in m['moves'] and p2 in m['moves']:
                        res = decide_round(m['moves'][p1], m['moves'][p2])
                        if res == 'draw':
                            with clients_lock:
                                for p in (p1, p2):
                                    if p in clients:
                                        send_json(clients[p]['conn'], {'type': 'round_result', 'you': 'draw', 'score': f"{m['scores'][p1]}-{m['scores'][p2]}", 'match_id': match_id})
                            server_log(f'Trận {match_id}: hòa round {m["round"]}')
                        else:
                            winner = p1 if res == 'p1' else p2
                            loser = p2 if winner == p1 else p1
                            m['scores'][winner] += 1
                            with clients_lock:
                                if winner in clients:
                                    send_json(clients[winner]['conn'], {'type': 'round_result', 'you': 'win', 'score': f"{m['scores'][p1]}-{m['scores'][p2]}", 'match_id': match_id})
                                if loser in clients:
                                    send_json(clients[loser]['conn'], {'type': 'round_result', 'you': 'lose', 'score': f"{m['scores'][p1]}-{m['scores'][p2]}", 'match_id': match_id})
                            server_log(f'Trận {match_id}: người thắng round này là {winner}')

                        m['moves'] = {}
                        m['round'] += 1

                        # Kiểm tra thắng chung cuộc
                        for pl in (p1, p2):
                            if m['scores'][pl] >= 2:
                                m['finished'] = True
                                winner = pl
                                loser = p1 if pl == p2 else p2
                                with clients_lock:
                                    if winner in clients:
                                        send_json(clients[winner]['conn'], {'type': 'match_end', 'result': 'win', 'score': f"{m['scores'][p1]}-{m['scores'][p2]}", 'match_id': match_id})
                                    if loser in clients:
                                        send_json(clients[loser]['conn'], {'type': 'match_end', 'result': 'lose', 'score': f"{m['scores'][p1]}-{m['scores'][p2]}", 'match_id': match_id})
                                server_log(f'Trận {match_id} kết thúc. Người thắng: {winner}')
                                append_history(winner, loser, 'Win', f"{m['scores'][winner]}-{m['scores'][loser]}")
                                append_history(loser, winner, 'Lose', f"{m['scores'][loser]}-{m['scores'][winner]}")
                                gui_queue.put(('matches', [(match_id, p1, p2, 'Finished')]))
                                break
                        else:
                            gui_queue.put(('matches', [(match_id, p1, p2, f'R{m["round"]} {m["scores"][p1]}-{m["scores"][p2]}')]))
                return

            # --- NGƯỜI CHƠI THOÁT GIỮA CHỪNG ---
            if action == 'quit':
                player = msg.get('player')
                with matches_lock:
                    for mid, m in list(matches.items()):
                        if m.get('finished'):
                            continue
                        if player == m['p1'] or player == m['p2']:
                            other = m['p2'] if player == m['p1'] else m['p1']
                            m['finished'] = True
                            with clients_lock:
                                if other in clients:
                                    send_json(clients[other]['conn'], {'type': 'match_end', 'result': 'win', 'reason': 'opponent_left', 'match_id': mid})
                            server_log(f'{player} thoát -> {other} thắng tự động')
                            append_history(other, player, 'Win (opponent left)', f"{m['scores'][other]}-{m['scores'][player]}")
                            append_history(player, other, 'Lose (left)', f"{m['scores'][player]}-{m['scores'][other]}")
                            gui_queue.put(('matches', [(mid, m['p1'], m['p2'], 'Finished')]))
                with clients_lock:
                    if player in clients:
                        try:
                            clients[player]['conn'].close()
                        except:
                            pass
                        del clients[player]
                        gui_queue.put(('players', list(clients.keys())))
                        server_log(f'{player} đã bị xóa (thoát trận)')
                return

        except Exception as e:
            server_log(f'Lỗi trong MatchServer.process_message: {e}')
            try:
                send_json(conn, {'type': 'error', 'note': 'server_error'})
            except:
                pass

if __name__ == '__main__':
    ms = MatchServer()
    ms.start()
    print('MatchServer đang chạy. Nhấn Ctrl+C để dừng.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        ms.stop()

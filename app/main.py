from. import recognition
from. import utils
from. import engine
from. import analysis as analysis_utils
from. import pieces as piece_utils
import config
import os

last_position = None
last_board_array = None
last_score_cp = None
last_score_delta_text = ""
last_client_info = None

def main(img_path, param):  
    # 棋局图像  
    # img_path = './cache/upload.png'
    print(color_status_text(f"本次图片: {os.path.basename(img_path)}"))

    # 预处理 : 把共同的图像处理操作抽出来,当前只有灰度化是共用的
    image, gray = recognition.pre_processing_image(img_path)

    x_array, y_array, pieces = recognize_board_and_pieces(image, gray, param)

    # 棋子位置
    position, is_red = recognition.calculate_pieces_position(x_array, y_array, pieces) # 按原始位置排列的二维数组

    # 检查局面是否变化
    global last_position, last_board_array, last_client_info
    if param['autoModel'] == 'On':
        if utils.check_repeat_position(position, last_position, is_red):
            return 'repeat'
    last_position = position

    # 转成 FEN字符串
    fen_str, board_array = utils.switch_to_fen(position, is_red)
    previous_board_array = last_board_array
    is_same_board = previous_board_array == board_array
    print(color_status_text(format_board_status(recognition.board_cache_debug(), previous_board_array, board_array, bool(last_client_info))))
    last_board_array = copy_board(board_array)

    if is_same_board and last_client_info:
        return last_client_info

    print(format_board_debug(position, is_red))
    board_error = piece_utils.validate_board_array(board_array)
    if board_error:
        print(color_text(f"识别异常: {board_error}", "33"))
        return f"分析失败: {board_error}"

    # 向引擎发送命令
    move, fen, analysis = engine.get_best_move(fen_str, is_red, param)
    if len(move) != 4 or not move[0].isalpha() or not move[1].isdigit() or not move[2].isalpha() or not move[3].isdigit():
        return f"分析失败: 引擎未返回有效走法\n{move}"

    # 发送通知
    second_line = format_analysis(analysis)
    branch_lines = build_branch_lines(move, analysis, board_array, is_red, param)
    score_delta_text = format_score_delta(analysis, is_red, previous_board_array, board_array)
    print(color_status_text(format_engine_debug(analysis)))
    if second_line:
        print(color_score_text(format_score_with_delta(second_line, score_delta_text)))
    info = format_client_branch_info(branch_lines, format_client_score(analysis, is_red), score_delta_text)
    last_client_info = info
    print(format_branch_debug(branch_lines))
    # routes.bark_notification(info)
    return info

def format_analysis(analysis):
    if not analysis:
        return ""

    if "mate_text" in analysis:
        score_text = analysis["mate_text"]
    else:
        score_text = analysis.get("score_text", "")

    return score_text

def format_moves(best_move, analysis, board_array, is_red):
    moves = analysis.get("moves", []) if analysis else []
    if best_move not in moves:
        moves.insert(0, best_move)

    chinese_moves = []
    for move in moves[:2]:
        chinese_moves.append(utils.convert_move_to_chinese(move, board_array, is_red))
    return " ".join(chinese_moves)

def format_score_delta(analysis, is_red, previous_board, current_board):
    global last_score_cp, last_score_delta_text
    current_score_cp = player_perspective_score_cp(analysis, is_red)
    if current_score_cp is None:
        return ""

    previous_score_cp = last_score_cp
    if previous_score_cp is None:
        last_score_cp = current_score_cp
        last_score_delta_text = ""
        return ""

    if is_suspicious_board_change(previous_board, current_board):
        last_score_cp = current_score_cp
        last_score_delta_text = ""
        return ""

    # 同一盘面重复分析时沿用上一次真实局面变化算出的分差。
    if previous_board == current_board:
        return last_score_delta_text

    delta = current_score_cp - previous_score_cp
    last_score_cp = current_score_cp
    last_score_delta_text = f"{delta:+d}"
    return last_score_delta_text

def format_score_with_delta(score_text, score_delta_text):
    if not score_delta_text:
        return score_text
    return f"{score_text}{format_delta_badge(score_delta_text)}"

def player_perspective_score_cp(analysis, is_red):
    if not analysis or "score_cp" not in analysis:
        return None

    score_cp = analysis["score_cp"]
    # Pikafish 分数对当前行棋方为正；这里转成“我方视角”。
    return score_cp

def format_client_score(analysis, is_red):
    if not analysis:
        return ""
    if "mate_text" in analysis:
        return format_client_mate(analysis["mate"], is_red)
    if "score_cp" not in analysis:
        return ""

    score_cp = analysis["score_cp"]
    if score_cp == 0:
        return "💛均势"

    lead_is_red = score_cp > 0 if is_red else score_cp < 0
    return f"{score_side_emoji(lead_is_red)}{abs(score_cp)}分"

def format_client_mate(mate, is_red):
    lead_is_red = mate > 0 if is_red else mate < 0
    return f"{score_side_emoji(lead_is_red)}{abs(mate)}步杀"

def format_engine_debug(analysis):
    return (
        f"引擎: {analysis_utils.format_search_fields_cn(analysis)} "
        f"(配置:线程={config.ENGINE_THREADS} 哈希={config.ENGINE_HASH_MB}MB 候选={config.ENGINE_MULTI_PV})"
    )

def color_score_text(text):
    if text.startswith("红方"):
        return color_text(text, "31")
    if text.startswith("黑方"):
        return color_text(text, "34")
    return text

def color_status_text(text):
    return color_text(text, "32")

def format_position_change_debug(previous_board, current_board):
    if previous_board is None:
        return ""

    stats = board_change_stats(previous_board, current_board)
    alerts = []
    if is_suspicious_piece_increase(stats):
        alerts.append(f"新增棋子 {stats['added']} 个")
    if is_suspicious_change_ratio(stats):
        alerts.append(f"位置变化 {stats['change_ratio']:.1%}")

    if alerts:
        return (
            "盘面变化: 疑似新局或识别大幅跳变 | "
            f"变化格={stats['changed_squares']}/90 "
            f"变化率={stats['change_ratio']:.1%} "
            f"新增={stats['added']} 减少={stats['removed']} | "
            + "，".join(alerts)
        )

    return (
        "盘面变化: 正常 | "
        f"变化格={stats['changed_squares']}/90 "
        f"变化率={stats['change_ratio']:.1%} "
        f"新增={stats['added']} 减少={stats['removed']}"
    )

def format_board_status(board_cache_text, previous_board, current_board, can_reuse):
    if previous_board is None:
        return board_cache_text

    if previous_board == current_board:
        change_text = "盘面变化: 未变化"
        if can_reuse:
            change_text += " 复用上次结果"
        return f"{board_cache_text} {change_text}"

    return f"{board_cache_text} {format_position_change_debug(previous_board, current_board)}"

def board_change_stats(previous_board, current_board):
    changed_squares = 0
    previous_piece_count = 0
    current_piece_count = 0
    for previous_row, current_row in zip(previous_board, current_board):
        for previous_piece, current_piece in zip(previous_row, current_row):
            if previous_piece != "-":
                previous_piece_count += 1
            if current_piece != "-":
                current_piece_count += 1
            if previous_piece != current_piece:
                changed_squares += 1

    piece_delta = current_piece_count - previous_piece_count

    return {
        "changed_squares": changed_squares,
        "change_ratio": changed_squares / 90,
        "added": max(0, piece_delta),
        "removed": max(0, -piece_delta),
    }

def is_suspicious_board_change(previous_board, current_board):
    if previous_board is None:
        return False

    stats = board_change_stats(previous_board, current_board)
    return is_suspicious_piece_increase(stats) or is_suspicious_change_ratio(stats)

def is_suspicious_piece_increase(stats):
    return stats["added"] >= 3

def is_suspicious_change_ratio(stats):
    return stats["change_ratio"] > 0.30

def build_branch_lines(best_move, analysis, board_array, is_red, param):
    pvs = analysis.get("pvs", []) if analysis else []
    if pvs:
        return build_branch_lines_from_pvs(
            pvs[:2],
            board_array,
            is_red,
            analysis.get("candidate_scores", []) if analysis else [],
        )

    candidates = candidate_moves(best_move, analysis)
    lines = []
    line_number = 1
    for candidate_index, move in enumerate(candidates[:2], start=1):
        candidate_board = copy_board(board_array)
        move_text = display_move_text(move, candidate_board, is_red)
        lines.append(
            branch_line(
                line_number,
                move_text,
                is_red,
                repeated_move_placeholder(),
                not is_red,
                repeated_move_placeholder(),
                is_red,
                "",
            )
        )
        line_number += 1
    return lines

def build_branch_lines_from_pvs(pvs, board_array, is_red, candidate_scores):
    lines = []
    followup_budget = {"remaining": config.MAX_SHORT_FOLLOWUPS}
    for index, pv_moves in enumerate(pvs, start=1):
        pv_board = copy_board(board_array)
        move_text = pv_move_text(pv_moves, 0, pv_board, is_red)
        reply_text = pv_or_short_followup_text(pv_moves, 1, pv_board, not is_red, followup_budget)
        response_text = repeated_move_placeholder()
        if reply_text != repeated_move_placeholder():
            response_text = pv_or_short_followup_text(pv_moves, 2, pv_board, is_red, followup_budget)
        score_text = compact_candidate_score(candidate_scores[index - 1] if index - 1 < len(candidate_scores) else {}, is_red)
        lines.append(branch_line(index, move_text, is_red, reply_text, not is_red, response_text, is_red, score_text))
    return lines

def pv_or_short_followup_text(pv_moves, index, board_array, is_red, followup_budget):
    if index < len(pv_moves):
        return pv_move_text(pv_moves, index, board_array, is_red)

    if followup_budget["remaining"] <= 0:
        return repeated_move_placeholder()

    followup_budget["remaining"] -= 1
    followup = short_followup_move(board_array, is_red)
    if not followup:
        return repeated_move_placeholder()

    move_text = display_move_text(followup, board_array, is_red)
    apply_move(board_array, followup)
    return move_text

def short_followup_move(board_array, is_red):
    fen = board_to_fen(board_array)
    short_param = {
        "goParam": "movetime",
        "movetime": config.SHORT_FOLLOWUP_MOVETIME,
    }
    move, _, _ = engine.get_best_move(fen, is_red, short_param)
    if analysis_utils.is_valid_bestmove(move):
        return move
    return None

def pv_move_text(pv_moves, index, board_array, is_red):
    if index >= len(pv_moves):
        return repeated_move_placeholder()

    move = pv_moves[index]
    move_text = display_move_text(move, board_array, is_red)
    apply_move(board_array, move)
    return move_text

def branch_line(index, move_text, move_is_red, reply_text, reply_is_red, response_text, response_is_red, score_text=""):
    return {
        "index": index,
        "move_text": move_text,
        "move_is_red": move_is_red,
        "reply_text": reply_text,
        "reply_is_red": reply_is_red,
        "response_text": response_text,
        "response_is_red": response_is_red,
        "score_text": score_text,
    }

def format_branch_debug(branch_lines):
    if not branch_lines:
        return "无候选分支"

    return "\n".join(format_branch_line(line) for line in branch_lines)

def format_client_branch_info(branch_lines, score_text, score_delta_text=""):
    if not branch_lines:
        return score_text or "无候选分支"

    main_lines = client_main_branch_lines(branch_lines)
    items = [format_client_branch_item(line, index) for index, line in enumerate(main_lines[:2], start=1)]
    first_line = items[0] if items else ""
    second_line = items[1] if len(items) > 1 else ""
    has_candidate_score = any(line.get("score_text") for line in main_lines[:2])
    if score_text and not has_candidate_score:
        first_line = f"{first_line} {score_text}" if first_line else score_text
    if score_delta_text:
        first_line = f"{first_line}{format_delta_badge(score_delta_text)}" if first_line else format_delta_badge(score_delta_text)
    return f"{first_line}\n{second_line}" if second_line else first_line

def client_main_branch_lines(branch_lines):
    return [line for line in branch_lines[:4] if line["move_text"] != repeated_move_placeholder(line["move_text"])]

def format_client_branch_item(line, index=None):
    label_index = index if index is not None else line["index"]
    score_text = f" {line['score_text']}" if line.get("score_text") else ""
    return (
        f"{branch_number_label(label_index)}"
        f"{line['move_text']}"
        f"{side_emoji(line['reply_is_red'])}{line['reply_text']}"
        f"{side_emoji(line['response_is_red'])}{line['response_text']}"
        f"{score_text}"
    )

def compact_candidate_score(score, is_red):
    if not score:
        return ""
    if "mate_text" in score:
        return format_client_mate(score["mate"], is_red)
    if "score_cp" not in score:
        return ""

    score_cp = score["score_cp"]
    if score_cp == 0:
        return "💛均势"

    lead_is_red = score_cp > 0 if is_red else score_cp < 0
    return f"{score_side_emoji(lead_is_red)}{abs(score_cp)}分"

def format_delta_badge(score_delta_text):
    if not score_delta_text:
        return ""
    return f"({score_delta_text})"

def side_emoji(is_red):
    return "🔴" if is_red else "🔵"

def score_side_emoji(is_red):
    return "❤️" if is_red else "💙"

def format_branch_line(line):
    score_text = f" {line['score_text']}" if line.get("score_text") else ""
    return (
        f"{branch_number_label(line['index'])} "
        f"{pad_colored_move(line['move_text'], line['move_is_red'])} "
        f"{pad_colored_move(line['reply_text'], line['reply_is_red'])} "
        f"{pad_colored_move(line['response_text'], line['response_is_red'])}"
        f"{score_text}"
    )

def branch_number_label(index):
    labels = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    if 1 <= index <= len(labels):
        return labels[index - 1]
    return f"{index}."

def pad_colored_move(move_text, is_red):
    padded = pad_display_text(move_text, 8)
    return color_move_text(padded, is_red)

def pad_display_text(text, target_width):
    text = str(text)
    width = visible_width(text)
    return text + " " * max(0, target_width - width)

def repeated_move_placeholder(move_text=None):
    return "－－－－"

def candidate_moves(best_move, analysis):
    moves = list(analysis.get("moves", []) if analysis else [])
    if best_move and best_move not in moves:
        moves.insert(0, best_move)
    return moves

def analyze_reply_moves(board_array, side, param):
    fen = board_to_fen(board_array)
    _, _, reply_analysis = engine.get_best_move(fen, side, param)
    return reply_analysis.get("moves", []) if reply_analysis else []

def format_move_for_board(move, board_array, is_red):
    if not analysis_utils.is_valid_bestmove(move):
        return move or repeated_move_placeholder()
    try:
        return utils.convert_move_to_chinese(move, board_array, is_red)
    except (KeyError, IndexError, ValueError):
        return move

def display_move_text(move, board_array, is_red):
    move_text = format_move_for_board(move, board_array, is_red)
    if not is_red:
        return to_fullwidth_digits(move_text)
    return move_text

def to_fullwidth_digits(text):
    return str(text).translate(str.maketrans("0123456789", "０１２３４５６７８９"))

def apply_move(board_array, move):
    if not analysis_utils.is_valid_bestmove(move):
        return

    start_col, start_row = move_to_index(move[0], move[1])
    end_col, end_row = move_to_index(move[2], move[3])
    piece = board_array[start_row][start_col]
    board_array[start_row][start_col] = "-"
    board_array[end_row][end_col] = piece

def move_to_index(col_char, row_char):
    col = ord(col_char) - ord("a")
    row = 9 - int(row_char)
    return col, row

def copy_board(board_array):
    return [row[:] for row in board_array]

def side_name(is_red):
    return "红" if is_red else "黑"

def colored_side_name(is_red):
    return color_text(side_name(is_red), "31" if is_red else "34")

def color_move_text(move_text, is_red):
    return color_text(move_text, "31" if is_red else "34")

def board_to_fen(board_array):
    rows = []
    for row in board_array:
        empty_count = 0
        row_text = []
        for cell in row:
            if cell == "-":
                empty_count += 1
                continue
            if empty_count:
                row_text.append(str(empty_count))
                empty_count = 0
            row_text.append(cell)
        if empty_count:
            row_text.append(str(empty_count))
        rows.append("".join(row_text))
    return "/".join(rows)

def format_board_debug(board_array, is_red):
    lines = [format_scale_row(top_scale(is_red), not is_red)]
    for index, row in enumerate(board_array):
        if index == 5:
            lines.append(" ========= 楚河      汉界 =========")
        lines.append(format_piece_row(row))
    lines.append(format_scale_row(bottom_scale(is_red), is_red))
    return "\n".join(lines)

def piece_label(piece):
    return piece_utils.piece_label(piece)

def bottom_scale(is_red):
    if is_red:
        return ["九", "八", "七", "六", "五", "四", "三", "二", "一"]
    return ["９", "８", "７", "６", "５", "４", "３", "２", "１"]

def top_scale(is_red):
    if is_red:
        return ["１", "２", "３", "４", "５", "６", "７", "８", "９"]
    return ["一", "二", "三", "四", "五", "六", "七", "八", "九"]

def format_scale_row(cells, is_red_side):
    return "".join(format_colored_cell(cell, scale_color(is_red_side)) for cell in cells)

def format_piece_row(pieces):
    return "".join(format_piece_cell(piece) for piece in pieces)

def format_piece_cell(piece):
    cell = format_plain_cell(piece_label(piece))
    if piece.isupper():
        return color_cell(cell, "31")
    if piece.islower():
        return color_cell(cell, "34")
    return cell

def format_colored_cell(label, color):
    return color_cell(format_plain_cell(label), color)

def format_plain_cell(label):
    return f" {label} "

def color_cell(cell, color):
    return f"\033[{color}m{cell}\033[0m"

def scale_color(is_red_side):
    return "31;2" if is_red_side else "34;2"

def color_text(text, color):
    return f"\033[{color}m{text}\033[0m"

def visible_width(text):
    width = 0
    in_escape = False
    for char in text:
        if char == "\033":
            in_escape = True
            continue
        if in_escape:
            if char == "m":
                in_escape = False
            continue
        width += 2 if ord(char) > 127 else 1
    return width

def recognize_board_and_pieces(image, gray, param):
    x_array, y_array = recognition.cached_board_recognition(image, gray)
    pieces = recognition.pieces_recognition(image, gray, param, x_array, y_array)
    return x_array, y_array, pieces


    
  

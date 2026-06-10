from. import recognition
from. import utils
from. import engine
from. import analysis as analysis_utils
import config

last_position = None
last_board_array = None

def main(img_path, param):  
    # 棋局图像  
    # img_path = './cache/upload.png'

    # 预处理 : 把共同的图像处理操作抽出来,当前只有灰度化是共用的
    image, gray = recognition.pre_processing_image(img_path)

    x_array, y_array, pieces = recognize_board_and_pieces(image, gray, param)
    print(color_status_text(recognition.board_cache_debug()))

    # 棋子位置
    position, is_red = recognition.calculate_pieces_position(x_array, y_array, pieces) # 按原始位置排列的二维数组

    # 检查局面是否变化
    global last_position, last_board_array
    if param['autoModel'] == 'On':
        if utils.check_repeat_position(position, last_position, is_red):
            return 'repeat'
    last_position = position

    # 转成 FEN字符串
    fen_str, board_array = utils.switch_to_fen(position, is_red)
    position_change_debug = format_position_change_debug(last_board_array, board_array)
    if position_change_debug:
        print(color_status_text(position_change_debug))
    last_board_array = copy_board(board_array)
    print(format_board_debug(position, is_red))

    # 向引擎发送命令
    move, fen, analysis = engine.get_best_move(fen_str, is_red, param)
    if len(move) != 4 or not move[0].isalpha() or not move[1].isdigit() or not move[2].isalpha() or not move[3].isdigit():
        return f"分析失败: 引擎未返回有效走法\n{move}"

    # 发送通知
    second_line = format_analysis(analysis)
    move_line = format_moves(move, analysis, board_array, is_red)
    print(color_status_text(format_engine_debug(analysis)))
    if second_line:
        print(color_score_text(second_line))
    info = f"{second_line}\n{move_line}" if second_line else move_line
    print(format_branch_debug(move, analysis, board_array, is_red, param))
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
    if stats["added"] >= 3:
        alerts.append(f"新增棋子 {stats['added']} 个")
    if stats["change_ratio"] > 0.30:
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

def format_branch_debug(best_move, analysis, board_array, is_red, param):
    candidates = candidate_moves(best_move, analysis)
    lines = []
    line_number = 1
    for candidate_index, move in enumerate(candidates[:2], start=1):
        candidate_board = copy_board(board_array)
        move_text = display_move_text(move, candidate_board, is_red)
        apply_move(candidate_board, move)

        replies = analyze_reply_moves(candidate_board, not is_red, param)
        if not replies:
            lines.append(format_branch_line(line_number, move_text, is_red, "无", not is_red, "无", is_red))
            line_number += 1
            continue

        for reply_index, reply in enumerate(replies[:2], start=1):
            reply_text = display_move_text(reply, candidate_board, not is_red)

            response_board = copy_board(candidate_board)
            apply_move(response_board, reply)
            responses = analyze_reply_moves(response_board, is_red, param)
            response_text = display_move_text(responses[0], response_board, is_red) if responses else "无"
            shown_move = move_text if reply_index == 1 else repeated_move_placeholder(move_text)
            lines.append(
                format_branch_line(line_number, shown_move, is_red, reply_text, not is_red, response_text, is_red)
            )
            line_number += 1
    return "\n".join(lines) if lines else "无候选分支"

def format_branch_line(index, move_text, move_is_red, reply_text, reply_is_red, response_text, response_is_red):
    return (
        f"{branch_number_label(index)} "
        f"{pad_colored_move(move_text, move_is_red)} "
        f"{pad_colored_move(reply_text, reply_is_red)} "
        f"{pad_colored_move(response_text, response_is_red)}"
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

def repeated_move_placeholder(move_text):
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
        return move or "无"
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
    names = {
        "r": "车", "n": "马", "b": "象", "a": "士", "k": "将", "c": "炮", "p": "卒",
        "R": "车", "N": "马", "B": "相", "A": "仕", "K": "帅", "C": "炮", "P": "兵",
        "-": "－",
    }
    return names.get(piece, piece)

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


    
  

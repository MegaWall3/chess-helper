PIECE_META = {
    "k": {"label": "將", "side": "黑", "limit": 1, "exact": True},
    "a": {"label": "士", "side": "黑", "limit": 2, "exact": False},
    "b": {"label": "象", "side": "黑", "limit": 2, "exact": False},
    "r": {"label": "車", "side": "黑", "limit": 2, "exact": False},
    "n": {"label": "馬", "side": "黑", "limit": 2, "exact": False},
    "c": {"label": "砲", "side": "黑", "limit": 2, "exact": False},
    "p": {"label": "卒", "side": "黑", "limit": 5, "exact": False},
    "K": {"label": "帥", "side": "红", "limit": 1, "exact": True},
    "A": {"label": "仕", "side": "红", "limit": 2, "exact": False},
    "B": {"label": "相", "side": "红", "limit": 2, "exact": False},
    "R": {"label": "俥", "side": "红", "limit": 2, "exact": False},
    "N": {"label": "傌", "side": "红", "limit": 2, "exact": False},
    "C": {"label": "炮", "side": "红", "limit": 2, "exact": False},
    "P": {"label": "兵", "side": "红", "limit": 5, "exact": False},
}

def validate_board_array(board_array):
    counts = count_board_pieces(board_array)
    errors = []
    for piece, meta in PIECE_META.items():
        count = counts.get(piece, 0)
        limit = meta["limit"]
        if count > limit or (meta["exact"] and count != limit):
            errors.append(f"{validation_piece_label(piece)}={count}/{limit}")
    errors.extend(validate_palace_positions(board_array))
    if errors:
        return "棋盘识别异常: " + " ".join(errors)
    return ""

def count_board_pieces(board_array):
    counts = {}
    for row in board_array:
        for piece in row:
            if piece == "-":
                continue
            counts[piece] = counts.get(piece, 0) + 1
    return counts

def piece_label(piece):
    if piece == "-":
        return "－"
    return PIECE_META.get(piece, {}).get("label", piece)

def validation_piece_label(piece):
    meta = PIECE_META.get(piece)
    if not meta:
        return piece
    return f"{meta['side']}{meta['label']}"

def validate_palace_positions(board_array):
    errors = []
    for row_index, row in enumerate(board_array):
        for col_index, piece in enumerate(row):
            if piece == "k" and not in_black_palace(row_index, col_index):
                errors.append(f"{validation_piece_label(piece)}位置={row_index + 1}行{col_index + 1}列")
            if piece == "K" and not in_red_palace(row_index, col_index):
                errors.append(f"{validation_piece_label(piece)}位置={row_index + 1}行{col_index + 1}列")
    return errors

def in_black_palace(row_index, col_index):
    return 0 <= row_index <= 2 and 3 <= col_index <= 5

def in_red_palace(row_index, col_index):
    return 7 <= row_index <= 9 and 3 <= col_index <= 5

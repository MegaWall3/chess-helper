from. import recognition
from. import utils
from. import engine

last_position = None

def main(img_path, param):  
    # 棋局图像  
    # img_path = './cache/upload.png'

    # 预处理 : 把共同的图像处理操作抽出来,当前只有灰度化是共用的
    image, gray = recognition.pre_processing_image(img_path)

    # 识别棋盘
    x_array, y_array = recognition.board_recognition(image, gray)

    # 识别棋子 
    pieces = recognition.pieces_recognition(image, gray, param, x_array, y_array)

    # 棋子位置
    position, is_red = recognition.calculate_pieces_position(x_array, y_array, pieces) # 按原始位置排列的二维数组

    # 检查局面是否变化
    global last_position
    if param['autoModel'] == 'On':
        if utils.check_repeat_position(position, last_position, is_red):
            return 'repeat'
    last_position = position

    # 转成 FEN字符串
    fen_str, board_array = utils.switch_to_fen(position, is_red)
    for i, row in enumerate(board_array):  
        print(row)

    # 向引擎发送命令
    move, fen, analysis = engine.get_best_move(fen_str, is_red, param)
    print(f'{fen}\n{move}')
    if len(move) != 4 or not move[0].isalpha() or not move[1].isdigit() or not move[2].isalpha() or not move[3].isdigit():
        return f"分析失败: 引擎未返回有效走法\n{move}"

    # 发送通知
    info = format_moves(move, analysis, board_array, is_red)
    second_line = format_analysis(analysis)
    if second_line:
        info = f"{second_line}\n{info}"
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

    labels = ["①", "②"]
    chinese_moves = []
    for index, move in enumerate(moves[:2]):
        chinese_moves.append(f"{labels[index]}{utils.convert_move_to_chinese(move, board_array, is_red)}")
    return " ".join(chinese_moves)


    
  

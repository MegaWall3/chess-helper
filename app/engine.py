import time
import atexit
import queue
import subprocess
import threading
import config
from. import analysis
from. import pikafish as pikafish_files

pikafish = None
output_queue = None
engine_lock = threading.Lock()


class EngineError(Exception):
    pass

def init_engine():
    global pikafish, output_queue # 全局变量
    if is_engine_alive():
        return

    # 开辟一个子进程, 运行引擎
    output_queue = queue.Queue()
    pikafish_command = pikafish_files.resolve_command()
    pikafish = subprocess.Popen(
        pikafish_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=config.PIKAFISH_HOME,
    )
    # 统一收集引擎输出，避免启动日志混入后续 bestmove 解析。
    threading.Thread(target=read_engine_stdout, args=(pikafish, output_queue), daemon=True).start()

    # 准备
    uci(pikafish) # 可以用全局变量,也可以用传参
    setoption(f'setoption name Threads value {config.ENGINE_THREADS}')
    setoption(f'setoption name Hash value {config.ENGINE_HASH_MB}')
    setoption(f'setoption name MultiPV value {config.ENGINE_MULTI_PV}')
    setoption(f'setoption name EvalFile value {pikafish_files.resolve_nnue_file()}')
    setoption('setoption name UCI_ShowWDL value true')
    isready()

def is_engine_alive():
    return pikafish is not None and pikafish.poll() is None

def restart_engine():
    stop_engine()
    init_engine()

def stop_engine():
    global pikafish, output_queue
    process = pikafish
    pikafish = None
    output_queue = None
    if process is None or process.poll() is not None:
        return

    try:
        process.stdin.write('quit\n')
        process.stdin.flush()
        process.wait(timeout=2)
    except (BrokenPipeError, OSError, ValueError, subprocess.TimeoutExpired):
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

def ensure_engine():
    if not is_engine_alive():
        init_engine()

def get_best_move(fen, side, parameter):
    fen_string = fen + ' ' + ('w' if side else 'b')

    param = parameter['goParam']
    value = parameter[param]
    if param is None or param == '' or value is None or value == '':
        param = config.DEFAULT_GO_PARAM
        value = parameter.get(param, config.DEFAULT_MOVETIME)

    # 单个 UCI 进程共用一条输出流，搜索请求需要串行处理。
    with engine_lock:
        last_error = None
        for attempt in range(2):
            try:
                ensure_engine()
                lines, best_move = go(fen_string, param, str(value))
                engine_analysis = analysis.parse_engine_info(lines, side)
                break
            except (BrokenPipeError, OSError, EngineError, pikafish_files.PikafishFileError) as error:
                last_error = error
                restart_engine()
        else:
            return f"No valid bestmove: {last_error}", fen_string, {}

    if not lines:
        best_move = "No output received within engine timeout"
    elif best_move:
        best_move = best_move.split()[1]
        if not analysis.is_valid_bestmove(best_move):
            best_move = "No valid bestmove"
    else:
        best_move = "No valid bestmove"

    return best_move, fen_string, engine_analysis

def write_command(process, command):
    if process is None or process.poll() is not None:
        raise EngineError("Pikafish process is not running")
    process.stdin.write(f'{command}\n')
    process.stdin.flush()

def read_line(process, timeout):
    if process is None or process.poll() is not None:
        raise EngineError("Pikafish process is not running")
    try:
        return output_queue.get(timeout=timeout)
    except queue.Empty:
        return None

def read_engine_stdout(process, target_queue):
    try:
        for line in process.stdout:
            line = line.strip()
            if line:
                target_queue.put(line)
    except ValueError:
        return

def send_command(cmd, interval, keyword):
    command = cmd
    write_command(pikafish, command)
    lines = []
    start_time = time.time()
    while True:  
        if (time.time() - start_time > interval):  # 如果超过指定时间，则退出循环  
            break
        # 读取一行输出（包括换行符），然后去除换行符  
        output = read_line(pikafish, max(0.0, interval - (time.time() - start_time)))
        if output is None:
            break
        if output:  
            lines.append(output)  # 将非空输出添加到列表中  
            if keyword in output:  # 如果找到 输出关键字，则立即退出循环  
                break  
    return lines

def uci(engine):
    command = 'uci'
    write_command(engine, command)
    lines = []
    start_time = time.time()
    while True:  
        if (time.time() - start_time > 1):  # 如果超过1秒，则退出循环  
            break
        # 读取一行输出（包括换行符），然后去除换行符  
        output = read_line(engine, max(0.0, 1 - (time.time() - start_time)))
        if output is None:
            break
        if output:  
            lines.append(output)  # 将非空输出添加到列表中  
            if 'uciok' in output:  # 如果找到 'uciok'，则立即退出循环  
                break  
    return lines

def isready():
    command = 'isready'
    write_command(pikafish, command)
    output = ''
    start_time = time.time()
    while True:
        if time.time() - start_time > 3:
            break
        line = read_line(pikafish, max(0.0, 3 - (time.time() - start_time)))
        if line is None:
            break
        if line:
            output = line
            if 'readyok' in line:
                break
    return output

def setoption(cmd):
    command = cmd
    write_command(pikafish, command)
    return

def ucinewgame():
    """
    发送ucinewgame之后应该总是发送isready命令,然后等待readyok
    """
    newgame_command = 'ucinewgame\n'
    isready_command = 'isready\n'
    pikafish.stdin.write(newgame_command)
    pikafish.stdin.write(isready_command)
    pikafish.stdin.flush() 
    start_time = time.time()
    while True:  
        if (time.time() - start_time > 3):  # 如果超过3秒，则退出循环 
            break
        output = read_line(pikafish, max(0.0, 3 - (time.time() - start_time)))
        if output is None:
            break
        if output:  
            if 'readyok' in output:  
                break  
    return output

def go(fen_string, param, value):
    start_position1 = 'rnbakabnr/9/1c5c1/p1p1p1p1p'
    start_position2 = 'P1P1P1P1P/1C5C1/9/RNBAKABNR'
    if start_position1 in fen_string or start_position2 in fen_string:
        ucinewgame()
        pos_command1 = "position startpos\n"
        pikafish.stdin.write(pos_command1)

    pos_command2 = "position fen " + fen_string + "\n"  
    go_command = "go " + param + " " + value + "\n" 
    # 发送命令  
    pikafish.stdin.write(pos_command2)  
    pikafish.stdin.write(go_command)  
    pikafish.stdin.flush() 
    # 读取数据
    lines, best_move = read_output_with_timeout(pikafish, search_timeout(param, value))
    if not best_move:
        write_command(pikafish, "stop")
        stop_lines, best_move = read_output_with_timeout(pikafish, 2)
        lines.extend(stop_lines)

    return lines, best_move

def search_timeout(param, value):
    if param == "movetime":
        try:
            return max(3, int(value) / 1000 + 5)
        except ValueError:
            return 8
    return 50

def read_output_with_timeout(process, timeout=1):  
    lines = []
    best_move = ''
    start_time = time.time()  
    
    while True:  
        # 控制读取时间,超时不再读取 
        if time.time() - start_time > timeout:  
            break
        # 读取一行输出（包括换行符），然后去除换行符  
        output = read_line(process, max(0.0, timeout - (time.time() - start_time)))
        if output is None:
            break
        if output: 
            lines.append(output)
            if output.startswith("bestmove "):
                best_move = output  # 获取包含"bestmove"的输出行
                break
    
    # 返回: 所有输出以及包含bestmove的行            
    return lines, best_move 

atexit.register(stop_engine)

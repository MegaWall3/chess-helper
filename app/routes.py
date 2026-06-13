from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime
import config
from. import main

app = Flask(__name__) #创建应用,谁有这句代码 谁就是入口

print(config.BASE_DIR) # 资源路径都以项目根目录为基准

# 上传图片按时间留存最近几张，方便回看识别错位的原图。
app.config['UPLOAD_FOLDER'] = config.CACHE_FOLDER
if not os.path.exists(config.CACHE_FOLDER):
    os.makedirs(config.CACHE_FOLDER)

# @app.route() 可以视为一个装饰器, 装饰后面紧跟着的那个函数
@app.route('/upload', methods=['GET', 'POST'])  
def upload_file():  
    if request.files:
        filepath, param_data = read_multipart_upload()
    else:
        filepath, param_data = read_body_upload()

    if filepath is None:
        return jsonify({"error": 'No upload image'}), 400

    # 保持 JSON 响应，方便移动端或快捷指令读取错误信息。
    try:
        info = main.main(filepath, param_data)
    except Exception as error:
        info = f"分析失败: {error}"
    return jsonify({"message": info})

def read_multipart_upload():
    if 'image' not in request.files or request.files['image'].filename == '':
        return None, {}
    if 'param' not in request.form:
        return None, {}

    try:
        param_data = json.loads(request.form['param'])
    except json.JSONDecodeError:
        return None, {}

    image = request.files['image']
    filepath = upload_cache_path(image.filename)
    image.save(filepath)
    cleanup_upload_history()
    return filepath, param_data

def read_body_upload():
    image_data = request.get_data()
    if not image_data:
        return None, {}

    param_data = {
        "platform": request.args.get("platform", config.DEFAULT_PLATFORM),
        "autoModel": request.args.get("autoModel", config.DEFAULT_AUTO_MODEL),
        "goParam": request.args.get("goParam", config.DEFAULT_GO_PARAM),
        "movetime": request.args.get("movetime", config.DEFAULT_MOVETIME),
        "depth": request.args.get("depth", config.DEFAULT_DEPTH),
    }
    filepath = upload_cache_path('upload.png')
    with open(filepath, 'wb') as file:
        file.write(image_data)
    cleanup_upload_history()
    return filepath, param_data

def upload_cache_path(filename):
    extension = os.path.splitext(filename)[1].lower() or '.png'
    if extension not in ('.png', '.jpg', '.jpeg'):
        extension = '.png'
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]
    return os.path.join(app.config['UPLOAD_FOLDER'], f'upload-{timestamp}{extension}')

def cleanup_upload_history():
    uploads = [
        os.path.join(app.config['UPLOAD_FOLDER'], filename)
        for filename in os.listdir(app.config['UPLOAD_FOLDER'])
        if filename.startswith('upload-') and filename.lower().endswith(('.png', '.jpg', '.jpeg'))
    ]
    uploads.sort(key=os.path.getmtime, reverse=True)
    for filepath in uploads[config.UPLOAD_HISTORY_LIMIT:]:
        try:
            os.remove(filepath)
        except OSError:
            pass

# 使用'bark'通知
@app.route('/bark_notification')
def bark_notification(info):
    response = requests.get(f'https://api.day.app/3oaR7upc6nHQkCPDCAuM3m/{info}') 
    return 'Done'

@app.route('/')
#定义根路径的处理函数; 返回一个字符串，显示主页的欢迎信息
def home():
    return 'Hello, this is the home page!'

# @app.route('/send_engine_uci') #默认是GET方法
# # 向引擎发送 uci 命令,告诉引擎使用uci协议
# def send_engine_uci():
#     output = engine.uci(engine.pikafish)
#     # 返回所有输出（可能有 'uciok', 可能没有, 也可能为空）  
#     return jsonify({"output": output}) if output else jsonify({"error": "No output found"}) 

# @app.route('/send_engine_isready')
# # 向引擎发送 isready 命令
# def send_engine_isready():
#     output = engine.isready()
#     return jsonify({"output": output}) if output else jsonify({"error": "No output in 0.5 second"}) 

@app.route('/send_engine_ucinewgame')
# 向引擎发送 ucinewgame 命令
def send_engine_ucinewgame():
    output = engine.ucinewgame()
    return jsonify({"message": output})

# @app.route('/get_best_move', methods=['POST'])
# def get_best_move():
#     """
#     处理 '/get_best_move' 路径的 POST 请求
#     从请求表单中获取 'fen' 以及其他go的附带参数, 并通过与 pikafish 进程交互获取最佳着法
#     最后返回最佳着法
#     """
#     if 'fen' not in request.form:  
#         return jsonify({"error": "Missing 'fen' in request"}), 400
#     if 'paramName' not in request.form:  
#         return jsonify({"error": "Missing 'paramName' in request"}), 400
#     if 'paramValue' not in request.form:  
#         return jsonify({"error": "Missing 'paramValue' in request"}), 400
    
#     fen_string = request.form['fen']
#     go_param_name = request.form['paramName']
#     go_param_value = request.form['paramValue']
    
#     lines, best_move = engine.go(fen_string, go_param_name, go_param_value)
    
#     # 如果列表为空，表示直到超时也没有输出  
#     if not lines:  
#         return jsonify({"error": "No output received within 40 seconds"}), 408  # 使用408 Request Timeout作为HTTP状态码  
  
#     # 列表不为空, 返回输出（可能有 'bestmove', 可能为空）  
#     return jsonify({"output": best_move}) if best_move else jsonify({"error": "No 'bestmove' found in output"})

# @app.route('/change_parameter', methods=['POST'])
# def change_parameter(): 
#     name        = request.form.get('param_name', 'depth')
#     is_add_str  = request.form.get('is_add', 'false')

#     # 恢复默认
#     if is_add_str == 'default':
#         engine.parameter['current'] = 'depth'
#         engine.parameter['value']['depth'] = '20'
#         engine.parameter['value']['movetime'] = '3000'
#         engine.save_parameters()
#         main.last_position = None #在'恢复默认'功能中附带清除last_position功能,偶尔识别失误一直提示repeat时可以用上
#         return jsonify({"message": engine.parameter})
    
#     # 修改引擎参数
#     is_add = is_add_str.lower() == 'true'
#     current_val = int(engine.parameter['value'][name])
#     if name == 'depth':
#         if is_add:
#             if current_val < 200:
#                 current_val = str(int(current_val) + 5)
#         else:
#             if current_val > 5:
#                 current_val = str(int(current_val) - 5)
#     elif name == 'movetime':
#         if is_add:
#             if current_val < 40000:
#                 current_val = str(int(current_val) + 5000)
#         else:
#             if current_val > 3000:
#                 current_val = str(int(current_val) - 5000)
#     else:
#         return jsonify({"error": "参数名错误"})
    
#     # 修改参数
#     engine.parameter['current'] = name
#     engine.parameter['value'][name] = current_val
#     engine.save_parameters()
#     print(f'修改后的参数:{engine.parameter}')
#     return jsonify({"message": engine.parameter})

# @app.route('/change_platform', methods=['POST'])
# def change_platform(): 
#     platfm = request.form.get('platform', 'TT')
#     data = {'platform':platfm}
#     with open('./app/json/platform.json', 'w') as file:
#         json.dump(data, file)
#     send_engine_ucinewgame()
#     return jsonify({"message": data})

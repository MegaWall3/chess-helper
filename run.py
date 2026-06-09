from app.routes import app 
import config
# 入口是哪个文件,就导入哪个文件(文件夹名.入口文件名)

if __name__ == '__main__':
    
    # 启动 Flask 应用，监听配置里的局域网端口
    
    app.run(host=config.SERVER_HOST,port=config.SERVER_PORT,debug=config.DEBUG)

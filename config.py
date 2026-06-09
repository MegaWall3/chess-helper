import os


# 本机局域网运行的默认配置集中放这里，避免后续全项目搜索零散数字。
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5050
DEBUG = True

PIKAFISH_HOME = './Pikafish'
CACHE_FOLDER = './cache/'
PIECE_IMAGE_HOME = './images'
ENGINE_THREADS = (os.cpu_count() or 1) * 2
ENGINE_HASH_MB = 256
ENGINE_MULTI_PV = 2

DEFAULT_PLATFORM = 'TT'
DEFAULT_AUTO_MODEL = 'Off'
DEFAULT_GO_PARAM = 'movetime'
DEFAULT_MOVETIME = '3000'
DEFAULT_DEPTH = '50'

import cv2
import numpy as np
import os
import config
from. import utils

class RecognitionError(Exception):
    pass

board_cache = None
board_cache_was_hit = False

def show_image(name, image):
    # 显示结果  
    cv2.imshow(name, image)  
    cv2.waitKey(0)  
    cv2.destroyAllWindows()

def pre_processing_image(img_path):
    img = cv2.imread(img_path)  
    if img is None:  
        print("Error: Image not found.")  
        return  None, None
    # print(f"图片宽高是:{img.shape[1]} x {img.shape[0]}")
    # 灰度化  
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) 

    return img, gray

# 棋盘坐标只缓存在进程内存中，不写 board.json。
def cached_board_recognition(img, gray):
    global board_cache, board_cache_was_hit
    if board_cache is not None:
        board_cache_was_hit = True
        return board_cache

    board_cache_was_hit = False
    x_array, y_array = board_recognition(img, gray)
    board_cache = (x_array, y_array)
    return x_array, y_array

def invalidate_board_cache():
    global board_cache, board_cache_was_hit
    board_cache = None
    board_cache_was_hit = False

def board_cache_debug():
    if board_cache is None:
        return "棋盘坐标: 无缓存"

    x_array, y_array = board_cache
    if board_cache_was_hit:
        return f"棋盘坐标: 缓存命中 x={x_array} y={y_array}"
    return f"棋盘坐标: x={x_array} y={y_array}"

# 识别棋盘
def board_recognition(img, gray):
    inferred = infer_board_from_piece_circles(img, gray)
    if inferred is not None:
        return inferred

    # 高斯模糊  
    gaus = cv2.GaussianBlur(gray, (5, 5), 0)  
    # 边缘检测  
    edges = cv2.Canny(gaus, 20, 120, apertureSize=3)  
    # show_image('Edges', edges)
    
    # 膨胀操作以合并相邻线条  
    # kernel = np.ones((3, 3), np.uint8)  # 定义膨胀核的大小，可以根据需要调整  
    # dilated_edges = cv2.dilate(edges, kernel, iterations=1) 
    
    # 腐蚀操作以恢复线条宽度  
    # eroded_edges = cv2.erode(dilated_edges, kernel, iterations=1) 
    
    # 可选：再次膨胀以调整线条宽度  
    # final_edges = cv2.dilate(eroded_edges, kernel, iterations=1)
    # show_image('Edges', final_edges)

    # 霍夫线变换  
    lines = cv2.HoughLinesP(edges, 0.5, np.pi/180, threshold=80, minLineLength=100, maxLineGap=5)  
    
    # 创建一张新图
    # black_img = np.zeros((img.shape[0], img.shape[1], 3), np.uint8)
    # black_img.fill(0) # 使用黑色填充图片区域

    # 过滤线段并在新图上绘制
    # 竖线 (x1 == x2)
    x_array = []
    vlines, yMin, yMax = utils.filter_vertical_lines(lines, img.shape[1])
    for line in vlines:  
        for x1, y1, x2, y2 in line:
            # cv2.line(black_img, (x1, yMin), (x2, yMax), (0, 255, 0), 1)
            x_array.append(int(x1))

    # 横线 (y1 == y2)
    y_array = []
    hlines, xMin, xMax = utils.filter_horizontal_lines(lines, img.shape[1])
    for line in hlines:  
        for x1, y1, x2, y2 in line:  
            # cv2.line(black_img, (xMin, y1), (xMax, y2), (0, 255, 0), 1)
            y_array.append(int(y1))
    
    
    # 显示结果 
    # show_image('Detected Lines', black_img) 
    # print(f"横坐标:{x_array}\n 纵坐标:{y_array}")

    return x_array, y_array

def infer_board_from_piece_circles(img, gray):
    width = img.shape[1]
    min_radius = int(0.8 * width / 9 / 2)
    max_radius = int(width / 9 / 2)
    min_dist = int(0.8 * width / 9)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, min_dist, param1=50, param2=30, minRadius=min_radius, maxRadius=max_radius)
    if circles is None:
        return None

    circles = np.round(circles[0, :]).astype("int")
    # 长截图只取 9:16 主区域推断棋盘，避开底部操作区。
    region = aspect_region(img, 9 / 16)
    return infer_board_from_circles(circles, region)


def infer_board_from_circles(circles, region):
    board_circles = [(x, y, r) for x, y, r in circles if point_in_region(x, y, region)]
    if len(board_circles) < 4:
        return None

    best_grid = find_best_board_grid(board_circles, region)
    if best_grid is None:
        return None

    x0, y0, step = best_grid
    x_array = [round(x0 + step * i) for i in range(9)]
    y_array = [round(y0 + step * i) for i in range(10)]
    return x_array, y_array

def find_best_board_grid(circles, region):
    best_grid = None
    best_score = None
    for step in grid_step_candidates(circles):
        for x, y, _ in circles:
            for col in range(9):
                x0 = x - col * step
                if not grid_x_in_region(x0, step, region):
                    continue
                for row in range(10):
                    y0 = y - row * step
                    if not grid_y_in_region(y0, step, region):
                        continue
                    score = score_board_grid(circles, x0, y0, step)
                    if best_score is None or score > best_score:
                        best_score = score
                        best_grid = (x0, y0, step)
    return best_grid

def grid_step_candidates(circles):
    median_radius = np.median([r for _, _, r in circles])
    min_step = median_radius * 1.6
    max_step = median_radius * 2.8
    steps = set()

    for index, (x1, y1, _) in enumerate(circles):
        for x2, y2, _ in circles[index + 1:]:
            add_step_candidates(steps, abs(x2 - x1), 8, min_step, max_step)
            add_step_candidates(steps, abs(y2 - y1), 9, min_step, max_step)

    return sorted(steps)

def add_step_candidates(steps, distance, max_grid_span, min_step, max_step):
    for span in range(1, max_grid_span + 1):
        step = distance / span
        if min_step <= step <= max_step:
            steps.add(round(step))

def grid_x_in_region(x0, step, region):
    x_min, _, x_max, _ = region
    return x_min - step <= x0 and x0 + step * 8 <= x_max + step

def grid_y_in_region(y0, step, region):
    _, y_min, _, y_max = region
    return y_min - step <= y0 and y0 + step * 9 <= y_max + step

def score_board_grid(circles, x0, y0, step):
    tolerance = step * 0.28
    matched_points = set()
    error = 0
    for x, y, _ in circles:
        col = round((x - x0) / step)
        row = round((y - y0) / step)
        if not (0 <= col < 9 and 0 <= row < 10):
            continue

        grid_x = x0 + col * step
        grid_y = y0 + row * step
        distance = ((x - grid_x) ** 2 + (y - grid_y) ** 2) ** 0.5
        if distance <= tolerance:
            matched_points.add((col, row))
            error += distance

    # 命中棋子越多越好；误差只作为同分时的细微排序。
    return len(matched_points), -error

def aspect_region(img, target_ratio):
    height, width = img.shape[:2]
    current_ratio = width / height
    if current_ratio >= target_ratio:
        region_width = int(height * target_ratio)
        x_min = (width - region_width) // 2
        return x_min, 0, x_min + region_width, height

    region_height = int(width / target_ratio)
    return 0, 0, width, min(height, region_height)

def point_in_region(x, y, region):
    x_min, y_min, x_max, y_max = region
    return x_min <= x <= x_max and y_min <= y <= y_max

# 识别棋子
def pieces_recognition(img, gray, param, x_array=None, y_array=None):

    # 模糊处理，不管是用mediaBlur还是GaussianBlur, 实际发现这不是必要的。用霍夫圆检测，直接使用灰度图也一样能找出来，可能棋子的圆相对规范的原因？
    #blur = cv2.medianBlur(gray, 5)
    #gaus = cv2.GaussianBlur(gray,(3,3),0)

    width = img.shape[1]
    maxRadius=int(width/9/2) # 棋盘宽度除以9 （横向最多就放9个棋子, 再除2 就是半径啦）
    minRadius=int(0.8* width/9/2)
    minDist = int(0.8 * width/9)  # 棋子与棋子间距，最小就是2个半径也就是直径。考虑误差，X0.8放宽一下条件
    
    # 检测圆形. 参数的设置很重要。它决定了哪些圆命中出来。参数设置有最小最大半径，以及各圆心间距等
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, minDist, param1=50, param2=30, minRadius=minRadius, maxRadius=maxRadius)
    
    # 绘制圆形
    pieces = []
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        # 只保留棋盘范围内的圆，避免把界面按钮当成棋子。
        board_bounds = board_region_bounds(x_array, y_array)
        # print("Total circles", len(circles))
        
        for idx, (x, y, r) in enumerate(circles):  # index 用来后面存图片比对用的
            if board_bounds is not None:
                x_min_bound, x_max_bound, y_min_bound, y_max_bound = board_bounds
                if not (x_min_bound <= x <= x_max_bound and y_min_bound <= y <= y_max_bound):
                    continue

            # 在图像上画圆
            # cv2.circle(img, (x, y), r, (0, 255, 0), 2)

            x1,y1,x2,y2= x-r, y-r, x+r, y+r

            if x1 < 0: x1 = 0  
            if y1 < 0: y1 = 0  
            if x2 >= img.shape[1]: x2 = img.shape[1] - 1  
            if y2 >= img.shape[0]: y2 = img.shape[0] - 1

            # cv2.imwrite(f"chess{idx}.jpg",img[y1:y2,x1:x2]) # 切割棋子保存到本地
            # print(f"slice coordinates ({x1}, {y1}) to ({x2}, {y2}) shape {img[y1:y2+1,x1:x2+1].shape}") 
            color = check_chess_piece_color_v2(img[y1:y2+1,x1:x2+1])
            if color is None:  
                print("Failed to determine color for this slice.")  
            # else:  
                # print(f"Determined color for slice: {color}")
            # print(f"棋子颜色为{idx}: {color}")

            # 根据游戏平台选择对比图片
            platform = param['platform']
            if platform == 'JJ':
                path_str = os.path.join(config.PIECE_IMAGE_HOME, 'jj')
            else:
                path_str = os.path.join(config.PIECE_IMAGE_HOME, 'tiantian')
            best_match, best_score = find_best_match(img[y1:y2+1,x1:x2+1], path_str)  
            if best_match is None:
                raise RecognitionError(f"未匹配到棋子: 平台={platform}, 颜色={color}, 坐标=({x},{y}), 分数={best_score}")
            pieces.append((x, y, r, utils.cut_substring(best_match)))
            # print(f"棋子圆心与半径:({x},{y}), {r},Best match: {utils.cut_substring(best_match)} score {best_score}")

            # show_image('Pieces', img[y1:y2,x1:x2])
    # show_image('Circles',img)
    return pieces

def board_region_bounds(x_array, y_array):
    if x_array is None or y_array is None or len(x_array) != 9 or len(y_array) != 10:
        return None

    x_margin = (max(x_array) - min(x_array)) / 8 / 2
    y_margin = (max(y_array) - min(y_array)) / 9 / 2
    return (
        min(x_array) - x_margin,
        max(x_array) + x_margin,
        min(y_array) - y_margin,
        max(y_array) + y_margin,
    )

#比较两张图片的特征点,返回相似度
def compare_feature(img1,img2):
    sift=cv2.SIFT_create()
    kp1,des1=sift.detectAndCompute(img1,None)
    kp2,des2=sift.detectAndCompute(img2,None)
    bf=cv2.BFMatcher()
    matches=bf.knnMatch(des1,des2,k=2)
    good=[]
    for m,n in matches:
        if m.distance<0.75*n.distance:
            good.append([m])
    return len(good)

# 判断棋子红色与黑色  (未使用)
def check_chess_piece_color_v2(img):
    if img is None or img.size == 0:  
        print(f"Error: img is None or empty (shape: {img.shape if img is not None else 'None'})")  
        return None  # 或者你可以返回一个表示错误的特殊值或抛出异常  

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)  
    if hsv is None or hsv.size == 0:  
        print(f"Error: Failed to convert image to HSV (shape before: {img.shape})")  
        return None  # 同样，返回特殊值或抛出异常 

    height, width = hsv.shape[:2]
    yy, xx = np.ogrid[:height, :width]
    center_mask = ((xx - width / 2) ** 2 + (yy - height / 2) ** 2 <= (min(height, width) * 0.34) ** 2)
    center_mask = center_mask.astype(np.uint8) * 255

    # 只看棋子内圈文字区域，避免外圈木纹、阴影把红棋误判成黑棋。
    red_mask = cv2.inRange(hsv, np.array([0, 70, 20], dtype=np.uint8), np.array([17, 255, 210], dtype=np.uint8))
    red_mask = cv2.bitwise_or(
        red_mask,
        cv2.inRange(hsv, np.array([150, 70, 20], dtype=np.uint8), np.array([180, 255, 210], dtype=np.uint8))
    )
    red_mask = cv2.bitwise_and(red_mask, center_mask)

    # 黑棋文字在内圈里亮度明显更低；木质背景的红黄色不计入黑棋笔画。
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  
    black_mask = cv2.inRange(gray, 0, 115)
    black_mask = cv2.bitwise_and(black_mask, center_mask)
  
    # 计算红色和黑色区域的面积  
    red_area = cv2.countNonZero(red_mask)  
    black_area = cv2.countNonZero(black_mask)  
  
    # 返回颜色判断结果  
    return "red" if red_area > black_area else 'black' 


# 判断棋子红黑
def check_chess_piece_color_v1(img):
    # 将图像从BGR转换到HSV  
    hsv_roi = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)  
    hsv_values = hsv_roi.reshape((-1, 3))
    v_min, _ = np.min(hsv_values[:, 2]), np.max(hsv_values[:, 2])
      
    # 通过measure_color_range()函数逐个打印发现低于这个值的为黑色，高于这个值的为红色
    # 临时办法: 不确定是否稳定,以及对其他棋盘图像是否有效   
    threshold = 12   
      
    if v_min > threshold:  
        return "red"  
    else:  
        return "black" 

def find_best_match(img, images_folder):  
    # 首先判断棋子的颜色  
    color = check_chess_piece_color_v2(img)  
      
    # 初始化最高分和最佳匹配  
    best_score = 0  
    best_match = None  
      
    # 遍历images_folder中的所有图片  
    for filename in os.listdir(images_folder):  
        if filename.endswith('.jpg'): 
            # 检查文件名是否与目标棋子颜色匹配  
            if (color == 'red' and filename.startswith('red_')) or (color == 'black' and filename.startswith('black_')):  
                local_img_path = os.path.join(images_folder, filename)  
                local_img = cv2.imread(local_img_path)  
                if local_img is not None:  
                    # 计算两张图片的相似度  
                    score = compare_feature(img, local_img)  
                    # 更新最高分和最佳匹配  
                    if score > best_score:  
                        best_score = score  
                        best_match = filename  
      
    return best_match, best_score

# 计算棋子坐标
def find_nearest_index(point, points):  
    distances = [abs(point - p) for p in points]  # 计算点到所有竖线x坐标的绝对值差异  
    return distances.index(min(distances))  # 返回最接近的竖线的索引 
  
def calculate_pieces_position(x_array, y_array, circles):  
    # 处理circles，计算每个圆心到最近的竖线和横线的索引，并更新pieceArray  
    
    # 初始化pieceArray  
    pieceArray = [["-"] * len(x_array) for _ in range(len(y_array))]  
      
    for cx, cy, radius, name in circles:  
        # 找到最接近的竖线和横线的索引  
        nearest_x_index = find_nearest_index(cx, x_array)  
        nearest_y_index = find_nearest_index(cy, y_array)  
          
        # 可选：检查圆心是否“足够接近”某条竖线或横线（使用半径作为阈值）  
        # 这里我们简单地标记最近的竖线和横线，不考虑阈值  
          
        # 在pieceArray中标记圆心位置  
        # 注意：这里我们假设要在一个“单元格”中标记圆心，即一个特定的(x, y)索引  
        pieceArray[nearest_y_index][nearest_x_index] = name  # 或者使用其他标记方式  
          
        # 如果想要表示圆心的范围（例如，使用半径画圆），则需要更复杂的逻辑  
        # 这通常涉及到在pieceArray中设置多个单元格，可能还需要额外的数据结构或算法  
    
    # 判断本方是红棋还是黑棋
    # 寻找 "K" 的位置以判断是红方还是黑方
    is_red = False
    for row in pieceArray[:3]: # 老将只会在9宫,所以只看前3行
        for cell in row:
            if 'k' in cell:
                is_red = True
                break
        if is_red:
            break

    return pieceArray, is_red   
  
# 测试棋子的HVS范围并打印
# def measure_color_range(roi):  
 
#     # 转换到HSV颜色空间  
#     hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)  
        
#     # 计算并显示颜色范围（这里只是简单地显示所有HSV值）  
#     # 在实际应用中，你可能需要分析这些值来确定合适的范围  
#     hsv_values = hsv_roi.reshape((-1, 3))  # 将图像转换为一维数组，每三个元素为一个HSV值  
        
#     # 打印或分析HSV值  
#     # 例如，你可以找到H、S、V通道的最小值和最大值  
#     h_min, h_max = np.min(hsv_values[:, 0]), np.max(hsv_values[:, 0])  
#     s_min, s_max = np.min(hsv_values[:, 1]), np.max(hsv_values[:, 1])  
#     v_min, v_max = np.min(hsv_values[:, 2]), np.max(hsv_values[:, 2])  
        
#     print(f"H range: {h_min} to {h_max}")  
#     print(f"S range: {s_min} to {s_max}")  
#     print(f"V range: {v_min} to {v_max}")  

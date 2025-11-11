import cv2
import datetime
from time import sleep
import os
import glob
from database.db_manager import insert_camera_log, insert_system_log, select_layer_info
from config import *

def get_file_name():
    """ファイル名を生成（例: 20250910_100000.jpg）"""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S.jpg")

def save_image(frame, file_path):
    """画像をJPEG形式で保存"""
    # 拡張子を強制的に .jpg にする
    if not file_path.lower().endswith(('.jpg', '.jpeg')):
        file_path = file_path.rsplit('.', 1)[0] + '.jpg'
    
    # JPEG形式で保存（品質95%）
    cv2.imwrite(file_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

def delete_old_images(save_dir):
    """指定期間より古い画像を自動削除"""
    today = datetime.datetime.now()
    cutoff_date = today - datetime.timedelta(days=RETENTION_DAYS)
    
    # jpg, jpeg, png形式の画像を対象にする
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        image_files.extend(glob.glob(os.path.join(save_dir, ext)))
    
    for file_path in image_files:
        try:
            timestamp = os.path.getctime(file_path)
            file_date = datetime.datetime.fromtimestamp(timestamp)
            
            if file_date < cutoff_date:
                os.remove(file_path)
        except Exception as e:
            # 削除エラーはCRITICALではないため、システムログには記録せず、コンソール出力のみ
            print(f"警告: 古い画像ファイル {file_path} の削除中にエラー: {e}")


# --- メインジョブ関数 ---
def execute_photo_job(layer_id: int):
    """
    指定された層 (layer_id) のカメラを起動し、撮影、保存、DB記録を行う。
    """
    SAVE_DIR = os.path.join(BASE_SAVE_DIR, f"layer_{layer_id}")
    
    # 1. 保存ディレクトリを作成
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    layer_info = select_layer_info(layer_id)
    
    if not layer_info:
        error_msg = f"Layer {layer_id} の情報がDBに見つかりません。"
        insert_system_log(
            layer_id=layer_id, 
            log_level='ERROR', 
            message=error_msg, 
            details='Layer ID not found in layers table.')
        print(f"エラー: {error_msg}")
        return
        
    camera_id = layer_info['cam_id'] # cam_id (例: '/dev/video0' または 0) を使用
    
    # 撮影前のディレイ処理
    # layer_id が 1 なら 0秒、2なら 2秒、3なら 4秒待つ (2秒間隔)
    delay_sec = (layer_id - 1) * 2 
    
    if delay_sec > 0:
        print(f"[{datetime.now()}] [CAMERA JOB] Layer {layer_id} は、リソース競合を避けるため {delay_sec} 秒待機します。")
        sleep(delay_sec)
    
    cap = cv2.VideoCapture(camera_id)

    if not cap.isOpened():
        error_msg = f"カメラ(ID:{camera_id})接続失敗。"
        insert_system_log(
            layer_id=layer_id, 
            log_level='ERROR', 
            message=error_msg, 
            details=f'VideoCapture({camera_id}) failed to open.')
        print(f"エラー: {error_msg}")
        return

    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, IMAGE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, IMAGE_HEIGHT)

        ret, frame = cap.read()
        cap.release() 

        if not ret:
            error_msg = f"Layer {layer_id} のフレーム読み込み失敗。"
            insert_system_log(
                layer_id=layer_id, 
                log_level='ERROR', 
                message=error_msg, 
                details='cap.read() returned False.')
            print(f"エラー: {error_msg}")
            return
        
        file_name = get_file_name()
        relative_file_path = os.path.join(SAVE_DIR, file_name) 
        
        save_image(frame, relative_file_path)
        
        insert_camera_log(layer_id, relative_file_path)
        
        insert_system_log(
            layer_id=layer_id, 
            log_level='INFO', 
            message='Camera job finished successfully.', 
            details=f'Path: {relative_file_path}')
        
        delete_old_images(SAVE_DIR)
        
        print(f"[CAMERA JOB] Layer {layer_id} の画像を {relative_file_path} に保存しました。")

    except Exception as e:
        insert_system_log(
            layer_id=layer_id, 
            log_level='ERROR', 
            message='Unexpected error during photo job.', 
            details=str(e))
        print(f"[CRITICAL ERROR] Photo job failed: {e}")
    finally:
        if cap.isOpened():
            cap.release()
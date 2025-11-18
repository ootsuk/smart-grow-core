import cv2
import datetime
from time import sleep
import os
import glob
from database.db_manager import insert_camera_log, insert_system_log, select_layer_info
from config import *

# AI解析ジョブをインポート
try:
    from jobs.ai_analysis_job import execute_ai_analysis_job
    AI_ANALYSIS_AVAILABLE = True
except ImportError:
    AI_ANALYSIS_AVAILABLE = False
    print("警告: AI解析ジョブがインポートできません。AI解析は実行されません。")

def get_file_name():
    """ファイル名を生成（例: 20250910_100000.jpg）"""
    now = datetime.datetime.now()
    return now.strftime("%Y%m%d_%H%M%S.jpg")

def is_valid_image(frame):
    """
    フレームが有効な画像かチェック（真っ黒な画像を検出）
    
    Returns:
        bool: 有効な画像ならTrue、真っ黒ならFalse
    """
    import numpy as np
    
    if frame is None or frame.size == 0:
        return False
    
    # 画像の平均輝度を計算
    mean_brightness = np.mean(frame)
    
    # 平均輝度が極端に低い（5未満）場合は真っ黒と判定
    # 通常の画像は30以上の輝度がある
    if mean_brightness < 5.0:
        print(f"[CAMERA] 警告: 真っ黒な画像を検出（平均輝度: {mean_brightness:.2f}）")
        return False
    
    # 画像の標準偏差をチェック（全ピクセルが同じ値の場合は0に近い）
    std_deviation = np.std(frame)
    if std_deviation < 1.0:
        print(f"[CAMERA] 警告: 変化のない画像を検出（標準偏差: {std_deviation:.2f}）")
        return False
    
    return True

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
    # 絶対パスでディレクトリを作成
    SAVE_DIR_ABS = os.path.join(BASE_SAVE_DIR, f"layer_{layer_id}")
    # Web表示用の相対パス
    SAVE_DIR_REL = f"plant_images/layer_{layer_id}"
    
    # 1. 保存ディレクトリを作成
    if not os.path.exists(SAVE_DIR_ABS):
        os.makedirs(SAVE_DIR_ABS)

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
        print(f"[{datetime.datetime.now()}] [CAMERA JOB] Layer {layer_id} は、リソース競合を避けるため {delay_sec} 秒待機します。")
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
        
        # 画像の有効性をチェック（真っ黒な画像を除外）
        if not is_valid_image(frame):
            error_msg = f"Layer {layer_id} の画像が無効（真っ黒または変化なし）。"
            insert_system_log(
                layer_id=layer_id, 
                log_level='WARNING', 
                message=error_msg, 
                details='Image validation failed. Camera may not be connected.')
            print(f"警告: {error_msg}")
            return
        
        file_name = get_file_name()
        # 絶対パス（ファイル保存用）
        absolute_file_path = os.path.join(SAVE_DIR_ABS, file_name)
        # 相対パス（DB/Web表示用）
        relative_file_path = f"{SAVE_DIR_REL}/{file_name}"
        
        save_image(frame, absolute_file_path)
        
        insert_camera_log(layer_id, relative_file_path)
        
        insert_system_log(
            layer_id=layer_id, 
            log_level='INFO', 
            message='Camera job finished successfully.', 
            details=f'Path: {relative_file_path}')
        
        delete_old_images(SAVE_DIR_ABS)
        
        print(f"[CAMERA JOB] Layer {layer_id} の画像を {relative_file_path} に保存しました。")
        
        # AI解析ジョブを実行（LLM_API_KEYが設定されている場合のみ）
        if AI_ANALYSIS_AVAILABLE and LLM_API_KEY:
            try:
                print(f"[CAMERA JOB] AI解析ジョブを開始します...")
                execute_ai_analysis_job(layer_id, relative_file_path)
            except Exception as ai_error:
                # AI解析のエラーはカメラジョブ全体の失敗とはしない
                insert_system_log(
                    layer_id=layer_id,
                    log_level='WARNING',
                    message='AI analysis job failed after camera capture.',
                    details=str(ai_error))
                print(f"[WARNING] AI解析ジョブでエラーが発生しましたが、カメラ撮影は成功しています: {ai_error}")

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
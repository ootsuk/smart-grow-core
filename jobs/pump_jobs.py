from time import sleep
from datetime import datetime
from database.db_manager import select_system_config, insert_system_log

# --- gpiozero を安全にインポート ---
try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False


def execute_pump_job(layer_id: int):
    """
    水ポンプ制御ジョブ。
    指定された層(layer_id)のポンプを一定時間ONにしてOFFにする。
    リレーモジュール AE-G5V-DRV を使用
    """
    # TODO:水圧センサ水完成後安全確認ロジックを追加 （給水、排水タンクの確認）
    # 例:
    # if tank_is_full():
    #     print("[WATER JOB] 排水タンクが満タンのため中止しました。")
    #     return

    config = select_system_config() or {}
    pump_pin = config.get("pump_gpio_sig", 17)
    duration = config.get("water_duration_sec", 10)
    
    print(f"[{datetime.now()}] [WATER JOB START] Layer {layer_id} の水ポンプ制御を開始します。")
    # ログ記録: ジョブ開始
    insert_system_log(
        layer_id=layer_id, 
        log_level='INFO',
        message='Pump job started.',
        details=f"GPIO Pin: {pump_pin}, Duration: {duration}s"
    )
 
    if not GPIO_AVAILABLE:
        print("[INFO] GPIOライブラリが利用できない環境です。ダミーモードで動作します。")
        print("[DUMMY] 5秒間ポンプON → OFF（実際の制御は行われません）")
        sleep(duration)
        print("[DUMMY] ポンプOFF完了。")
        
        insert_system_log(
            layer_id=layer_id, 
            log_level='INFO', 
            message='GPIO library not available, running in dummy mode.', 
            details='Dummy mode: GPIO not available, no actual pump control performed.'
        )   
        return
    
    pump = None
    
    try:
        pump = OutputDevice(pump_pin, active_high=False, initial_value=False)
        # ポンプをON（リレーLOW出力）
        pump.off()
        print(f"[WATER JOB] ポンプを {duration} 秒間動作させます。")
        sleep(duration)
        #　ログ記録：成功
        insert_system_log(
            layer_id=layer_id, 
            log_level='INFO', 
            message='Pump job completed successfully.', 
            details='Pump turned OFF after operation.'
        )
        
    except Exception as e:
        print(f"[WATER JOB ERROR] {e}")
        insert_system_log(
            layer_id=layer_id, 
            log_level='CRITICAL', 
            message='Error occurred during pump job.', 
            details=f'[CRITICAL ERROR] pomp job failed: {e}'
        )
        
    finally:
        if pump:
            # ポンプを確実にOFFに
            pump.on()
        print(f"[{datetime.now()}] [WATER JOB END] Layer {layer_id} のポンプ制御を終了しました。")
        
        # ログ記録: ジョブ終了
        end_msg = f"Layer {layer_id} のポンプ制御プロセス全体を終了しました。"
        print(f"[{datetime.now()}] [WATER JOB END] {end_msg}")
        
        insert_system_log(
            layer_id=layer_id, 
            log_level='INFO', 
            message='Pump job process terminated.',
            details='Pump OFF attempt was completed in finally block.'
        )
        
if __name__ == "__main__":
    # テスト実行
    execute_pump_job(layer_id=1)
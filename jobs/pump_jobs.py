from datetime import datetime
from database.db_manager import select_system_config, insert_system_log
from hardware.pump_controller import activate_pump

def execute_pump_job(layer_id: int):
    """
    水ポンプ制御ジョブ。
    システム設定からピン番号と作動時間を取得し、ポンプ制御関数を呼び出す。
    """
    print(f"[{datetime.now()}] [WATER JOB START] Layer {layer_id} の水ポンプ制御を開始します。")

    config = select_system_config() or {}
    # `pump_gpio_sig` というキー名でDBに保存されている
    pump_pin = config.get("pump_gpio_sig", 17)
    duration = config.get("water_duration_sec", 10)
    
    # ログ記録: ジョブ開始
    insert_system_log(
        layer_id=layer_id, 
        log_level='INFO',
        message='Pump job started.',
        details=f"Attempting to run pump on GPIO {pump_pin} for {duration}s."
    )

    # TODO:水圧センサの値に基づいた安全確認ロジックを追加
    # 例:
    # supply_pressure = get_latest_tank_status(0).get('supply_pressure')
    # if supply_pressure < config.get('supply_low_threshold'):
    #     insert_system_log(layer_id, 'WARNING', 'Pump job skipped: Supply tank level is too low.')
    #     print("[WATER JOB] 給水タンクの水位が低いため、ポンプ作動を中止しました。")
    #     return

    # ハードウェア制御関数を呼び出す
    success, message = activate_pump(pin=pump_pin, duration_sec=duration)
    
    if success:
        log_level = 'INFO'
        log_message = 'Pump job completed successfully.'
    else:
        log_level = 'CRITICAL'
        log_message = 'Error occurred during pump job.'

    # ログ記録: ジョブ完了
    insert_system_log(
        layer_id=layer_id,
        log_level=log_level,
        message=log_message,
        details=message
    )
    
    print(f"[{datetime.now()}] [WATER JOB END] Layer {layer_id} のポンプ制御を終了しました。 Status: {log_level}")

if __name__ == "__main__":
    # テスト実行
    print("ポンプジョブのテスト実行を開始します...")
    # Layer 0 はシステム全体を指すため、テストでもそれを模倣
    execute_pump_job(layer_id=0)
    print("ポンプジョブのテスト実行が完了しました。")

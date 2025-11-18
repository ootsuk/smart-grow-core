from time import sleep

# --- gpiozero を安全にインポート ---
try:
    from gpiozero import OutputDevice
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[HARDWARE] GPIOライブラリが利用できないため、ダミーモードで動作します。")

def activate_pump(pin: int, duration_sec: int):
    """
    指定されたGPIOピンに接続されたポンプを一定時間作動させる。

    Args:
        pin (int): ポンプが接続されているGPIOピン番号。
        duration_sec (int): ポンプを作動させる秒数。

    Returns:
        bool: 制御が成功したかどうか。
        str: 処理結果のメッセージ。
    """
    if not GPIO_AVAILABLE:
        print(f"[DUMMY PUMP] ポンプを {duration_sec} 秒間ONにします（実際の制御なし）。")
        sleep(duration_sec)
        print("[DUMMY PUMP] ポンプOFF完了。")
        return True, "Dummy mode: GPIO not available."

    pump_device = None
    try:
        # リレーモジュールは active_high=False で制御することが多い
        pump_device = OutputDevice(pin, active_high=False, initial_value=False)

        # ポンプをON（リレーにLOW信号を送る）
        pump_device.off()
        print(f"[PUMP CONTROLLER] GPIO {pin} のポンプを {duration_sec} 秒間作動させます。")
        sleep(duration_sec)

        return True, f"Pump on GPIO {pin} ran for {duration_sec} seconds."

    except Exception as e:
        error_msg = f"ポンプ制御エラー (GPIO {pin}): {e}"
        print(f"[PUMP CONTROLLER ERROR] {error_msg}")
        return False, error_msg

    finally:
        if pump_device:
            # ポンプを確実にOFF（リレーにHIGH信号を送る）
            pump_device.on()
            pump_device.close()
            print(f"[PUMP CONTROLLER] GPIO {pin} のポンプを停止し、リソースを解放しました。")

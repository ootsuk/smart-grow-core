import time
import errno # OSErrorのerrnoを扱うためにインポート
import random
import platform

# --- smbus2を安全にインポート ---
try:
    import smbus2
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False

from config import AHT_ADDRESS, AHT_TRIGGER_CMD
    
def read_aht_sensor(i2c_bus_num=1):
    """
    AHT25/AHT20センサーから温湿度データを1回取得し、辞書で返す。
    
    Args:
        i2c_bus_num (int): I2Cバスの番号 (デフォルト: 1)
        
    Returns:
        dict: {"temperature": T, "humidity": H} のデータ, または None
    """
    simulate = False
    # --- 自動的にPCではsimulateモードにする ---
    if not SMBUS_AVAILABLE or platform.system() != "Linux":
        simulate = True

    if simulate:
        # ダミーデータ（安定動作確認用）
        print("AHT Sensor Simulation Mode: 実機ではありません。")
        return {"temperature": 23.5, "humidity": 45.2}

    try:
        # I2Cバスに接続
        i2c = smbus2.SMBus(i2c_bus_num)
        
        # 1. 初期化コマンドの送信 (0xBE, 0x08, 0x00)
        # これはセンサーのキャリブレーションやステータス設定を行うためのコマンドです
        i2c.write_i2c_block_data(AHT_ADDRESS, 0xBE, [0x08, 0x00])
        time.sleep(0.2)
        
        # 2. 測定トリガコマンド送信 (0xAC, 0x33, 0x00)
        i2c.write_i2c_block_data(AHT_ADDRESS, 0xAC, [0x33, 0x00])
        time.sleep(0.5) # 測定完了を待機
        
        # 3. データの読み込み
        try:
            # 6バイトのデータを読み込む (Status, RH_H, RH_M, RH_L/Temp_H, Temp_M, Temp_L)
            data = i2c.read_i2c_block_data(AHT_ADDRESS, 0x00, 6)
        except OSError as e:
            # エラー121 (Remote I/O error) は、センサーがまだ準備できていない可能性があるため再試行
            if e.errno == errno.EREMOTEIO: # EREMOTEIO は通常 121
                time.sleep(0.1)
                data = i2c.read_i2c_block_data(AHT_ADDRESS, 0x00, 6)
            else:
                raise # その他のOSErrorは再スロー
                
        # 4. データ変換と物理量計算

        hum_raw = (data[1] << 12) | (data[2] << 4) | (data[3] >> 4)
        humidity = hum_raw * 100 / 1048576.0 # 2^20 = 1048576.0
        
        # 温度 (℃)
        temp_raw = ((data[3] & 0x0F) << 16) | (data[4] << 8) | data[5]
        temperature = temp_raw * 200 / 1048576.0 - 50
        
        return {
            "temperature": round(temperature, 2), 
            "humidity": round(humidity, 2)
        }
            
    except FileNotFoundError:
        print("AHT Sensor Error: I2Cバスが見つかりません。I2Cが有効か確認してください。")
        return None
    except Exception as e:
        print(f"AHT Sensor Error: 読み取り中に予期せぬエラーが発生しました: {e}")
        return None
    
    
def read_pressure_sensor(sim_name: str) -> float | None:
    """
    水圧センサー（MS5837）のダミー値を返す。10回に1回は読み取りエラーをシミュレートする。
    単位は MS5837 ライブラリのデフォルトに合わせ「mbar (ミリバール)」とする。

    :param sim_name: センサーの識別名 ('Supply' または 'Drain')
    :return: 圧力値 (mbar, float) または None (読み取り失敗時)
    """
    # --- 将来、本物のセンサーを接続する場合 例---
    # if SMBUS_AVAILABLE and platform.system() == "Linux":
    #     try:
    #         # import ms5837
    #         # sensor = ms5837.MS5837_30BA() # モデルに合わせて選択
    #         # if not sensor.init():
    #         #     print("Sensor could not be initialized")
    #         #     return None
    #         # sensor.read()
    #         # return round(sensor.pressure(), 2) # mbar
    #     except Exception as e:
    #         print(f"{sim_name} Pressure Sensor Error: {e}")
    #         return None

    # --- 以下はダミーモードの動作 ---
    # 10%の確率でNoneを返し、読み取りエラーをシミュレート
    if random.randint(1, 10) == 1:
        print(f"{sim_name} Pressure Sensor Simulation: 読み取りエラー（Noneを返します）")
        return None
    
    # ダミー値: センサーの種類によって異なる範囲を設定
    if sim_name == "Supply":
        # 給水タンク: 100〜150 kPa (満タン時は高圧)
        dummy_pressure = random.uniform(100.0, 150.0)
    else:  # "Drain"
        # 排水タンク: 50〜100 kPa (通常は低圧、溜まると上昇)
        dummy_pressure = random.uniform(50.0, 100.0)
    
    return round(dummy_pressure, 2)

def read_supply_pressure() -> float | None:
    """
    給水タンクの水圧/水位を読み取るダミー関数。
    """
    return read_pressure_sensor("Supply")

def read_drain_pressure() -> float | None:
    """
    排水タンクの水圧/水位を読み取るダミー関数。
    """
    return read_pressure_sensor("Drain")
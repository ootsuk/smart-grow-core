"""
30日間分のセンサーテストデータを生成してデータベースに挿入するスクリプト
"""
from datetime import datetime, timedelta
import random
import math
from database.db_manager import open_db

def generate_sensor_test_data(days=30, interval_minutes=30, layer_id=1):
    """
    指定期間のセンサーテストデータを生成
    
    Args:
        days: データ生成する日数（デフォルト: 30日）
        interval_minutes: データ取得間隔（分）（デフォルト: 30分）
        layer_id: レイヤーID（デフォルト: 1）
    """
    print(f"📊 {days}日間分のテストデータを生成します...")
    print(f"   間隔: {interval_minutes}分おき")
    print(f"   データ件数: 約 {(days * 24 * 60) // interval_minutes}件")
    
    # 現在時刻から過去に遡る
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    # データ生成
    data_points = []
    current_time = start_time
    count = 0
    
    while current_time <= end_time:
        # 時間ベースの変動パターン（日周期）
        hour = current_time.hour
        day_of_year = current_time.timetuple().tm_yday
        
        # 温度: 15℃〜30℃の間で変動（日周期 + ランダムノイズ）
        # 昼間（12時）に最高、夜中（0時）に最低
        temp_base = 22.5  # 基準温度
        temp_daily_variation = 5.0 * math.sin((hour - 6) * math.pi / 12)  # ±5℃の日周期
        temp_noise = random.uniform(-1.5, 1.5)  # ノイズ
        temperature = round(temp_base + temp_daily_variation + temp_noise, 1)
        
        # 湿度: 30%〜70%の間で変動（温度と逆相関）
        humidity_base = 50.0
        humidity_daily_variation = -10.0 * math.sin((hour - 6) * math.pi / 12)  # 温度と逆
        humidity_noise = random.uniform(-3, 3)
        humidity = round(max(30, min(70, humidity_base + humidity_daily_variation + humidity_noise)), 1)
        
        # 給水タンク圧力: 70〜110 kPa（徐々に減少し、時々補給でジャンプ）
        # 12時間ごとに補給イベント
        hours_since_start = (current_time - start_time).total_seconds() / 3600
        supply_cycle = (hours_since_start % 12) / 12  # 0〜1のサイクル
        supply_pressure = round(110 - (supply_cycle * 30) + random.uniform(-3, 3), 1)
        
        # 排水タンク圧力: 80〜140 kPa（徐々に増加し、時々排水でリセット）
        # 24時間ごとに排水イベント
        drain_cycle = (hours_since_start % 24) / 24  # 0〜1のサイクル
        drain_pressure = round(80 + (drain_cycle * 50) + random.uniform(-3, 3), 1)
        
        data_points.append({
            'layer_id': layer_id,
            'timestamp': current_time.isoformat(),
            'temperature': temperature,
            'humidity': humidity,
            'supply_pressure': supply_pressure,
            'drain_pressure': drain_pressure
        })
        
        current_time += timedelta(minutes=interval_minutes)
        count += 1
        
        # 進捗表示（100件ごと）
        if count % 100 == 0:
            print(f"   生成中... {count}件")
    
    print(f"✅ {count}件のデータ生成完了")
    return data_points

def insert_test_data(data_points):
    """
    生成したテストデータをデータベースに挿入
    
    Args:
        data_points: データポイントのリスト
    """
    print(f"\n💾 データベースに挿入中...")
    
    with open_db() as conn:
        cursor = conn.cursor()
        
        # 既存のテストデータを削除（必要に応じて）
        # cursor.execute("DELETE FROM sensor_logs WHERE layer_id = ?", (1,))
        # print("   既存データをクリアしました")
        
        # データ挿入
        inserted = 0
        for data in data_points:
            cursor.execute("""
                INSERT INTO sensor_logs 
                (layer_id, timestamp, temperature, humidity, supply_pressure, drain_pressure)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data['layer_id'],
                data['timestamp'],
                data['temperature'],
                data['humidity'],
                data['supply_pressure'],
                data['drain_pressure']
            ))
            inserted += 1
            
            if inserted % 200 == 0:
                print(f"   挿入中... {inserted}件")
        
        print(f"✅ {inserted}件のデータを挿入完了")

def verify_data():
    """
    挿入されたデータを検証
    """
    print(f"\n🔍 データ検証中...")
    
    with open_db() as conn:
        cursor = conn.cursor()
        
        # 総件数
        cursor.execute("SELECT COUNT(*) as count FROM sensor_logs WHERE layer_id = 1")
        total = cursor.fetchone()['count']
        print(f"   総データ件数: {total}件")
        
        # 最古のデータ
        cursor.execute("""
            SELECT timestamp, temperature, humidity 
            FROM sensor_logs 
            WHERE layer_id = 1 
            ORDER BY timestamp ASC 
            LIMIT 1
        """)
        oldest = cursor.fetchone()
        print(f"   最古データ: {oldest['timestamp']} (温度: {oldest['temperature']}℃)")
        
        # 最新のデータ
        cursor.execute("""
            SELECT timestamp, temperature, humidity 
            FROM sensor_logs 
            WHERE layer_id = 1 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        latest = cursor.fetchone()
        print(f"   最新データ: {latest['timestamp']} (温度: {latest['temperature']}℃)")
        
        # 統計情報
        cursor.execute("""
            SELECT 
                AVG(temperature) as avg_temp,
                MIN(temperature) as min_temp,
                MAX(temperature) as max_temp,
                AVG(humidity) as avg_hum
            FROM sensor_logs 
            WHERE layer_id = 1
        """)
        stats = cursor.fetchone()
        print(f"\n   📈 統計情報:")
        print(f"      平均温度: {stats['avg_temp']:.1f}℃")
        print(f"      温度範囲: {stats['min_temp']:.1f}℃ 〜 {stats['max_temp']:.1f}℃")
        print(f"      平均湿度: {stats['avg_hum']:.1f}%")

if __name__ == '__main__':
    print("=" * 60)
    print("  🌱 Smart Grow System - テストデータ生成ツール")
    print("=" * 60)
    
    # テストデータ生成
    data_points = generate_sensor_test_data(days=30, interval_minutes=30, layer_id=1)
    
    # データベースに挿入
    insert_test_data(data_points)
    
    # 検証
    verify_data()
    
    print("\n" + "=" * 60)
    print("  ✅ 完了！データベースにテストデータが追加されました")
    print("=" * 60)


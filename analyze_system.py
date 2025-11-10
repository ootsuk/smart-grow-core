#!/usr/bin/env python3
"""
システムの現状を分析するスクリプト
"""
from database.db_manager import open_db

def analyze_system():
    """システムの現状を分析"""
    try:
        with open_db() as conn:
            cursor = conn.cursor()
            
            print("=" * 60)
            print("📊 Smart Grow System 現状分析")
            print("=" * 60)
            
            # 1. レイヤー情報
            print("\n【1. レイヤー情報】")
            cursor.execute("SELECT * FROM layers ORDER BY layer_id")
            layers = cursor.fetchall()
            print(f"レイヤー数: {len(layers)}件")
            print("\nID | Layer Name | Camera ID | Active")
            print("-" * 50)
            for layer in layers:
                active_str = "✓" if layer['is_active'] else "✗"
                print(f"{layer['layer_id']:2d} | {layer['layer_name']:10s} | {layer['cam_id']:9d} | {active_str}")
            
            # 2. スケジュール情報
            print("\n【2. スケジュール情報】")
            cursor.execute("SELECT * FROM schedules ORDER BY layer_id, job_type")
            schedules = cursor.fetchall()
            print(f"スケジュール数: {len(schedules)}件")
            print("\nID | Layer | Job Type | Exec Time | Enabled")
            print("-" * 50)
            for sched in schedules:
                enabled_str = "✓" if sched['is_enabled'] else "✗"
                job_icon = {'camera': '📷', 'sensor': '📊', 'water': '💧'}.get(sched['job_type'], '🔧')
                print(f"{sched['schedule_id']:2d} | {sched['layer_id']:5d} | {job_icon} {sched['job_type']:8s} | {sched['exec_time']:8s} | {enabled_str}")
            
            # 3. レイヤーごとのジョブ分析
            print("\n【3. レイヤーごとのジョブ分析】")
            for layer in layers:
                layer_id = layer['layer_id']
                layer_name = layer['layer_name']
                print(f"\n▶ Layer {layer_id} ({layer_name}):")
                
                cursor.execute("""
                    SELECT job_type, exec_time, is_enabled
                    FROM schedules
                    WHERE layer_id = ?
                    ORDER BY job_type
                """, (layer_id,))
                jobs = cursor.fetchall()
                
                if not jobs:
                    print("  ジョブなし")
                else:
                    for job in jobs:
                        enabled_str = "有効" if job['is_enabled'] else "無効"
                        job_icon = {'camera': '📷', 'sensor': '📊', 'water': '💧'}.get(job['job_type'], '🔧')
                        print(f"  {job_icon} {job['job_type']:8s} - {job['exec_time']} ({enabled_str})")
            
            # 4. Layer 0の特殊分析
            print("\n【4. Layer 0 (システム全体) の分析】")
            cursor.execute("""
                SELECT job_type, COUNT(*) as count
                FROM schedules
                WHERE layer_id = 0
                GROUP BY job_type
            """, )
            layer0_jobs = cursor.fetchall()
            
            if not layer0_jobs:
                print("⚠️  Layer 0にジョブがありません")
            else:
                for job in layer0_jobs:
                    job_icon = {'camera': '📷', 'sensor': '📊', 'water': '💧'}.get(job['job_type'], '🔧')
                    print(f"  {job_icon} {job['job_type']}: {job['count']}個")
            
            # 5. 各レイヤーのジョブ統計
            print("\n【5. レイヤー別ジョブ統計】")
            cursor.execute("""
                SELECT 
                    layer_id,
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN job_type = 'camera' THEN 1 ELSE 0 END) as camera_count,
                    SUM(CASE WHEN job_type = 'sensor' THEN 1 ELSE 0 END) as sensor_count,
                    SUM(CASE WHEN job_type = 'water' THEN 1 ELSE 0 END) as water_count
                FROM schedules
                GROUP BY layer_id
                ORDER BY layer_id
            """)
            stats = cursor.fetchall()
            
            print("\nLayer | Total | 📷 Camera | 📊 Sensor | 💧 Water")
            print("-" * 50)
            for stat in stats:
                print(f"{stat['layer_id']:5d} | {stat['total_jobs']:5d} | {stat['camera_count']:9d} | {stat['sensor_count']:9d} | {stat['water_count']:8d}")
            
            # 6. 問題点の指摘
            print("\n【6. ⚠️  検出された問題点】")
            issues = []
            
            # Layer 0にカメラジョブがあるか
            cursor.execute("SELECT COUNT(*) as count FROM schedules WHERE layer_id = 0 AND job_type = 'camera'")
            if cursor.fetchone()['count'] > 0:
                issues.append("❌ Layer 0 (システム全体) にカメラジョブがあります（不要）")
            
            # Layer 1以降に水やりジョブがあるか
            cursor.execute("SELECT COUNT(*) as count FROM schedules WHERE layer_id > 0 AND job_type = 'water'")
            water_in_layers = cursor.fetchone()['count']
            if water_in_layers > 0:
                issues.append(f"❌ Layer 1以降に水やりジョブが{water_in_layers}個あります（給水は上から下に循環するので不要）")
            
            # Layer 0に水やりジョブがあるか
            cursor.execute("SELECT COUNT(*) as count FROM schedules WHERE layer_id = 0 AND job_type = 'water'")
            if cursor.fetchone()['count'] == 0:
                issues.append("⚠️  Layer 0 (システム全体) に水やりジョブがありません（必要）")
            
            # 各レイヤーにカメラとセンサーがあるか
            for layer in layers:
                if layer['layer_id'] > 0:
                    cursor.execute("""
                        SELECT 
                            SUM(CASE WHEN job_type = 'camera' THEN 1 ELSE 0 END) as camera_count,
                            SUM(CASE WHEN job_type = 'sensor' THEN 1 ELSE 0 END) as sensor_count
                        FROM schedules
                        WHERE layer_id = ?
                    """, (layer['layer_id'],))
                    result = cursor.fetchone()
                    
                    if result['camera_count'] == 0:
                        issues.append(f"⚠️  Layer {layer['layer_id']} にカメラジョブがありません")
                    if result['sensor_count'] == 0:
                        issues.append(f"⚠️  Layer {layer['layer_id']} にセンサージョブがありません")
            
            if issues:
                for issue in issues:
                    print(f"  {issue}")
            else:
                print("  ✅ 問題は検出されませんでした")
            
            # 7. 推奨される設計
            print("\n【7. 推奨される設計】")
            print("\n▶ Layer 0 (システム全体):")
            print("  📊 sensor  - タンク圧力測定（給水タンク・排水タンク）")
            print("  💧 water   - 給水ポンプ起動（上から下へ循環）")
            print("\n▶ Layer 1, 2, 3... (各栽培層):")
            print("  📷 camera  - 豆苗の撮影")
            print("  📊 sensor  - 温度・湿度測定")
            print("  ❌ water   - 不要（水は上から自動で流れてくる）")
            
            print("\n" + "=" * 60)
                
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_system()


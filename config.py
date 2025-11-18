import os
from pathlib import Path
from dotenv import load_dotenv

# .env ファイルを読み込む
load_dotenv()

# プロジェクトのルートディレクトリを取得
PROJECT_ROOT = Path(__file__).parent.absolute()

# === DB設定 ===
# 絶対パスを使用（web_app/からアクセスしても正しく参照できる）
DB_PATH = os.getenv("DB_PATH", str(PROJECT_ROOT / "smart_grow_system.db"))

# === Slack通知設定 ===
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# === LLM関連設定 ===
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_NAME = "gpt-4-turbo"  # 固定値（必要に応じて .env 化可）

# === デフォルトシステム設定 ===
DEFAULT_SYSTEM_CONFIG = {
    "water_duration_sec": 10,
    "slack_webhook_url": SLACK_WEBHOOK_URL,
    "temp_high_threshold": 38.0,
    "temp_low_threshold": 10.0,
    "pump_gpio_sig": 17,
    "dashboard_url": "http://your.funnel.url/dashboard",
    "i2c_bus_num": 1,

    # 水圧関連
    "supply_low_threshold": 90.0,
    "drain_high_threshold": 150.0,
    "supply_pressure_gpio_sig": 26,
    "drain_pressure_gpio_sig": 27,

    # LLM関連
    "llm_model_name": LLM_MODEL_NAME,
}

# === 初期レイヤー設定 ===
DEFAULT_LAYERS = [
    (1, "1段目", 0, 1),
]

# === デフォルトスケジュール ===
# Layer 0: システム全体（温湿度センサー + タンク圧力測定 + 給水ポンプ）
# Layer 1以降: 各層ごとに（カメラのみ）
# 
# センサー設計：
# - 温度・湿度センサーはシステム全体で共通（Layer 0）
# - タンク圧力センサーもシステム全体で共通（Layer 0）
# - 各層は共通センサーの値を参照
# 
# 水循環の仕組み：
# - 給水ポンプで上から水を供給
# - 水が各層を上から下へ循環
# - 各層の横穴から次の層へ自動で流れる
# - 排水タンクに回収
DEFAULT_SCHEDULES = [
    (0, "sensor", "00:30:00", 1),  # システム全体: 温湿度 + タンク圧力測定（30分おき）
    (0, "water", "12:00:00", 1),   # システム全体: 給水ポンプ起動（毎日12時）
    (1, "camera", "09:00:00", 1),  # Layer 1: カメラ撮影（毎日9時）
]

# === カメラ設定 ===
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720
RETENTION_DAYS = 90
BASE_SAVE_DIR = str(PROJECT_ROOT / "plant_images")

# === AHT25 センサー設定 ===
AHT_ADDRESS = 0x38
AHT_TRIGGER_CMD = [0xAC, 0x33, 0x00]

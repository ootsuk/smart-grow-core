# smart-grow-core/web_app/routes/ui_routes.py
# 
# 注意: このファイルはrun_web.py（Blueprintベース）用のルートですが、
# 現在のプロジェクトではapp.py（スタンドアロン）を使用しています。
# app.pyに完全な実装があるため、このファイルは使用されていません。
# 
# TODO: 将来的にBlueprint構成に統一する場合は、app.pyのルートをこちらに移行してください。

from flask import Blueprint, render_template

ui_bp = Blueprint('ui_bp', __name__)

# プレースホルダールート（現在は使用されていません）
# 実際のルートはweb_app/app.pyにあります

@ui_bp.route('/')
@ui_bp.route('/dashboard')
def dashboard():
    """ダッシュボード画面（プレースホルダー）"""
    # 注意: 実際の実装はapp.pyにあります
    status_data = {"temp": 25.0, "pump_status": "ON"}
    return render_template('dashboard.html', data=status_data)

@ui_bp.route('/logs')
def logs():
    """ログ履歴画面（プレースホルダー）"""
    # 注意: 実際の実装はapp.pyにあります
    return render_template('logs.html', logs=[])
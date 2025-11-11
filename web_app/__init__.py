# smart-grow-core/web_app/__init__.py

from flask import Flask

# Blueprintをインポート
from .routes.ui_routes import ui_bp
from .routes.api_routes import api_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object('config') # config.pyの設定を読み込む
    
    # テンプレートと静的ファイルの場所を設定（web_appディレクトリ内を参照させる）
    app.template_folder = 'templates'
    app.static_folder = 'static'
    
    # ルーティングを登録
    # 注意: api_bpは自身で'/api'プレフィックスを持っているため、ここでは追加しない
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp)

    return app
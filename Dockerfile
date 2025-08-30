# Python公式イメージを使用
FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# 依存ライブラリをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# wait-for-it スクリプトをコピーして実行権限を付与
COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh

# アプリ本体、static、templatesをコピー
COPY . .

# Flask用環境変数
ENV FLASK_APP=onediary_app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# 起動コマンド
CMD ["flask", "run"]
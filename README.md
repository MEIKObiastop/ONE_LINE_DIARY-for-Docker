# 一行日記をDockerでコンテナ化【学習用】

以前作成した[ONE LINE DIARY](https://github.com/MEIKObiastop/ONE_LINE_DIARY)を、
あらゆる環境で動作確認できるようにコンテナ化しました。  
デプロイ版は[こちら](https://one-line-diary.onrender.com/login)

## 注意
- 開発用サーバーで動作しているだけで、本番用ではありません
- `SECRET_KEY` や `DATABASE_URL` は学習用で固定していますが、公開環境では変更してください

---

## 実行方法
### Docker Hub からイメージを取得
```bash
docker pull meikobaiastop/onediary_web:latest
```

### PostgreSQL コンテナ起動
```bash
docker run -d --name onediary_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=onediary \
  -p 5432:5432 postgres:15
```

### Web アプリ起動
```bash
docker run -d --name onediary_web \
  --link onediary_db:db \
  -e DATABASE_URL=postgresql://user:password@db:5432/onediary \
  -e SECRET_KEY=testsecret \
  -p 5000:5000 meikobaiastop/onediary_web:latest \
  ./wait-for-it.sh db:5432 -- flask run --host=0.0.0.0
```

### ブラウザで確認
[http://localhost:5000](http://localhost:5000)

### 削除
```bash
docker rm -f onediary_db onediary_web
docker volume rm postgres_data
```
**ボリューム削除は onediary に関係するものだけにしてください。他のボリュームを消さないよう注意。  
'docker volume rm $(docker volume ls -q)'などを使うのはNG**

---

## 使用技術
- **フロントエンド**: HTML, CSS
- **バックエンド**: Python (Flask + Jinja2 template)
- **データベース**: PostgreSQL (Render)
- **ライブラリ**: SQLAlchemy, pytz, csv
- **デプロイ**: Render

---

## 機能一覧
- ユーザー認証（ログイン / ログアウト / アカウント削除）
- 投稿・削除機能
- 投稿内容から絵文字を自動付与（csvファイル内のワードを参照）
- 直近20件の投稿内容から背景色を自動変更
- 日付を JST（日本時間）に変換して表示

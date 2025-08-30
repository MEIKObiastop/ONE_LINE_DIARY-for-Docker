from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
import csv
import os

# --- Flask アプリと DB の設定 ---
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://user:password@db:5432/onediary'
)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'testsecret')

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import inspect

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Flask-Login 設定 ---
login_manager = LoginManager()
login_manager.init_app(app)

def utc_now():
    return datetime.utcnow()

class Post(db.Model):
    __tablename__ = 'onediary_post' # テーブル名を指定
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=utc_now)
    
    user_id = db.Column(db.Integer, db.ForeignKey('onediary_user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))

    def __repr__(self):
        return f'<Post {self.id}>'

class User(UserMixin, db.Model):
    __tablename__ = 'onediary_user' # テーブル名を指定
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(128))


# --- 単語CSV読み込み ---
basedir = os.path.abspath(os.path.dirname(__file__))
word_dict = {}  # 単語とカテゴリーを格納する辞書
csv_path = os.path.join(basedir, 'data', 'feelings.csv')
with open(csv_path, encoding="utf-8-sig") as f:  # BOM対策で utf-8-sig
    reader = csv.DictReader(f)
    for row in reader:
        if not row["word"]:  # 空行ならスキップ
            continue
        word_dict[row["word"]] = row["category"]

# --- 背景色グラデーションカラー ---
colors = [
    "#D2D3F2","#DAE0F7","#E1E8F7","#E8EDF7","#E8F4F7",
    "#E8F7F5","#E8F7F1","#EBF7EE","#EDF7EB","#F1F7EE",
    "#F7F7F0",  # 中間値（ポジ・ネガ0.5付近）
    "#F7F5EA","#F7F0E8","#F7EBE2","#F7E8E1","#F7E4E1",
    "#F7DDDD","#FAD6D5","#FFD3D2","#FFCFCF","#FFCFCF"
]

# --- 感情分析 ---
def analyze_sentiment(text):
    pos_count = 0
    neg_count = 0
    for word,category in word_dict.items():
        if word in text:
            if category == 'positive':
                pos_count += 1
            else:
                neg_count += 1
    total = pos_count + neg_count
    if total == 0:
        return 0.5  # 中立  （辞書にない単語のみの場合）
    return pos_count / total  # ポジティブ度を返す

# 感情分析を21ランクの整数に変換
def sentiment_to_rank(pos_ratio):
    return int(pos_ratio * 20)

# 感情ランクに対して色を取得
def get_color_for_sentiment(rank):
    return colors[rank]


# --- 絵文字解析 ---
def analyze_emoji(text: str) -> str:
    score = 0
    for word, category in word_dict.items():
        if word in text:
            score += 1 if category == "positive" else -1

    if score > 0:
        return "\u2600"  # ☀️ ポジティブ
    elif score < 0:
        return "\u2602"  # ☂️ ネガティブ
    else:
        return "\u2601"  # ☁️ ニュートラル


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_background_color():
    if not current_user.is_authenticated:
        return dict(background_color="#F7F7F0")

    # ユーザーの直近20件を取得
    recent_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.date_created.desc()).limit(20).all()
    ratios = [analyze_sentiment(p.content) for p in recent_posts]

    # 投稿が20件に満たない場合は、中立0.5で補完
    remaining = 20 - len(ratios)
    if remaining > 0:
        ratios.extend([0.5] * remaining)

    # 平均を計算して色を決定
    avg_ratio = sum(ratios) / len(ratios)
    overall_color = get_color_for_sentiment(sentiment_to_rank(avg_ratio))

    return dict(background_color=overall_color)

with app.app_context():
    inspector = inspect(db.engine)
    if "onediary_user" not in inspector.get_table_names():
        print(">>> Creating tables...")
        db.create_all()
        print(">>> Done creating tables!")

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    
    # 全件取得（新しい順）
    all_posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.date_created.desc()).all()
    
    # --- 絵文字用 ---
    posts_with_emoji = []
    for post in all_posts:
        emoji = analyze_emoji(post.content)
        jst_date = post.date_created.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Tokyo'))
        posts_with_emoji.append({
            "content": post.content,
            "date": jst_date,
            "emoji": emoji
        })


    return render_template(
        'index.html',
        posts_all=posts_with_emoji,
    )


@app.route('/newuser', methods=['GET', 'POST'])
def newuser():
    default_color = "#F7F7F0"
    error_message = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username:
            error_message = "ユーザー名を入力してください"
        elif not password:
            error_message = "パスワードを入力してください"
        elif User.query.filter_by(username=username).first():
            error_message = "すでに登録されているユーザー名です"
        else:
            user = User(
                username=username, 
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            db.session.add(user)
            db.session.commit()
            return render_template('login.html', background_color=default_color)

    return render_template('newuser.html', background_color=default_color, error=error_message)



@app.route('/login', methods=['GET', 'POST'])
def login():
    default_color = "#F7F7F0"
    error_message = None  # 初期値

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # ユーザーが存在しないかパスワードが間違っている場合
        if not user or not check_password_hash(user.password, password):
            error_message = "ユーザー名かパスワードが間違っています"
        else:
            login_user(user)
            return redirect(url_for('index'))

    return render_template('login.html', background_color=default_color, error=error_message)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


@app.route('/posts',methods=['POST'])
@login_required
def posts():
    content = request.form['diary_entry']
    new_post = Post(content=content, date_created=utc_now(), user_id=current_user.id)
    db.session.add(new_post)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/edit')
@login_required
def edit():
    posts_all = Post.query.filter_by(user_id=current_user.id).order_by(Post.date_created.desc()).all()
    return render_template('edit.html', posts_all=posts_all)


@app.route('/delete/<int:post_id>', methods=['GET'])
@login_required
def delete(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        return redirect(url_for('edit'))
    
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('edit'))




# ユーザー削除確認画面
@app.route('/user_delete_confirm')
@login_required
def user_delete_confirm():
    return render_template('user_delete_confirm.html')

# 実際に削除するルート
@app.route('/user_delete', methods=['POST'])
@login_required
def user_delete():
    user = current_user
    
    # このユーザーの全投稿を削除
    Post.query.filter_by(user_id=user.id).delete()
    
    # ユーザー自身を削除
    db.session.delete(user)
    db.session.commit()
    
    flash("アカウントと投稿がすべて削除されました。")

    return redirect(url_for('login'))

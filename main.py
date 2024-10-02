from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['MAIL_SERVER'] = 'smtp.gmail.com' 
app.config['MAIL_PORT'] = 587  
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Thay bằng email Gmail của bạn
app.config['MAIL_PASSWORD'] = 'your_app_password'  # Thay bằng App Password của bạn

socketio = SocketIO(app)
db = SQLAlchemy(app)
mail = Mail(app)
ts = URLSafeTimedSerializer(app.config["SECRET_KEY"])

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            return 'Tên người dùng đã tồn tại!'
        user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('chat'))
        else:
            return 'Sai tên đăng nhập hoặc mật khẩu!'
    return render_template('login.html')

@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('chat.html', username=user.username)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = ts.dumps(user.email, salt='recover-key')
            recover_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Yêu cầu đặt lại mật khẩu', 
                          sender=app.config['MAIL_USERNAME'], 
                          recipients=[email])
            msg.body = f'''Xin chào {user.username},

Bạn đã yêu cầu đặt lại mật khẩu. Vui lòng nhấp vào liên kết sau:

{recover_url}

Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này.

Trân trọng,
Đội ngũ Live Chat
'''
            mail.send(msg)
            return 'Chúng tôi đã gửi email hướng dẫn đặt lại mật khẩu.'
        else:
            return 'Email không tồn tại!'
    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = ts.loads(token, salt='recover-key', max_age=3600)
    except SignatureExpired:
        return 'Liên kết đặt lại mật khẩu đã hết hạn!'
    user = User.query.filter_by(email=email).first_or_404()
    if request.method == 'POST':
        new_password = request.form['password']
        user.password = generate_password_hash(new_password)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    emit('status', {'msg': username + ' đã tham gia phòng chat.'}, room=room)

@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    emit('status', {'msg': username + ' đã rời khỏi phòng chat.'}, room=room)

@socketio.on('message')
def handle_message(data):
    username = data['username']
    room = data['room']
    msg = data['msg']
    emit('message', {'username': username, 'msg': msg}, room=room)

if __name__ == '__main__':
    socketio.run(app, debug=True)
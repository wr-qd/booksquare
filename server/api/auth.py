from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
from flask_mail import Message
import jwt

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# 延迟导入，避免循环依赖
def get_dependencies():
    from extensions import db, mail
    from models.user import User, EmailVerification
    from config import Config
    return db, mail, User, EmailVerification, Config

@auth_bp.route('/send-verification-code', methods=['POST'])
def send_verification_code():
    """发送邮箱验证码"""
    db, mail, User, EmailVerification, Config = get_dependencies()
    
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    
    if not email:
        return jsonify({'error': '邮箱不能为空'}), 400
    
    # 检查邮箱是否已注册
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '该邮箱已被注册'}), 400
    
    # 生成验证码
    code = EmailVerification.generate_code()
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # 保存验证码
    verification = EmailVerification(
        email=email,
        code=code,
        expires_at=expires_at
    )
    db.session.add(verification)
    db.session.commit()
    
    cfg = current_app.config
    sender = cfg.get('MAIL_DEFAULT_SENDER') or cfg.get('MAIL_USERNAME')
    username = cfg.get('MAIL_USERNAME')
    password = cfg.get('MAIL_PASSWORD')

    # 如果没有配置邮箱，开发环境返回验证码直接给前端，避免阻塞
    if not sender or not username or not password:
        current_app.logger.warning('MAIL 未配置，返回验证码给前端用于开发调试')
        return jsonify({
            'message': '开发环境未配置邮箱，验证码直接返回',
            'code': code,
            'expires_in': 600
        }), 200

    # 发送邮件
    try:
        msg = Message(
            '书籍评论系统 - 邮箱验证码',
            sender=sender,
            recipients=[email]
        )
        msg.body = f'''
您好！

您的验证码是: {code}

此验证码将在10分钟后失效。

如果这不是您的操作，请忽略此邮件。

书籍评论系统团队
'''
        mail.send(msg)
        
        return jsonify({
            'message': '验证码已发送到您的邮箱',
            'expires_in': 600  # 10分钟
        }), 200
    except Exception as e:
        current_app.logger.error(f'发送邮件失败: {e}')
        return jsonify({'error': f'发送邮件失败: {str(e)}'}), 500


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    db, _, User, EmailVerification, _ = get_dependencies()
    
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    
    # 验证必填字段
    if not all([email, username, password]):
        return jsonify({'error': '邮箱、用户名、密码均不能为空'}), 400
    
    # 检查用户名和邮箱是否已存在
    if User.query.filter_by(email=email).first():
        return jsonify({'error': '该邮箱已被注册'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': '该用户名已被使用'}), 400
    
    # 创建用户（简化：无需邮箱验证码）
    user = User(email=email, username=username, is_verified=True)
    user.set_password(password)
    
    db.session.add(user)
    db.session.commit()
    
    # 生成token
    token = generate_token(user.id)
    
    return jsonify({
        'message': '注册成功',
        'token': token,
        'user': user.to_dict()
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    from models.user import User
    
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    password = data.get('password')
    
    if not all([email, password]):
        return jsonify({'error': '邮箱和密码不能为空'}), 400
    
    # 查找用户
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': '邮箱不存在'}), 401

    if not user.check_password(password):
        return jsonify({'error': '密码错误'}), 401
    
    # 生成token
    token = generate_token(user.id)
    
    return jsonify({
        'message': '登录成功',
        'token': token,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """验证token"""
    from models.user import User
    
    data = request.get_json(silent=True) or {}
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Token不能为空'}), 400
    
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        return jsonify({
            'valid': True,
            'user': user.to_dict()
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token已过期'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Token无效'}), 401


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """获取用户信息（需要token）"""
    from models.user import User
    
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not token:
        return jsonify({'error': '未授权'}), 401
    
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': '用户不存在'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
    except:
        return jsonify({'error': 'Token无效'}), 401


def generate_token(user_id):
    """生成JWT token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

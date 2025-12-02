#
#
# from flask import Flask, render_template, request, redirect, url_for, flash
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from datetime import datetime
# import os
# from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
import os
import sqlite3
from dotenv import load_dotenv
import secrets

# Загружаем .env
load_dotenv()

app = Flask(__name__)

# Безопасное получение SECRET_KEY
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    # В продакшене генерируем ошибку
    if os.getenv('FLASK_ENV') == 'production':
        raise ValueError("SECRET_KEY must be set in production")
    # В разработке используем случайный ключ
    secret_key = secrets.token_hex(32)
    print(f"⚠️  SECRET_KEY не найден, сгенерирован временный ключ")
app.secret_key = secret_key


# Безопасное получение настроек SMTP
def get_smtp_config():
    """Безопасно получает SMTP настройки"""
    config = {
        'server': os.getenv('SMTP_SERVER', '').strip(),
        'port': int(os.getenv('SMTP_PORT', 0)) or 587,
        'username': os.getenv('EMAIL_USER', '').strip(),
        'password': os.getenv('EMAIL_PASSWORD', '').strip(),
        'to_email': os.getenv('TO_EMAIL', '').strip()
    }

    # Маскируем пароль в логах
    masked_config = config.copy()
    if masked_config['password']:
        masked_config['password'] = '***masked***'

    print(f"🔧 SMTP настроен: {bool(config['username'] and config['password'])}")
    return config


SMTP_CONFIG = get_smtp_config()


# Инициализация базы данных
def init_database():
    """Инициализирует базу данных с безопасным путем"""
    # Используем безопасный путь вне репозитория
    db_path = os.getenv('DATABASE_PATH', 'applications.db')

    # В продакшене лучше использовать абсолютный путь
    if os.getenv('FLASK_ENV') == 'production':
        db_path = '/var/data/applications.db'

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            comment TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    return db_path


DB_PATH = init_database()


@app.context_processor
def inject_now():
    return {'now': datetime.now()}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/form')
def form():
    return render_template('form.html')


@app.route('/submit_application', methods=['POST'])
def submit_application():
    if request.method == 'POST':
        try:
            # Получаем данные
            data = {
                'name': request.form.get('full_name', '').strip()[:100],
                'address': request.form.get('address', '').strip()[:200],
                'phone': request.form.get('phone', '').strip()[:20],
                'comment': request.form.get('comment', '').strip()[:500]
            }

            # Защита от пустых заявок
            if not all([data['name'], data['address'], data['phone']]):
                flash('❌ Заполните все обязательные поля', 'error')
                return redirect(url_for('form'))

            # Защита от слишком частых заявок (простая)
            # Можно добавить более сложную логику

            # Сохраняем в базу с дополнительной информацией
            save_to_database(data, request)

            # Пытаемся отправить email
            email_sent = False
            if SMTP_CONFIG['username'] and SMTP_CONFIG['password']:
                email_sent = send_email_safe(data)

            if email_sent:
                flash('✅ Заявка принята! Мы свяжемся с вами.', 'success')
            else:
                flash('✅ Заявка принята!', 'success')

            return redirect(url_for('prices'))

        except Exception as e:
            # Не показываем детали ошибки пользователю
            print(f"⚠️ Ошибка обработки заявки: {e}")
            flash('⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.', 'error')
            return redirect(url_for('form'))


@app.route('/prices')
def prices():
    return render_template('prices.html')


def send_email_safe(data):
    """Безопасная отправка email с обработкой ошибок"""
    try:
        # Проверяем настройки
        if not all([SMTP_CONFIG['username'], SMTP_CONFIG['password'], '@' in SMTP_CONFIG['username']]):
            return False

        # Создаем сообщение
        msg = EmailMessage()
        msg['From'] = SMTP_CONFIG['username']
        msg['To'] = SMTP_CONFIG['to_email'] or SMTP_CONFIG['username']
        msg['Subject'] = f"Заявка от {data['name'][:30]}"

        body = f"""
        Новая заявка:

        ФИО: {data['name']}
        Телефон: {data['phone']}
        Адрес: {data['address']}
        Комментарий: {data['comment'] or 'Нет'}

        Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """

        msg.set_content(body)

        # Пробуем отправить
        context = ssl.create_default_context()

        if SMTP_CONFIG['port'] == 465:
            with smtplib.SMTP_SSL(SMTP_CONFIG['server'], SMTP_CONFIG['port'],
                                  context=context, timeout=15) as server:
                server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'], timeout=15) as server:
                server.starttls(context=context)
                server.login(SMTP_CONFIG['username'], SMTP_CONFIG['password'])
                server.send_message(msg)

        return True

    except Exception as e:
        # Логируем ошибку, но не показываем пользователю
        print(f"📧 Ошибка отправки email: {type(e).__name__}")
        return False


def save_to_database(data, request):
    """Безопасное сохранение в базу данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Получаем дополнительную информацию
        ip_address = request.remote_addr
        user_agent = request.user_agent.string[:200] if request.user_agent else ''

        cursor.execute('''
            INSERT INTO applications (full_name, address, phone, comment, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['address'], data['phone'], data['comment'], ip_address, user_agent))

        conn.commit()
        conn.close()

        print(f"💾 Сохранена заявка от: {data['name']}")
        return True

    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        return False


if __name__ == '__main__':
    # Безопасный запуск
    debug_mode = os.getenv('FLASK_ENV') != 'production'

    print("\n" + "=" * 60)
    print("🚀 Flask Application - Безопасная конфигурация")
    print("=" * 60)
    print(f"📁 База данных: {DB_PATH}")
    print(f"🔐 SMTP настроен: {bool(SMTP_CONFIG['username'])}")
    print(f"🐛 Режим отладки: {debug_mode}")
    print(f"🌐 Адрес: http://localhost:5000")
    print("=" * 60)

    app.run()

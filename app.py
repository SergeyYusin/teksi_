from flask import Flask, render_template, request, redirect, url_for, flash
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime
import os
import sqlite3
import json  # ДОБАВИТЬ ЭТОТ ИМПОРТ!
import secrets
from dotenv import load_dotenv

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


# Инициализация базы данных (ОБНОВЛЕННАЯ!)
def init_database():
    """Инициализирует базу данных с полями для работ"""
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
            selected_works TEXT,  -- JSON с выбранными работами
            total_amount REAL,    -- Общая стоимость
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


# ОБНОВЛЕННАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ ФОРМЫ С РАСЧЕТОМ
@app.route('/submit_application', methods=['POST'])
def submit_application():
    if request.method == 'POST':
        try:
            # Основные данные
            data = {
                'name': request.form.get('full_name', '').strip()[:100],
                'address': request.form.get('address', '').strip()[:200],
                'phone': request.form.get('phone', '').strip()[:20],
                'comment': request.form.get('comment', '').strip()[:500]
            }

            # Данные о работах (НОВОЕ!)
            selected_works_json = request.form.get('selected_works_json', '[]')
            total_amount = request.form.get('total_amount', '0')

            try:
                selected_works = json.loads(selected_works_json)
            except:
                selected_works = []

            # Валидация
            if not all([data['name'], data['address'], data['phone']]):
                flash('❌ Заполните все обязательные поля', 'error')
                return redirect(url_for('form'))

            if not selected_works:
                flash('❌ Выберите хотя бы один вид работ', 'error')
                return redirect(url_for('form'))

            # Сохраняем в базу с данными о работах
            save_to_database(data, request, selected_works, total_amount)

            # Пытаемся отправить email с деталями работ
            email_sent = False
            if SMTP_CONFIG['username'] and SMTP_CONFIG['password']:
                email_sent = send_email_with_works(data, selected_works, total_amount)

            if email_sent:
                flash(f'✅ Заявка отправлена! Примерная стоимость: {int(float(total_amount)):,} ₽', 'success')
            else:
                flash(f'✅ Заявка сохранена! Примерная стоимость: {int(float(total_amount)):,} ₽', 'info')

            return redirect(url_for('prices'))

        except Exception as e:
            print(f"⚠️ Ошибка обработки заявки: {e}")
            flash('⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.', 'error')
            return redirect(url_for('form'))


@app.route('/prices')
def prices():
    return render_template('prices.html')


# НОВАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ EMAIL С РАБОТАМИ
def send_email_with_works(data, selected_works, total_amount):
    """Отправка email с детализацией работ"""
    try:
        # Проверяем настройки
        if not all([SMTP_CONFIG['username'], SMTP_CONFIG['password'], '@' in SMTP_CONFIG['username']]):
            return False

        # Создаем сообщение
        msg = EmailMessage()
        msg['From'] = SMTP_CONFIG['username']
        msg['To'] = SMTP_CONFIG['to_email'] or SMTP_CONFIG['username']
        msg['Subject'] = f"Заявка с расчетом от {data['name'][:30]}"

        # Формируем детализацию работ
        works_details = "Выбранные работы:\n"
        works_details += "=" * 40 + "\n"
        for work in selected_works:
            works_details += f"• {work['type']}\n"
            works_details += f"  Количество: {work['quantity']} {work['unit']}\n"
            works_details += f"  Цена за единицу: {work['price']:,} ₽\n"
            works_details += f"  Стоимость: {work['cost']:,} ₽\n"
            works_details += "-" * 30 + "\n"

        works_details += f"\nОбщая стоимость: {int(float(total_amount)):,} ₽\n"
        works_details += "=" * 40 + "\n\n"

        body = f"""
        Новая заявка с расчетом стоимости:

        👤 КОНТАКТНАЯ ИНФОРМАЦИЯ:
        ФИО: {data['name']}
        Телефон: {data['phone']}
        Адрес: {data['address']}

        💰 РАСЧЕТ СТОИМОСТИ:
        {works_details}

        💬 КОММЕНТАРИЙ:
        {data['comment'] or 'Нет комментария'}

        ⏰ ВРЕМЯ ЗАЯВКИ:
        {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """

        msg.set_content(body)

        # Отправка
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
        print(f"📧 Ошибка отправки email: {type(e).__name__}")
        return False


# ОБНОВЛЕННАЯ ФУНКЦИЯ СОХРАНЕНИЯ В БАЗУ
def save_to_database(data, request, selected_works, total_amount):
    """Сохраняет заявку в базу данных с работами"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Получаем дополнительную информацию
        ip_address = request.remote_addr
        user_agent = request.user_agent.string[:200] if request.user_agent else ''

        # Преобразуем работы в JSON
        works_json = json.dumps(selected_works, ensure_ascii=False)

        cursor.execute('''
            INSERT INTO applications (full_name, address, phone, comment, 
                                     ip_address, user_agent, selected_works, total_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['address'], data['phone'], data['comment'],
              ip_address, user_agent, works_json, total_amount))

        conn.commit()
        conn.close()

        print(f"💾 Сохранена заявка с расчетом от: {data['name']} ({total_amount} ₽)")
        return True

    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
        return False


if __name__ == '__main__':
    # Безопасный запуск
    debug_mode = os.getenv('FLASK_ENV') != 'production'

    print("\n" + "=" * 60)
    print("🚀 Flask Application - Форма с расчетом стоимости")
    print("=" * 60)
    print(f"📁 База данных: {DB_PATH}")
    print(f"🔐 SMTP настроен: {bool(SMTP_CONFIG['username'])}")
    print(f"🐛 Режим отладки: {debug_mode}")
    print(f"🌐 Адрес: http://localhost:5000")
    print("=" * 60)

    app.run(
        debug=debug_mode,
        host=os.getenv('FLASK_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_PORT', 5000))
    )


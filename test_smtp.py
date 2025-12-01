import smtplib
import ssl
from email.message import EmailMessage
import os
from dotenv import load_dotenv

load_dotenv()


def test_yandex_smtp():
    """Тестирует подключение к Яндекс SMTP"""

    email = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASSWORD')

    print(f"\n🔍 Тестируем Яндекс SMTP...")
    print(f"   Email: {email}")
    print(f"   Пароль: {'*' * len(password) if password else 'НЕ ЗАДАН'}")

    if not email or not password:
        print("❌ Настройки не указаны в .env файле")
        return False

    # Пробуем порт 587
    try:
        print("\n🔄 Пробуем порт 587 (STARTTLS)...")
        with smtplib.SMTP('smtp.yandex.ru', 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(email, password)
            print("✅ Порт 587 работает!")
            return True
    except Exception as e:
        print(f"❌ Порт 587: {e}")

    # Пробуем порт 465
    try:
        print("\n🔄 Пробуем порт 465 (SSL)...")
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.yandex.ru', 465, context=context, timeout=10) as server:
            server.login(email, password)
            print("✅ Порт 465 работает!")
            return True
    except Exception as e:
        print(f"❌ Порт 465: {e}")

    return False


if __name__ == '__main__':
    if test_yandex_smtp():
        print("\n🎉 SMTP подключение работает!")
    else:
        print("\n⚠️  SMTP не работает. Проверьте:")
        print("   1. Пароль приложения в Яндекс")
        print("   2. Разрешения в настройках Яндекс.Почты")
        print("   3. Брандмауэр Windows (попробуйте отключить временно)")
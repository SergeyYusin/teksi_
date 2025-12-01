#!/usr/bin/env python3
"""Проверяет безопасность перед коммитом"""

import os
import sys


def check_secrets():
    """Проверяет, нет ли секретов в репозитории"""

    # Исключаем текущий файл из проверки
    current_file = os.path.abspath(__file__)

    sensitive_files = [
        '.env',
        '.env.local',
        '.env.production',
        'config.json',
        'secrets.json',
        'credentials.json',
        'applications.db',
        'instance/',
        'venv/'
    ]

    # Паттерны, которые НЕ должны быть в коде
    sensitive_patterns = [
        r'SECRET_KEY\s*=',
        r'PASSWORD\s*=',
        r'API_KEY\s*=',
        r'DATABASE_URL\s*=',
        r'AWS_ACCESS_KEY\s*=',
        r'email\s*=\s*["\'].*@.*["\']',  # email в коде
        r'passwd\s*=',
        r'token\s*='
    ]

    # Паттерны, которые могут быть в тестовых файлах/документации
    safe_patterns_in_docs = [
        r'SECRET_KEY=ваш-секретный-ключ',
        r'PASSWORD=пароль-приложения',
        r'EMAIL_USER=ваш-email@',
        r'#.*SECRET_KEY',
        r'#.*PASSWORD',
        r'# Пример:',
        r'\.env\.example'
    ]

    print("🔍 Проверка безопасности репозитория...")
    print("=" * 60)

    issues_found = []

    # 1. Проверяем наличие чувствительных файлов
    print("\n📁 Проверка файлов:")
    for file in sensitive_files:
        if os.path.exists(file):
            if os.path.isdir(file):
                print(f"   ⚠️  Обнаружена папка: {file}/")
                issues_found.append(f"Папка {file}/")
            else:
                print(f"   ❌ Обнаружен чувствительный файл: {file}")
                issues_found.append(f"Файл {file}")

    # 2. Проверяем .py файлы на наличие секретов
    print("\n🐍 Проверка Python файлов:")

    for root, dirs, files in os.walk('.'):
        # Исключаем системные папки
        exclude_dirs = ['.git', '__pycache__', 'venv', '.vscode', '.idea']
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            if file.endswith('.py'):
                filepath = os.path.abspath(os.path.join(root, file))

                # Пропускаем текущий файл
                if filepath == current_file:
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')

                        for line_num, line in enumerate(lines, 1):
                            line_lower = line.lower()

                            # Проверяем на опасные паттерны
                            is_dangerous = False
                            for pattern in sensitive_patterns:
                                import re
                                if re.search(pattern, line, re.IGNORECASE):
                                    # Но проверяем, не безопасный ли это паттерн
                                    is_safe = False
                                    for safe_pattern in safe_patterns_in_docs:
                                        if re.search(safe_pattern, line):
                                            is_safe = True
                                            break

                                    if not is_safe:
                                        is_dangerous = True
                                        break

                            if is_dangerous and ('example' not in line_lower and
                                                 'пример' not in line_lower and
                                                 'ваш-' not in line_lower):
                                rel_path = os.path.relpath(filepath)
                                print(f"   ⚠️  {rel_path}:{line_num} - возможный секрет")
                                issues_found.append(f"Потенциальный секрет в {rel_path}:{line_num}")

                except Exception as e:
                    print(f"   ⚠️  Не удалось прочитать {filepath}: {e}")

    # 3. Проверяем .env файлы
    print("\n🔐 Проверка .env файлов:")
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.startswith('.env') and not file.endswith('.example'):
                filepath = os.path.join(root, file)
                if os.path.exists(filepath):
                    print(f"   ❌ Обнаружен файл окружения: {filepath}")
                    issues_found.append(f"Файл окружения {filepath}")

    # 4. Вывод результатов
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")

    if not issues_found:
        print("✅ Все проверки пройдены успешно!")
        print("   Репозиторий безопасен для публикации.")
        return True
    else:
        print(f"⚠️  Найдено проблем: {len(issues_found)}")
        for issue in issues_found[:5]:  # Показываем только первые 5
            print(f"   • {issue}")

        if len(issues_found) > 5:
            print(f"   ... и еще {len(issues_found) - 5} проблем")

        print("\n🔧 РЕКОМЕНДАЦИИ:")
        print("1. Убедитесь, что файл .env добавлен в .gitignore")
        print("2. Удалите реальные секреты из кода")
        print("3. Используйте .env.example для примеров конфигурации")
        print("4. Запустите: git status - для проверки что коммитится")

        return False


if __name__ == '__main__':
    print("=" * 60)
    print("🔒 ПРОВЕРКА БЕЗОПАСНОСТИ GIT РЕПОЗИТОРИЯ")
    print("=" * 60)

    try:
        # Проверяем, что мы в git репозитории
        git_dir = os.path.join('.git')
        if not os.path.exists(git_dir):
            print("⚠️  Текущая папка не является git репозиторием")
            print("   Инициализируйте git: git init")
            sys.exit(1)

        if check_secrets():
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n❌ Проверка прервана пользователем")
        sys.exit(1)
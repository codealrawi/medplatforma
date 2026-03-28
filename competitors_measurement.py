"""
Скрипт измерения времени отклика конкурирующих платформ
Источник данных для сравнительной таблицы диссертации

Инструкция:
1. Открыть https://www.webpagetest.org
2. Для каждого сайта — ввести URL, выбрать локацию "Moscow, Russia"
3. Запустить тест, сохранить PDF-отчёт и скриншот
4. Записать TTFB (Time To First Byte) и Load Time

Альтернатива — измерить вручную через браузер:
1. Открыть DevTools (F12)
2. Вкладка Network → очистить → обновить страницу (Ctrl+Shift+R)
3. Посмотреть нижнюю строку: "Finish: X.XX s, DOMContentLoaded: X.XX s"
4. Записать время и сделать скриншот с адресной строкой + датой

ПЛАТФОРМЫ ДЛЯ ИЗМЕРЕНИЯ:
"""

platforms = {
    "PatientsLikeMe":   "https://www.patientslikeme.com",
    "ПроДокторов":      "https://prodoctorov.ru",
    "СпросиВрача":      "https://sprosivracha.com",
    "DonorSearch":      "https://donorsearch.org",
    "Здоровье Mail.ru": "https://health.mail.ru",
}

print("=" * 65)
print("ИНСТРУКЦИЯ: Измерение времени отклика конкурентов")
print("=" * 65)
print()
print("Шаг 1. Откройте https://www.webpagetest.org")
print()
for name, url in platforms.items():
    print(f"  • {name}")
    print(f"    URL: {url}")
    print(f"    Настройки: Location = Moscow, Russia")
    print(f"               Connection = Cable")
    print(f"               Runs = 3 (среднее из трёх)")
    print()

print("Шаг 2. Для каждого сайта сохраните:")
print("  - TTFB (Time To First Byte) — первый байт")
print("  - Fully Loaded Time — полная загрузка")
print("  - Скриншот отчёта с датой")
print()
print("Шаг 3. Занесите данные в таблицу:")
print()
print(f"{'Платформа':<22} {'TTFB мс':>10} {'Load Time мс':>14} {'Источник':>30}")
print("-" * 80)
for name in platforms:
    print(f"{name:<22} {'[измерить]':>10} {'[измерить]':>14} {'WebPageTest.org, март 2026':>30}")

print()
print("Шаг 4. Формулировка для диссертации:")
print("""
  «По данным инструмента WebPageTest.org (тестирование
  выполнено автором в марте 2026 г., сервер измерения —
  Москва, подключение Cable, 3 прогона), среднее время
  загрузки главной страницы составило: ...»
""")

print("=" * 65)
print("ПОИСК SUS-ОЦЕНОК В НАУЧНЫХ СТАТЬЯХ")
print("=" * 65)
print()
queries = [
    ('Google Scholar', '"PatientsLikeMe" usability evaluation SUS score'),
    ('Google Scholar', '"prodoctorov" OR "ПроДокторов" usability'),
    ('Google Scholar', 'medical Q&A platform usability system usability scale'),
    ('Google Scholar', 'telemedicine platform SUS evaluation Russia'),
    ('eLibrary.ru',    'медицинская платформа юзабилити оценка пользователей'),
    ('CyberLeninka',   'веб-система здравоохранение удовлетворённость пользователей'),
]
for db, q in queries:
    print(f"  [{db}]")
    print(f"  Запрос: {q}")
    print()

print("Если статьи не найдены — проведите собственный мини-опрос:")
print("  • 10 участников (студенты/знакомые, 5+ — пользователи мед. сайтов)")
print("  • 10 вопросов стандартной SUS-анкеты (есть в открытом доступе)")
print("  • Подсчёт: сумма × 2.5 = итоговый балл (0–100)")
print("  • Ссылка: Brooke J. (1996) SUS: A quick and dirty usability scale")

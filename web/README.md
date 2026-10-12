# TOIIM

Веб-платформа для организации свадеб, тоев и юбилеев в Казахстане: площадки, ведущие, музыка, фото и видео, калькулятор бюджета и Telegram-бот [@toi3_bot](https://t.me/toi3_bot).

## Технологии

Python, Django 5.2, Django REST Framework, PostgreSQL, иконки Lucide.

## Запуск

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Откройте http://127.0.0.1:8000/

Демо-данные помечены «(демо)»: это вымышленные компании для показа.

## Команда

- **Рыскали Диас**: тимлид, разработчик сайта
- **Нуркенулы Рауан**: Telegram-бот @toi3_bot
- **Мамаев Мейржан**: продукт, контент, тестирование, питч

## Деплой

Живая ссылка: https://toiim.onrender.com
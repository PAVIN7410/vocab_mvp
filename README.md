# 📚 Vocab MVP: Smart Flashcards Bot & Web App

MVP-проект для изучения иностранных слов методом интервальных повторений (Spaced Repetition). Система включает в себя Django-сайт для управления словарем и Telegram-бота для тренировок.

## ✨ Основные функции

*   **Автоматический перевод**: При добавлении слова система сама находит перевод (интеграция с `deep-translator`).
*   **Генерация карточек**: Для каждого слова создается карточка с уровнем сложности.
*   **Визуализация**: Автоматическая генерация ассоциативных картинок через AI (`Pollinations.ai`).
*   **Озвучка**: Прослушивание произношения как на сайте, так и в боте (используется `gTTS`).
*   **Интервальные повторения**: Умный алгоритм планирования тренировок (алгоритм на базе SM-2).
*   **Telegram-интерфейс**: Удобный квиз в боте с кнопками озвучки и статистикой.

## 🛠 Технологии

*   **Backend**: Python 3.10+, Django 5.x
*   **Database**: SQLite (стандарт для MVP)
*   **Bot Framework**: Aiogram 3.x
*   **Translation**: Deep Translator (Google API)
*   **Speech**: gTTS (Google Text-to-Speech)
*   **AI Images**: Pollinations AI

## 🚀 Быстрый запуск

### 1. Клонирование и установка
```bash
git clone <your-repo-url>
cd vocab_mvp
python -m venv venv
source venv/bin/activate  # Для Windows: venv\Scripts\activate
pip install -r requirements.txt
Используйте код с осторожностью.
pip install --upgrade pip setuptools wheel


2. Настройка окружения
Создайте файл .env в корне проекта и добавьте ваши ключи:
BOT_TOKEN=your_token_here
DEBUG=True
Используйте код с осторожностью.

3. База данных
bash
python manage.py makemigrations
python manage.py migrate
Используйте код с осторожностью.

4. Создай супер пользователя
python manage.py createsuperuser
пароль будет невидимый

5. Запуск проекта
Запуск веб-панели:
bash
python manage.py runserver
Используйте код с осторожностью.

6.Запуск Telegram-бота (в отдельном терминале):
bash
python bot/telegram_bot.py
Используйте код с осторожностью.

📸 Генерация картинок
Система автоматически пытается создать картинку при добавлении нового слова. Если картинка не создалась (например, из-за сетевой ошибки), слово всё равно сохранится, а вместо картинки будет использоваться текстовая карточка.
📝 Лицензия
MIT

Чтобы открывались все страницы надо перейти в бота: 💬 Telegram бот и в меню выбрать "Start"

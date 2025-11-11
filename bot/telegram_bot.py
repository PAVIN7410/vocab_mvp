#### vocab_mvp/bot/telegram_bot.py

import asyncio
import os
import random

import django
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from dotenv import load_dotenv
from googletrans import Translator

# Загружаем .env
load_dotenv()

# Добавляем корневую директорию проекта в PYTHONPATH
import sys
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__) + os.sep + "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Указываем Django, где искать настройки
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vocab.settings")
django.setup()
from django.utils import timezone

# Импортируем модели
# Импортируем модуль распознавания речи

from vocab.models import TelegramUser, Card, Repetition
from words.models import Word

# Импортируем утилиты
from bot.voice import synthesize_text_to_mp3
from bot.speech_recognition_helper import recognize_speech_from_ogg
from asgiref.sync import sync_to_async

# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")

bot = Bot(token=BOT_TOKEN)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
# Регистрируем router
router = Router()
dp.include_router(router)

# Главное меню с inline кнопками
main_menu_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="📝 Ввести слово", callback_data="enter_word")],
    [types.InlineKeyboardButton(text="🧠 Начать тест", callback_data="start_test")],
    [types.InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
])

translator = Translator()

# Словарь для отслеживания состояний пользователей
user_states = {}


# ============ CALLBACK HANDLERS ============

@router.callback_query(lambda c: c.data == 'enter_word')
async def process_enter_word_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки 'Ввести слово'"""
    await bot.answer_callback_query(callback_query.id)
    user_states[callback_query.from_user.id] = "waiting_for_word"
    await bot.send_message(
        callback_query.from_user.id,
        "📝 Напишите или 🎤 произнесите слово:\n\n"
        "🔸 Пример: hello\n"
        "🔸 Пример: привет\n"
        "🎤 Или отправьте голосовое сообщение!\n\n"
        "Я переведу слово и озвучу его на оба языка!"
    )


@router.callback_query(lambda c: c.data == 'settings')
async def process_settings_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки 'Настройки'"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "⚙️ Настройки времени:\n\n"
        "По умолчанию повторения назначаются через 2 часа.\n"
        "При правильном ответе интервал увеличивается.\n"
        "При неправильном - сбрасывается.",
        reply_markup=main_menu_kb
    )


@router.callback_query(lambda c: c.data == 'start_test')
async def process_start_test_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки 'Начать тест'"""
    await bot.answer_callback_query(callback_query.id)
    # Создаем fake message объект для передачи в start_quiz
    fake_message = Message(
        message_id=callback_query.message.message_id,
        date=callback_query.message.date,
        chat=callback_query.message.chat,
        from_user=callback_query.from_user
    )
    await start_quiz(fake_message)


# ============ COMMAND HANDLERS ============

@router.message(Command(commands=["start"]))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    user_name = message.from_user.first_name or message.from_user.username or "Пользователь"
    
    # Создаём или обновляем запись пользователя
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=message.from_user.id,
            defaults={
                'username': message.from_user.username or user_name
            }
        )
        if created:
            welcome_text = f"Привет, {user_name}! Добро пожаловать в VocabBot! 🎓\n\n"
        else:
            welcome_text = f"Привет снова, {user_name}! 😊\n\n"
            
        welcome_text += (
            "📚 Основные функции:\n"
            "• Нажмите 'Ввести слово' - я переведу и озвучу\n"
            "• Нажмите 'Начать тест' - проверьте свои знания\n"
            "• 🎤 Можно отправлять голосовые сообщения!\n\n"
            "Выберите действие:"
        )
        
        await message.answer(welcome_text, reply_markup=main_menu_kb)
        
    except Exception as e:
        await message.answer(
            f"Ошибка регистрации: {str(e)}\n"
            "Попробуйте ещё раз позже.",
            reply_markup=main_menu_kb
        )


# ============ VOICE MESSAGE HANDLER ============

@router.message(lambda message: message.voice is not None)
async def handle_voice_message(message: Message):
    """Обработка голосовых сообщений"""
    user_state = user_states.get(message.from_user.id)
    
    # Проверяем, что пользователь в состоянии ожидания
    if user_state not in ["waiting_for_word"] and not (isinstance(user_state, dict) and user_state.get("state") == "waiting_for_answer"):
        await message.answer(
            "🎤 Чтобы использовать голосовой ввод:\n\n"
            "• Нажмите 'Ввести слово' и отправьте голосовое\n"
            "• Или 'Начать тест' и ответьте голосом",
            reply_markup=main_menu_kb
        )
        return
    
    processing_msg = await message.answer("🎤 Распознаю речь...")
    
    try:
        # Скачиваем голосовое сообщение
        file = await bot.get_file(message.voice.file_id)
        
        # Создаем временный файл
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_path = temp_file.name
            await bot.download_file(file.file_path, temp_path)
        
        # Распознаем речь (пробуем оба языка)
        try:
            recognized_text = await recognize_speech_from_ogg(temp_path, language="ru-RU")
        except:
            recognized_text = await recognize_speech_from_ogg(temp_path, language="en-US")
        
        # Удаляем временный файл
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        await processing_msg.edit_text(f"✅ Распознано: **{recognized_text}**")
        
        # Обрабатываем распознанный текст
        if user_state == "waiting_for_word":
            user_states.pop(message.from_user.id, None)
            await handle_word_input(message, recognized_text)
        elif isinstance(user_state, dict) and user_state.get("state") == "waiting_for_answer":
            await handle_quiz_answer(message, recognized_text)
            
    except Exception as e:
        await processing_msg.edit_text(
            f"⚠️ Ошибка распознавания: {str(e)[:100]}...\n\n"
            "Попробуйте говорить четче или напишите текстом.",
            reply_markup=main_menu_kb
        )


# ============ MESSAGE HANDLER ============

@router.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.", reply_markup=main_menu_kb)
        return

    text = message.text.strip()
    
    # Проверяем состояние пользователя
    user_state = user_states.get(message.from_user.id)
    
    if user_state == "waiting_for_word":
        # Пользователь ввёл слово после нажатия "Ввести слово"
        user_states.pop(message.from_user.id, None)  # Очищаем состояние
        await handle_word_input(message, text)
        return
        
    elif isinstance(user_state, dict) and user_state.get("state") == "waiting_for_answer":
        # Пользователь отвечает на вопрос в тесте
        await handle_quiz_answer(message, text)
        return
    
    # Если это неизвестная команда/сообщение, показываем помощь
    await message.answer(
        "🤔 Не понял команду.\n\n"
        "🔹 Нажмите 'Ввести слово' для перевода\n"
        "🔹 Нажмите 'Начать тест' для тестирования\n"
        "🔹 🎤 Можно отправлять голосовые сообщения\n\n"
        "Выберите нужное действие из меню:",
        reply_markup=main_menu_kb
    )


# ============ HELPER FUNCTIONS ============

async def handle_word_input(message: Message, text: str):
    """Обработка ввода слова"""
    if not text or len(text.strip()) == 0:
        await message.answer("Пожалуйста, введите слово.", reply_markup=main_menu_kb)
        return

    # Проверяем регистрацию пользователя
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=message.from_user.id)
    except TelegramUser.DoesNotExist:
        await message.answer(
            "Вы не зарегистрированы. Используйте /start для регистрации.",
            reply_markup=main_menu_kb
        )
        return

    # Отправляем сообщение о начале обработки
    processing_msg = await message.answer("🔄 Обрабатываю слово...")

    # Переводим слово
    try:
        detection = translator.detect(text)
        detected_lang = detection.lang
        
        if detected_lang == 'ru':
            translation = translator.translate(text, src='ru', dest='en')
        else:
            translation = translator.translate(text, src='en', dest='ru')
            
        word_text = text
        word_translation = translation.text
            
        # Проверяем что перевод не пустой
        if not word_translation or not word_translation.strip():
            raise Exception("Пустой перевод")
            
    except Exception as e:
        await processing_msg.edit_text(
            f"⚠️ Не удалось перевести слово: {str(e)[:50]}...\n\nПопробуйте с другим словом.",
            reply_markup=main_menu_kb
        )
        return

    # Отправляем результат с переводом
    result_text = (
        f"✅ Перевод готов!\n\n"
        f"📝 **{word_text}** — **{word_translation}**\n"
        f"🌍 Язык: {detected_lang.upper()}"
    )

    await processing_msg.edit_text(result_text, reply_markup=main_menu_kb)
    
    # Озвучиваем оригинальное слово
    try:
        orig_lang = 'ru' if detected_lang == 'ru' else 'en'
        audio_path_orig = synthesize_text_to_mp3(word_text, lang=orig_lang)
        voice_file_orig = types.FSInputFile(path=audio_path_orig)
        await message.answer_voice(
            voice=voice_file_orig,
            caption=f"🔊 Оригинал: {word_text} ({orig_lang.upper()})"
        )
        if os.path.exists(audio_path_orig):
            os.remove(audio_path_orig)
    except Exception as audio_error:
        await message.answer(f"⚠️ Ошибка озвучивания оригинала: {str(audio_error)[:30]}...")
                
    # Озвучиваем перевод
    try:
        trans_lang = 'ru' if detected_lang != 'ru' else 'en'
        audio_path_trans = synthesize_text_to_mp3(word_translation, lang=trans_lang)
        voice_file_trans = types.FSInputFile(path=audio_path_trans)
        await message.answer_voice(
            voice=voice_file_trans,
            caption=f"🔊 Перевод: {word_translation} ({trans_lang.upper()})"
        )
        if os.path.exists(audio_path_trans):
            os.remove(audio_path_trans)
    except Exception as audio_error:
        await message.answer(f"⚠️ Ошибка озвучивания перевода: {str(audio_error)[:30]}...")
    
    # Сохраняем в БД (в фоне)
    try:
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Определяем исходный язык для сохранения
        source_lang = 'ru' if detected_lang == 'ru' else 'en'
        
        await sync_to_async(Word.objects.get_or_create)(
            user=telegram_user,
            text=word_text,
            defaults={
                'translation': word_translation,
                'source_lang': source_lang,
                'next_review': timezone.now() + timedelta(hours=2)
            }
        )
    except Exception as db_error:
        # Не показываем ошибку пользователю
        print(f"Ошибка сохранения: {db_error}")


async def start_quiz(message: Message):
    """Начинает тестирование"""
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=message.from_user.id)
        words = await sync_to_async(list)(Word.objects.filter(user=telegram_user))
        
        if len(words) < 1:
            await bot.send_message(
                message.chat.id,
                "📚 Нужно минимум 1 слово для теста.\n"
                "Добавьте несколько слов!",
                reply_markup=main_menu_kb
            )
            return
        
        # Фильтруем слова, где оригинал и перевод НЕ совпадают
        valid_words = [w for w in words if w.text.lower().strip() != w.translation.lower().strip()]
        
        if len(valid_words) < 1:
            await bot.send_message(
                message.chat.id,
                "📚 Нет подходящих слов для теста.\n"
                "Добавьте слова, которые переводятся по-разному!",
                reply_markup=main_menu_kb
            )
            return
            
        # Простой тест - показываем случайное слово из валидных
        random_word = random.choice(valid_words)
        
        # Определяем язык слова для правильного озвучивания
        def has_cyrillic(text):
            return bool([c for c in text if 'а' <= c.lower() <= 'я' or c.lower() in 'ёщ'])
        
        word_lang = 'ru' if has_cyrillic(random_word.text) else 'en'
        
        # Сохраняем состояние теста
        user_states[message.from_user.id] = {
            "state": "waiting_for_answer",
            "correct_answer": random_word.translation.lower().strip(),
            "word": random_word.text
        }
        
        await bot.send_message(
            message.chat.id,
            f"🧠 Тест начался!\n\n"
            f"📖 Переведите слово:\n\n"
            f"**{random_word.text}**\n\n"
            "Напишите перевод:"
        )
        
        # Озвучиваем слово на правильном языке
        try:
            audio_path = synthesize_text_to_mp3(random_word.text, lang=word_lang)
            voice_file = types.FSInputFile(path=audio_path)
            await bot.send_voice(
                message.chat.id,
                voice=voice_file,
                caption=f"🔊 Прослушайте: {random_word.text}"
            )
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as audio_error:
            await bot.send_message(
                message.chat.id,
                f"⚠️ Ошибка озвучивания: {str(audio_error)[:30]}..."
            )
        
    except TelegramUser.DoesNotExist:
        await bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы. Используйте /start.",
            reply_markup=main_menu_kb
        )


async def handle_quiz_answer(message: Message, text: str):
    """Обрабатывает ответ пользователя в тесте"""
    user_state = user_states.get(message.from_user.id, {})
    correct_answer = user_state.get("correct_answer", "")
    original_word = user_state.get("word", "")
    
    # Очищаем состояние
    user_states.pop(message.from_user.id, None)
    
    user_answer = text.lower().strip()
    
    # Проверяем ответ
    if user_answer == correct_answer:
        await message.answer(
            f"✅ **Правильно!**\n\n"
            f"📝 {original_word} — {correct_answer}\n\n"
            f"🎉 Отличная работа!",
            reply_markup=main_menu_kb
        )
    else:
        await message.answer(
            f"❌ **Неправильно!**\n\n"
            f"📝 {original_word} — **{correct_answer}**\n"
            f"💭 Ваш ответ: {user_answer}\n\n"
            f"💪 Попробуйте ещё раз позже!",
            reply_markup=main_menu_kb
        )

# telegram_bot.py

@router.message(Command(commands=["review"]))
async def review_handler(message: Message):
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=message.from_user.id)
    except TelegramUser.DoesNotExist:
        await message.answer("Вы не зарегистрированы. Используйте /start.", reply_markup=main_menu_kb)
        return

    # Находим карточки, готовые к повторению
    due_repetitions = await sync_to_async(list)(Repetition.objects.filter(card__owner=telegram_user,next_review__lte=timezone.now()).select_related('card')[:1]
    )

    if not due_repetitions:
        await message.answer("Нет слов для повторения. Молодец!", reply_markup=main_menu_kb)
        return

    repetition = due_repetitions[0]
    card = repetition.card

    # Сохраняем состояние
    user_states[message.from_user.id] = {
        "state": "waiting_for_review_answer",
        "card_id": card.id,
        "correct_answer": card.translation.lower().strip(),
        "word": card.word
    }

    await message.answer(
        f"🧠 Повторение:\n\n"
        f"📖 Переведите слово:\n\n"
        f"**{card.word}**\n\n"
        "Напишите перевод:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Отменить повторение")]],
            resize_keyboard=True
        )
    )

    # Озвучиваем слово
    try:
        lang = 'ru' if any('а' <= c <= 'я' for c in card.word.lower()) else 'en'
        audio_path = synthesize_text_to_mp3(card.word, lang=lang)
        voice_file = types.FSInputFile(path=audio_path)
        await message.answer_voice(voice=voice_file, caption="🔊 Слово")
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка озвучки: {str(e)[:30]}...")


async def handle_quiz_answer(message: Message, text: str):
    user_state = user_states.get(message.from_user.id, {})
    state_type = user_state.get("state")

    if state_type not in ["waiting_for_answer", "waiting_for_review_answer"]:
        return

    correct_answer = user_state.get("correct_answer", "")
    original_word = user_state.get("word", "")
    card_id = user_state.get("card_id")

    # Очищаем состояние
    user_states.pop(message.from_user.id, None)

    user_answer = text.lower().strip()

    # Определяем качество
    quality = 5 if user_answer == correct_answer else 1

    # Обновляем Repetition
    if card_id:
        try:
            card = await sync_to_async(Card.objects.get)(id=card_id)
            repetition = await sync_to_async(lambda: card.repetition)()
            repetition.schedule_review(quality)
        except Exception as e:
            print(f"Ошибка обновления повторения: {e}")

    # Ответ пользователю
    if user_answer == correct_answer:
        result_text = f"✅ **Правильно!**\n\n📝 {original_word} — {correct_answer}\n🎉 Отличная работа!"
    else:
        result_text = f"❌ **Неправильно!**\n\n📝 {original_word} — **{correct_answer}**\n💭 Ваш ответ: {user_answer}\n💪 Попробуйте ещё раз позже!"

    await message.answer(result_text, reply_markup=main_menu_kb)






async def main():
    print("🤖 Bot is starting...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except asyncio.CancelledError:
        print("⚠️ Polling cancelled.")
        pass


if __name__ == "__main__":
    asyncio.run(main())

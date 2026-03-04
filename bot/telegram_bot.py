# vocab_mvp/bot/telegram_bot.py
import asyncio
import os
import random
import sys
import tempfile
from datetime import timedelta

from aiogram import Bot, Dispatcher, types
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message
from asgiref.sync import sync_to_async
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()
# Добавляем корневую директорию проекта в PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__) + os.sep + "..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# Указываем Django, где искать настройки и инициализируем
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vocab.settings")
import django
django.setup()
# Django / модели (импорты после django.setup)
from django.utils import timezone
# Если вы используете напрямую библиотеку:
from bot.image_generator import fetch_image_for_word
from vocab.models import TelegramUser, Card, Repetition, UserSettings
from words.models import Word
# Наши утилиты (локальные модули)
from bot.voice import synthesize_text_to_mp3
from bot.speech_recognition_helper import detect_language_from_text
from bot.speech_recognition_helper import recognize_speech_from_ogg
# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")
bot = Bot(token=BOT_TOKEN)
# Aiogram storage / dispatcher / router
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

SETTINGS_URL = "http://127.0.0.1:8000/settings/"
LOGIN_URL = "http://127.0.0.1:8000/bot-login"
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')  # При хостинге: https://yoursite.com

# Состояния пользователей
user_states: dict = {}

# ================== КНОПКИ / МЕНЮ ==================
def make_settings_keyboard(current_gender: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Женский" if current_gender == "female" else "Женский",
                callback_data="voice_female",
            ),
            InlineKeyboardButton(
                text="✅ Мужской" if current_gender == "male" else "Мужской",
                callback_data="voice_male",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌐 Открыть веб-настройки",
                url=SETTINGS_URL
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Главное меню",
                callback_data="back_to_menu"
            )
        ]
    ])

def make_main_menu_keyboard(telegram_id):
    """Creates main menu with web link"""
    web_url = f"http://127.0.0.1:8000/bot-login/?telegram_id={telegram_id}"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📝 Ввести слово", callback_data="enter_word")],
        [types.InlineKeyboardButton(text="🧠 Начать тест", callback_data="start_test")],
        [types.InlineKeyboardButton(text="🔁 Повторение", callback_data="start_review")],
        [types.InlineKeyboardButton(text="🌐 Открыть сайт", url=web_url)],
        [types.InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
    ])
# Для обратной совместимости (где не известен telegram_id)
main_menu_kb = types.InlineKeyboardMarkup(inline_keyboard=[
    [types.InlineKeyboardButton(text="📝 Ввести слово", callback_data="enter_word")],
    [types.InlineKeyboardButton(text="🧠 Начать тест", callback_data="start_test")],
    [types.InlineKeyboardButton(text="🔁 Повторение", callback_data="start_review")],
    [types.InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]
])

# ================== HELPER: ОБРАБОТКА ВВОДА СЛОВА ==================
async def handle_word_input(message: Message, text: str):
    """Обработка ввода слова (текст или распознанный голос)."""
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
    processing_msg = await message.answer("🔄 Обрабатываю слово...")
    # Перевод слова
    try:
        raw_text = text.strip()
        # Детекция языка
        speech_lang = detect_language_from_text(raw_text)  # "ru-RU" или "en-US"
        if speech_lang == "ru-RU":
            detected_lang = "ru"
            src_lang = "ru"
            dest_lang = "en"
        else:
            detected_lang = "en"
            src_lang = "en"
            dest_lang = "ru"
        word_text = raw_text
        from deep_translator import GoogleTranslator
        word_translation = GoogleTranslator(source=src_lang, target=dest_lang).translate(word_text)
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
    # Озвучиваем оригинал
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
    # Сохраняем в БД и генерируем картинку
    try:
        source_lang = 'ru' if detected_lang == 'ru' else 'en'
        word_obj, created = await sync_to_async(Word.objects.get_or_create)(
            user=telegram_user,
            text=word_text,
            defaults={
                'translation': word_translation,
                'source_lang': source_lang,
                'next_review': timezone.now() + timedelta(hours=2),
            }
        )
        if created:
            # Пытаемся получить картинку через Pollinations
            django_file = fetch_image_for_word(word_text, word_translation)
            if django_file:
                # сохранить в ImageField асинхронно
                await sync_to_async(word_obj.image.save)(
                    django_file.name,
                    django_file,
                    save=True,
                )
                # отправить её пользователю
                try:
                    photo = types.FSInputFile(path=word_obj.image.path)
                    await message.answer_photo(
                        photo=photo,
                        caption="🖼 Картинка для этого слова",
                    )
                except Exception as send_err:
                    print(f"Error sending photo: {send_err}")
            else:
                # Картинку подобрать/сгенерировать не удалось — просто молчим или шлём текст
                print("Pollinations не смог вернуть картинку, продолжаем без неё.")
    except Exception as db_error:
        print(f"Ошибка сохранения: {db_error}")

# ================== ТЕСТ (QUIZ) ==================
async def start_quiz(message: Message):
    """Начинает тестирование."""
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
        valid_words = [w for w in words if w.text.lower().strip() != w.translation.lower().strip()]
        if len(valid_words) < 1:
            await bot.send_message(
                message.chat.id,
                "📚 Нет подходящих слов для теста.\n"
                "Добавьте слова, которые переводятся по-разному!",
                reply_markup=main_menu_kb
            )
            return
        random_word = random.choice(valid_words)
        def has_cyrillic(text: str) -> bool:
            return any('а' <= c <= 'я' or c in 'ёЁ' for c in text.lower())
        word_lang = 'ru' if has_cyrillic(random_word.text) else 'en'
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
            # card — это объект Card
            if card.image:
                photo = FSInputFile(card.image.path)
                await message.answer_photo(photo=photo, caption=card.word)
            else:
                await message.answer(card.word)

    except TelegramUser.DoesNotExist:
        await bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы. Используйте /start.",
            reply_markup=main_menu_kb
        )

async def handle_quiz_answer(message: Message, text: str):
    user_state = user_states.get(message.from_user.id, {})
    state_type = user_state.get("state")
    if state_type not in ["waiting_for_answer", "waiting_for_review_answer"]:
        return
    correct_answer = user_state.get("correct_answer", "")
    original_word = user_state.get("word", "")
    card_id = user_state.get("card_id")
    user_states.pop(message.from_user.id, None)
    user_answer = text.lower().strip()
    quality = 5 if user_answer == correct_answer else 1
    if card_id:
        try:
            card = await sync_to_async(Card.objects.select_related('repetition').get)(id=card_id)
            await sync_to_async(card.repetition.schedule_review)(quality)
            print(f"✅ Статистика обновлена для карточки {card_id}")
        except Exception as e:
            print(f"❌ Ошибка обновления повторения: {e}")
    pronounce_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="🔊 Прослушать ответ",
            callback_data=f"pronounce_{correct_answer[:40]}"
        )]
    ])
    if user_answer == correct_answer:
        result_text = (
            f"✅ **Правильно!**\n\n"
            f"📝 {original_word} — {correct_answer}\n"
            f"🎉 Отличная работа!"
        )
    else:
        result_text = (
            f"❌ **Неправильно!**\n\n"
            f"📝 {original_word} — **{correct_answer}**\n"
            f"💭 Ваш ответ: {user_answer}\n"
            f"💪 Попробуйте ещё раз позже!"
        )
    await message.answer(result_text, reply_markup=pronounce_kb)

# ================== CALLBACK HANDLERS ==================
@router.callback_query(lambda c: c.data == 'enter_word')
async def process_enter_word_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()
    user_states[callback_query.from_user.id] = "waiting_for_word"
    await bot.send_message(
        callback_query.from_user.id,
        "📝 Напишите или 🎤 произнесите слово:\n\n"
        "🔸 Пример: hello\n"
        "🔸 Пример: привет\n"
        "🎤 Или отправьте голосовое сообщение!\n\n"
        "Я переведу слово и озвучу его на оба языка!",
        reply_markup=main_menu_kb
    )

@router.callback_query(lambda c: c.data == 'start_test')
async def process_start_test_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки 'Начать тест'."""
    try:
        await callback_query.answer()
    except Exception:
        pass
    fake_message = Message(
        message_id=callback_query.message.message_id,
        date=callback_query.message.date,
        chat=callback_query.message.chat,
        from_user=callback_query.from_user
    ).as_(callback_query.bot)
    await start_quiz(fake_message)

@router.callback_query(lambda c: c.data == 'start_review')
async def process_start_review_callback(callback_query: types.CallbackQuery):
    """Обработка кнопки 'Повторение'."""
    try:
        await callback_query.answer()
    except Exception:
        pass
    fake_message = Message(
        message_id=callback_query.message.message_id,
        date=callback_query.message.date,
        chat=callback_query.message.chat,
        from_user=callback_query.from_user
    ).as_(callback_query.bot)
    await review_handler(fake_message)

@router.callback_query(lambda c: c.data == "settings")
async def process_settings_callback(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(
            telegram_id=callback_query.from_user.id
        )
    except TelegramUser.DoesNotExist:
        await bot.send_message(
            callback_query.from_user.id,
            "Вы не зарегистрированы. Используйте /start.",
            reply_markup=main_menu_kb
        )
        return
    settings, _ = await sync_to_async(UserSettings.objects.get_or_create)(
        user=telegram_user
    )
    kb = make_settings_keyboard(settings.voice_gender)
    text = (
        "⚙️ Настройки озвучки\n\n"
        f"Текущий голос: {'женский' if settings.voice_gender == 'female' else 'мужской'}.\n\n"
        "Выбери голос для озвучки кнопками ниже или открой веб-страницу настроек."
    )
    await bot.send_message(
        chat_id=callback_query.from_user.id,
        text=text,
        reply_markup=kb
    )

@router.callback_query(lambda c: c.data in ("voice_female", "voice_male"))
async def process_voice_choice(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass
    gender = "female" if callback_query.data == "voice_female" else "male"
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(
            telegram_id=callback_query.from_user.id
        )
        settings, _ = await sync_to_async(UserSettings.objects.get_or_create)(
            user=telegram_user
        )
        settings.voice_gender = gender
        await sync_to_async(settings.save)()
        kb = make_settings_keyboard(settings.voice_gender)
        try:
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=(
                    "⚙️ Настройки озвучки\n\n"
                    f"Текущий голос: {'женский' if gender == 'female' else 'мужской'}.\n\n"
                    "Выбери голос для озвучки кнопками ниже или открой веб-страницу настроек."
                ),
                reply_markup=kb
            )
        except Exception as e:
            if "message is not modified" in str(e):
                await callback_query.answer("Изменений нет")
            else:
                print(f"Ошибка сохранения: {e}")
    except Exception as e:
        await bot.send_message(
            callback_query.from_user.id,
            f"Ошибка сохранения настроек: {str(e)[:80]}",
            reply_markup=main_menu_kb
        )

@router.callback_query(lambda c: c.data == "back_to_menu")
async def process_back_to_menu(callback_query: types.CallbackQuery):
    try:
        await callback_query.answer()
    except Exception:
        pass
    await bot.send_message(
        callback_query.from_user.id,
        "Главное меню:",
        reply_markup=main_menu_kb
    )

@router.callback_query(lambda c: c.data.startswith("review_q"))
async def process_review_quality(callback_query: types.CallbackQuery):
    """Обработка оценки повторения."""
    try:
        await callback_query.answer()
    except Exception:
        pass
    parts = callback_query.data.split('_')
    quality = int(parts[1][1])  # q1/q2/q3/q4
    card_id = int(parts[2])
    try:
        card = await sync_to_async(Card.objects.select_related('repetition').get)(id=card_id)
        repetition = card.repetition
        await sync_to_async(repetition.schedule_review)(quality)
        quality_names = {
            1: "Совсем не помнил",
            2: "С трудом",
            3: "Хорошо",
            4: "Отлично"
        }
        result_text = f"✅ Оценка сохранена: {quality_names[quality]}\n\n"
        next_review = repetition.next_review
        result_text += f"📅 Следующее повторение: {next_review.strftime('%d.%m.%Y %H:%M')}"
        await callback_query.bot.send_message(
            chat_id=callback_query.from_user.id,
            text=result_text,
            reply_markup=main_menu_kb
        )
    except Exception as e:
        await callback_query.bot.send_message(
            chat_id=callback_query.from_user.id,
            text=f"⚠️ Ошибка сохранения: {str(e)[:100]}",
            reply_markup=main_menu_kb
        )

@router.callback_query(lambda c: c.data.startswith("show_answer_"))
async def process_show_answer_callback(callback_query: types.CallbackQuery):
    await callback_query.answer("Обрабатываю...")
    card_id = int(callback_query.data.split('_')[2])
    card = await sync_to_async(Card.objects.get)(id=card_id)
    telegram_user = await sync_to_async(TelegramUser.objects.get)(
        telegram_id=callback_query.from_user.id
    )
    user_settings, _ = await sync_to_async(UserSettings.objects.get_or_create)(
        user=telegram_user
    )
    lang = 'ru' if any('a' <= c <= 'z' for c in card.word.lower()) else 'en'
    translation_text = (
        "💡 Перевод: **%s**\n\nОцените, насколько легко вы вспомнили:" % card.translation
    )
    quality_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="1 — Совсем не помнил", callback_data=f"review_q1_{card.id}")],
        [types.InlineKeyboardButton(text="2 — С трудом", callback_data=f"review_q2_{card.id}")],
        [types.InlineKeyboardButton(text="3 — Хорошо", callback_data=f"review_q3_{card.id}")],
        [types.InlineKeyboardButton(text="4 — Отлично", callback_data=f"review_q4_{card.id}")],
    ])
    await callback_query.message.answer(translation_text, reply_markup=quality_kb)
    try:
        gender = user_settings.voice_gender  # пока просто читаем; можно учитывать в synthesize_text_to_mp3
        audio_path = synthesize_text_to_mp3(card.translation, lang=lang)
        if os.path.exists(audio_path):
            voice_file = FSInputFile(audio_path)
            await callback_query.message.answer_voice(voice=voice_file)
            os.remove(audio_path)
    except Exception as e:
        print(f"Ошибка озвучки: {e}")

@router.callback_query(lambda c: c.data.startswith("pronounce_"))
async def pronounce_callback(callback: types.CallbackQuery):
    text_to_speak = callback.data.split("_", 1)[1]
    try:
        lang = 'en' if any('a' <= c <= 'z' for c in text_to_speak.lower()) else 'ru'
        audio_path = synthesize_text_to_mp3(text_to_speak, lang=lang)
        if audio_path and os.path.exists(audio_path):
            voice_file = types.FSInputFile(path=audio_path)
            await callback.message.answer_voice(voice=voice_file, caption=f"🔊 {text_to_speak}")
            os.remove(audio_path)
            await callback.answer()
    except Exception as e:
        await callback.answer(f"Ошибка озвучки: {str(e)[:30]}", show_alert=True)

# ================== КОМАНДЫ ==================
@router.message(Command(commands=["start"]))
async def start_handler(message: Message):
    """Обработчик команды /start."""
    user_name = message.from_user.first_name or message.from_user.username or "Пользователь"
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(
            telegram_id=message.from_user.id,
            defaults={
                'username': message.from_user.username or user_name
            }
        )
        if created:
            prefix = f"Привет, {user_name}! Добро пожаловать в VocabBot! 🎓\n\n"
        else:
            prefix = f"Привет снова, {user_name}! 😊\n\n"
        main_part = (
            "📚 Основные функции:\n"
            "• Нажмите 'Ввести слово' — я переведу и озвучу\n"
            "• Нажмите 'Начать тест' — проверим ваши знания\n"
            "• Нажмите 'Повторение' — повторение по SM‑2\n"
            "• 🎤 Можно отправлять голосовые сообщения!\n\n"
            "Выберите действие:"
        )
        welcome_text = prefix + main_part
        
        # Используем меню со ссылкой на сайт
        menu_kb = make_main_menu_keyboard(message.from_user.id)
        await message.answer(welcome_text, reply_markup=menu_kb)
    except Exception as e:
        await message.answer(
            f"Ошибка регистрации: {str(e)}\n"
            "Попробуйте ещё раз позже.",
            reply_markup=main_menu_kb
        )

@router.message(Command(commands=["settings"]))
async def cmd_settings(message: Message):
    """Команда /settings — выбор голоса и ссылка на веб-настройки."""
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(
            telegram_id=message.from_user.id
        )
    except TelegramUser.DoesNotExist:
        await message.answer("Вы не зарегистрированы. Используйте /start.", reply_markup=main_menu_kb)
        return
    settings, _ = await sync_to_async(UserSettings.objects.get_or_create)(
        user=telegram_user
    )
    kb = make_settings_keyboard(settings.voice_gender)
    text = (
        "⚙️ Настройки озвучки\n\n"
        f"Текущий голос: {'женский' if settings.voice_gender == 'female' else 'мужской'}.\n\n"
        "Выбери голос для озвучки кнопками ниже или открой веб-страницу настроек."
    )
    await message.answer(text, reply_markup=kb)

@router.message(Command(commands=["review"]))
async def review_handler(message: Message):
    """
    Обработчик команды /review и кнопки 'Повторение'.
    Показывает только слово, ответ скрыт за кнопкой.
    """
    try:
        telegram_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=message.from_user.id)
    except TelegramUser.DoesNotExist:
        await message.answer("Вы не зарегистрированы. Используйте /start.", reply_markup=main_menu_kb)
        return
    due_repetitions = await sync_to_async(list)(
        Repetition.objects.filter(
            card__owner=telegram_user,
            next_review__lte=timezone.now()
        ).select_related('card').order_by('next_review')[:1]
    )
    if not due_repetitions:
        await message.answer("Нет слов для повторения. Молодец!", reply_markup=main_menu_kb)
        return
    repetition = due_repetitions[0]
    card = repetition.card
    show_kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="👁 Показать перевод", callback_data=f"show_answer_{card.id}")]
    ])
    caption = f"🧠 Повторение:\n\n📖 Переведите слово:\n\n**{card.word}**"
    if card.image:
        try:
            photo = types.FSInputFile(path=card.image.path)
            await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=show_kb
            )
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")
            await message.answer(caption, reply_markup=show_kb)
    else:
        await message.answer(caption, reply_markup=show_kb)
    try:
        lang = 'ru' if any('а' <= c <= 'я' for c in card.word.lower()) else 'en'
        audio_path = synthesize_text_to_mp3(card.word, lang=lang)
        voice_file = types.FSInputFile(path=audio_path)
        await message.answer_voice(voice=voice_file, caption="🔊 Произношение")
        if os.path.exists(audio_path):
            os.remove(audio_path)
    except Exception as e:
        print(f"Ошибка озвучки: {e}")

# ================== VOICE / TEXT HANDLERS ==================
@router.message(lambda message: message.voice is not None)
async def handle_voice_message(message: Message):
    """Обработка голосовых сообщений."""
    user_state = user_states.get(message.from_user.id)
    valid_states = ["waiting_for_word"]
    valid_dict_states = ["waiting_for_answer", "waiting_for_review_answer"]
    is_valid = user_state in valid_states or (
        isinstance(user_state, dict) and user_state.get("state") in valid_dict_states
    )
    if not is_valid:
        await message.answer(
            "🎤 Чтобы использовать голосовой ввод:\n\n"
            "• Нажмите 'Ввести слово' и отправьте голосовое\n"
            "• Или 'Начать тест' и ответьте голосом\n"
            "• Или 'Повторение' и ответьте голосом",
            reply_markup=main_menu_kb
        )
        return
    processing_msg = await message.answer("🎤 Распознаю речь...")
    try:
        file = await bot.get_file(message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_path = temp_file.name
            await bot.download_file(file.file_path, temp_path)
        try:
            recognized_text = await recognize_speech_from_ogg(temp_path, language="ru-RU")
        except Exception:
            recognized_text = await recognize_speech_from_ogg(temp_path, language="en-US")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        await processing_msg.edit_text(f"✅ Распознано: **{recognized_text}**")
        if user_state == "waiting_for_word":
            user_states.pop(message.from_user.id, None)
            await handle_word_input(message, recognized_text)
        elif isinstance(user_state, dict) and user_state.get("state") in ["waiting_for_answer", "waiting_for_review_answer"]:
            await handle_quiz_answer(message, recognized_text)
    except Exception as e:
        await processing_msg.edit_text(
            f"⚠️ Ошибка распознавания: {str(e)[:100]}...\n\n"
            "Попробуйте говорить четче или напишите текстом.",
            reply_markup=main_menu_kb
        )

@router.message()
async def handle_message(message: Message):
    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовое сообщение.", reply_markup=main_menu_kb)
        return
    text = message.text.strip()
    user_state = user_states.get(message.from_user.id)
    if user_state == "waiting_for_word":
        user_states.pop(message.from_user.id, None)
        await handle_word_input(message, text)
        return
    elif isinstance(user_state, dict) and user_state.get("state") == "waiting_for_answer":
        await handle_quiz_answer(message, text)
        return
    elif isinstance(user_state, dict) and user_state.get("state") == "waiting_for_review_answer":
        await handle_quiz_answer(message, text)
        return
    await message.answer(
        "🤔 Не понял команду.\n\n"
        "🔹 Нажмите 'Ввести слово' для перевода\n"
        "🔹 Нажмите 'Начать тест' для тестирования\n"
        "🔹 🎤 Можно отправлять голосовые сообщения\n\n"
        "Выберите нужное действие из меню:",
        reply_markup=main_menu_kb
    )

# ================== MAIN ==================
async def main():
    print("🤖 Bot is starting...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except asyncio.CancelledError:
        print("⚠️ Polling cancelled.")
        return

if __name__ == "__main__":
    asyncio.run(main())

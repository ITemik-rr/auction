from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import DatabaseManager, create_collage
import schedule
import threading
import sqlite3
import time
import os
import cv2
import numpy as np
from config import API_TOKEN, DATABASE

bot = TeleBot(API_TOKEN)
manager = DatabaseManager(DATABASE)

def gen_markup(prize_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=f"get_{prize_id}"))
    return markup

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    username = message.from_user.username or f"user_{user_id}"

    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, username)
        bot.reply_to(message, """Привет Добро пожаловать 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки, и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку «Получить»

Только три первых пользователя получат картинку""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    rating = manager.get_rating()
    if not rating:
        bot.send_message(message.chat.id, "Рейтинг пока пуст.")
        return

    header = f"| {'USER_NAME':<12} | {'ПРИЗЫ':<8} |\n" + "-" * 28
    rows = [f"| @{user:<12} | {count:<8} |" for user, count in rating]
    table = "\n".join([header] + rows)
    bot.send_message(message.chat.id, f"```\n{table}\n```", parse_mode="Markdown")

@bot.message_handler(commands=['get_my_score'])
def get_my_score(message):
    user_id = message.chat.id
    username = message.from_user.username or f"user_{user_id}"

    # Получаем список выигранных картинок
    won_images = set(manager.get_winners_img(user_id))

    # Все возможные призы
    all_images = os.listdir('img')

    # Формируем пути: выигранные — из `img/`, остальные — из `hidden_img/`
    image_paths = []
    for img in all_images:
        if not img.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
            continue
        path = f'img/{img}' if img in won_images else f'hidden_img/{img}'
        # Если запикселенная версия не существует — создаём
        if path.startswith('hidden_img/') and not os.path.exists(path):
            hide_img(img)  # Убедимся, что запикселенная версия есть
        if os.path.exists(path):
            image_paths.append(path)

    if not image_paths:
        bot.send_message(user_id, "Пока нет доступных призов для отображения.")
        return

    # Создаём коллаж
    try:
        collage = create_collage(image_paths, target_size=(120, 120))
        temp_path = f'collage_{user_id}.jpg'
        cv2.imwrite(temp_path, collage)

        with open(temp_path, 'rb') as photo:
            bot.send_photo(user_id, photo, caption=f"Твои достижения, @{username} 🎉\nБелые — выигранные, пиксельные — упущенные.")

        os.remove(temp_path)  # Удаляем временный файл
    except Exception as e:
        bot.send_message(user_id, "Не удалось создать коллаж. Попробуй позже.")
        print(f"Ошибка при создании коллажа: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("get_"))
def callback_query(call):
    prize_id = int(call.data.split("_")[1])
    user_id = call.message.chat.id
    username = call.from_user.username or f"user_{user_id}"

    current_winners = manager.get_winners_count(prize_id)
    if current_winners >= 3:
        bot.send_message(user_id, "К сожалению, ты не успел. Приз уже разыгран. Попробуй в следующий раз!")
        return

    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
    if cur.fetchone():
        bot.send_message(user_id, "Ты уже получил этот приз!")
        return

    result = manager.add_winner(user_id, prize_id)
    if result == 1:
        img = manager.get_prize_img(prize_id)
        with open(f'img/{img}', 'rb') as photo:
            bot.send_photo(user_id, photo, caption="🎉 Поздравляем Ты один из первых трёх Вот расшифрованная картинка!")
    else:
        bot.send_message(user_id, "Произошла ошибка при получении приза.")

def hide_img(img_name):
    """Пикселизация изображения."""
    image = cv2.imread(f'img/{img_name}')
    if image is None:
        return
    blurred = cv2.GaussianBlur(image, (15, 15), 0)
    small = cv2.resize(blurred, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated = cv2.resize(small, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    os.makedirs('hidden_img', exist_ok=True)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated)

def send_message():
    prize_data = manager.get_random_prize()
    if not prize_data:
        return
    prize_id, img_name = prize_data
    manager.mark_prize_used(prize_id)
    hide_img(img_name)
    for user_id in manager.get_users():
        try:
            with open(f'hidden_img/{img_name}', 'rb') as photo:
                bot.send_photo(user_id, photo, reply_markup=gen_markup(prize_id))
        except Exception as e:
            print(f"Ошибка при отправке фото пользователю {user_id}: {e}")

def schedule_thread():
    schedule.every().hour.do(send_message)
    while True:
        schedule.run_pending()
        time.sleep(1)

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager.create_tables()
    os.makedirs('hidden_img', exist_ok=True)

    threading.Thread(target=polling_thread, daemon=True).start()
    threading.Thread(target=schedule_thread, daemon=True).start()

    print("Бот запущен. Ожидание команд...")
    while True:
        time.sleep(1)

import sqlite3
import os
import cv2
import numpy as np
from config import DATABASE
import datetime

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
            ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0,
                sent_time TEXT  -- время первого розыгрыша
            )
            ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
            ''')
            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT OR IGNORE INTO users (user_id, user_name) VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('INSERT OR IGNORE INTO prizes (image) VALUES (?)', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
            if cur.fetchone():
                return 0
            conn.execute('INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)', (user_id, prize_id, win_time))
            conn.commit()
            return 1

    def mark_prize_used(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE prizes SET used = 1 WHERE prize_id = ?', (prize_id,))
            conn.commit()

    def get_users(self):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT user_id FROM users')
        return [row[0] for row in cur.fetchall()]

    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id,))
        row = cur.fetchone()
        return row[0] if row else None

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1')
        row = cur.fetchone()
        return row

    def get_winners_count(self, prize_id):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (prize_id,))
        return cur.fetchone()[0]

    def get_rating(self):
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('''
            SELECT u.user_name, COUNT(w.prize_id) AS prize_count
            FROM users u
            INNER JOIN winners w ON u.user_id = w.user_id
            GROUP BY u.user_id, u.user_name
            ORDER BY prize_count DESC
            LIMIT 10
        ''')
        return cur.fetchall()

    def get_winners_img(self, user_id):
        """Возвращает список имён изображений, которые пользователь выиграл."""
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        cur.execute('''
            SELECT p.image
            FROM winners w
            INNER JOIN prizes p ON w.prize_id = p.prize_id
            WHERE w.user_id = ?
        ''', (user_id,))
        return [row[0] for row in cur.fetchall()]


def create_collage(image_paths, target_size=(100, 100)):

    images = []
    for path in image_paths:
        if not os.path.exists(path):
            continue
        image = cv2.imread(path)
        if image is None:
            continue
        image = cv2.resize(image, target_size)
        images.append(image)

    if not images:
        # Возвращаем пустое изображение 100x100, если нет картинок
        return np.ones((100, 100, 3), dtype=np.uint8) * 200

    num_images = len(images)
    num_cols = max(1, int(np.floor(np.sqrt(num_images))))
    num_rows = int(np.ceil(num_images / num_cols))

    h, w, c = target_size[1], target_size[0], 3
    collage = np.zeros((num_rows * h, num_cols * w, c), dtype=np.uint8)

    for i, img in enumerate(images):
        row = i // num_cols
        col = i % num_cols
        collage[row*h:(row+1)*h, col*w:(col+1)*w, :] = img

    return collage
    
def mark_prize_sent_time(self, prize_id, sent_time=None):
    """Отмечает время первого розыгрыша приза."""
    if sent_time is None:
        sent_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(self.database)
    with conn:
        conn.execute('UPDATE prizes SET sent_time = ? WHERE prize_id = ?', (sent_time, prize_id))
        conn.commit()

def get_prizes_for_second_chance(self):
    """Возвращает призы, по которым прошёл 1 час, но победителей < 3."""
    conn = sqlite3.connect(self.database)
    cur = conn.cursor()
    cur.execute('''
        SELECT p.prize_id, p.image
        FROM prizes p
        WHERE p.used = 1
          AND p.sent_time IS NOT NULL
          AND DATETIME('now') >= DATETIME(p.sent_time, '+1 hour')
          AND (SELECT COUNT(*) FROM winners w WHERE w.prize_id = p.prize_id) < 3
    ''')
    return cur.fetchall()

def get_non_winners(self, prize_id):
    """Возвращает user_id всех пользователей, кроме победителей этого приза."""
    conn = sqlite3.connect(self.database)
    cur = conn.cursor()
    cur.execute('''
        SELECT u.user_id
        FROM users u
        WHERE u.user_id NOT IN (
            SELECT w.user_id FROM winners w WHERE w.prize_id = ?
        )
    ''', (prize_id,))
    return [row[0] for row in cur.fetchall()]

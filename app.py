from flask import Flask, request, jsonify
import sqlite3
import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Конфигурация
BOT_TOKEN = "7969256328:AAFmG9IcEnWjCaW6Y-aHqE1SqZ9U9veDs9M"
ADMIN_IDS = [1996167272]  # Ваш Telegram ID

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN)


# Инициализация БД
def init_db():
    if not os.path.exists("shop.db"):
        conn = sqlite3.connect("shop.db")
        cursor = conn.cursor()

        # Таблица товаров
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            description TEXT
        )
        """)

        # Таблица заказов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            user_name TEXT,
            product_id INTEGER NOT NULL,
            product_name TEXT,
            status TEXT DEFAULT 'pending',
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Добавляем тестовые товары, если их нет
        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                "INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
                [
                    ("Смартфон", 29999, "Новейший смартфон"),
                    ("Ноутбук", 59999, "Мощный ноутбук"),
                    ("Наушники", 4999, "Беспроводные наушники")
                ]
            )

        conn.commit()
        conn.close()


# API для сайта
@app.route("/bot-api/products", methods=["GET"])
def get_products():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    conn.close()

    return jsonify([
        {"id": p[0], "name": p[1], "price": p[2], "description": p[3]}
        for p in products
    ])


@app.route("/bot-api/orders", methods=["GET"])
def get_user_orders():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, p.name, o.status 
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
    """, (user_id,))

    orders = cursor.fetchall()
    conn.close()

    return jsonify([
        {"id": o[0], "product_name": o[1], "status": o[2]}
        for o in orders
    ])


@app.route("/bot-api/all_orders", methods=["GET"])
def get_all_orders():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.user_id, o.user_name, p.name, o.status 
        FROM orders o
        JOIN products p ON o.product_id = p.id
    """)

    orders = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "id": o[0],
            "user_id": o[1],
            "user_name": o[2],
            "product_name": o[3],
            "status": o[4]
        }
        for o in orders
    ])


@app.route("/bot-api/create_order", methods=["POST"])
def create_order():
    data = request.json
    user_id = data.get("user_id")
    product_id = data.get("product_id")

    if not user_id or not product_id:
        return jsonify({"error": "Missing data"}), 400

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()

    # Получаем данные товара
    cursor.execute("SELECT name FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    # Получаем имя пользователя (если есть)
    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    user_name = user[0] if user else None

    # Создаем заказ
    cursor.execute("""
        INSERT INTO orders (user_id, user_name, product_id, product_name)
        VALUES (?, ?, ?, ?)
    """, (user_id, user_name, product_id, product[0]))

    conn.commit()
    order_id = cursor.lastrowid
    conn.close()

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        bot.send_message(
            admin_id,
            f"🛒 Новый заказ #{order_id}\n"
            f"👤 Пользователь: {user_name or user_id}\n"
            f"📦 Товар: {product[0]}\n"
            f"🔄 Статус: pending"
        )

    return jsonify({"success": True, "order_id": order_id})


@app.route("/bot-api/update_order", methods=["POST"])
def update_order():
    data = request.json
    order_id = data.get("order_id")
    status = data.get("status")

    if not order_id or not status:
        return jsonify({"error": "Missing data"}), 400

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/bot-api/is_admin", methods=["GET"])
def is_admin():
    user_id = request.args.get("user_id")
    return jsonify({"is_admin": int(user_id) in ADMIN_IDS})


# Запуск бота и Flask-сервера
if __name__ == "__main__":
    init_db()

    # Удаляем вебхук (если был)
    bot.remove_webhook()

    # Устанавливаем вебхук для обработки сообщений
    bot.set_webhook(url="https://your-server.com/webhook")

    # Запускаем Flask
    app.run(host="0.0.0.0", port=5000)
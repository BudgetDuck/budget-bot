import logging
logging.basicConfig(level=logging.DEBUG)
import gspread
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime
import os
print("🔧 Bot.py is starting...")


# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_SHEET = os.getenv("BudgetBot")
print("🔑 TOKEN:", BOT_TOKEN)
print("📄 SHEET:", GOOGLE_SHEET)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Авторизация Google Sheets
gc = gspread.service_account(filename="credentials.json")
sheet = gc.open(GOOGLE_SHEET).sheet1

# Telegram ID → Имя
user_map = {
    "katty_kattie": "Катя",
    "AndreiSheleg": "Андрей"
}

# Платёжные средства → Валюта
account_currency_map = {
    "PKO Андрей PLN": "PLN", "PKO Катя PLN": "PLN", "PKO Катя EUR": "EUR",
    "карта Santander PLN": "PLN", "карта PEKAO PLN": "PLN", "карта MBank PLN": "PLN",
    "Revolut Катя": "PLN",
    "карта Приор Катя": "BYN", "карта Приор Андрея": "BYN",
    "наличные BYN": "BYN", "наличные PLN": "PLN"
}

# Стартовая клавиатура
start_kb = ReplyKeyboardMarkup(resize_keyboard=True)
start_kb.add(
    KeyboardButton("Доход"),
    KeyboardButton("Расход"),
    KeyboardButton("Перевод")
)

# Средства оплаты
payment_methods = ["карта MBank PLN"] + [x for x in account_currency_map.keys() if x != "карта MBank PLN"]
payment_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
for item in payment_methods:
    payment_kb.add(KeyboardButton(item))

# Категории
expense_categories = {
    "Жилье": ["Коммунальные", "Электричество", "Аренда квартиры", "Легализация", "Интернет", "Мобильная связь", "Карточки", "Крупные покупки: техника, мебель и пр.", "Прочее"],
    "Питание": ["Обеды", "Прочее"],
    "Проезд": ["Проездной, талоны", "Витебск, Солигорск", "Такси и прочее"],
    "Бытовая химия": ["Косметика", "Бытовая химия", "Колготки, носки", "Прочее"],
    "Досуг": ["Путешествия, визы", "Обучение, книги", "Встречи с друзьями / коллегами", "Театр, кино", "Кафе", "Прочее"],
    "Уход за собой": ["Маникюр/педикюр", "Прическа, стрижка", "Косметолог, эпиляция", "Бассейн, велик, спорт", "Лечение, аптеки", "Прочее"],
    "Ребенок": ["Питание", "Бытовая химия, аптека, быт", "Одежда, обувь", "Игрушки, развивашки, книги", "Детский сад", "Прочее"],
    "Автомобиль": ["Обязательные платежи", "Топливо", "Обслуживание", "Мойка", "Ремонт", "Прочее"],
    "Одежда": ["Нижняя одежда", "Майки, шорты, сарафаны и пр.", "Верхняя одежда", "Кофты, штаны, платья", "Обувь", "Сумки, галантерея"],
    "Подарки": ["Родные", "Крестники", "Друзья", "В гости", "Коллеги"],
    "Дикая утка": ["Оплаты Мбанку", "Арендаторы", "Чынш, медиа, интернет", "Мебель, техника, ремонт", "Прочее"]
}
income_cat1 = ["Катя", "Андрей"]
income_cat2 = ["ЗП на карточку", "Халтура", "Согласования", "Подарки"]

# Память
user_data = {}

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Что вы хотите внести?", reply_markup=start_kb)
    
@dp.message_handler(lambda msg: msg.text in ["Доход", "Расход", "Перевод"])
async def step1(msg: types.Message):
    user_data[msg.from_user.id] = {
        "Тип": msg.text,
        "Имя": user_map.get(msg.from_user.username, "Неизвестно")
    }
    await msg.answer("Введите сумму (числом):")

@dp.message_handler(lambda msg: msg.text.replace(".", "").replace(",", "").replace("-", "").isdigit())
async def step2(msg: types.Message):
    data = user_data.get(msg.from_user.id)
    if not data:
        return await msg.answer("Сначала выберите тип операции")

    amount = abs(float(msg.text))
    data["Сумма"] = amount

    if data["Тип"] == "Перевод":
        kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for method in payment_methods:
            kb.add(KeyboardButton(method))
        await msg.answer("Откуда перевод?", reply_markup=kb)
    else:
        if data["Тип"] == "Расход":
            amount = -amount
        data["Сумма"] = amount
        await msg.answer("Выберите средство оплаты:", reply_markup=payment_kb)

@dp.message_handler(lambda msg: user_data.get(msg.from_user.id, {}).get("Тип") == "Перевод" and "Откуда" not in user_data.get(msg.from_user.id, {}))
async def step_transfer_from(msg: types.Message):
    data = user_data.get(msg.from_user.id)
    data["Откуда"] = msg.text
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for method in payment_methods:
        kb.add(KeyboardButton(method))
    await msg.answer("Куда перевод?", reply_markup=kb)

@dp.message_handler(lambda msg: user_data.get(msg.from_user.id, {}).get("Тип") == "Перевод" and "Куда" not in user_data.get(msg.from_user.id, {}))
async def step_transfer_to(msg: types.Message):
    data = user_data.get(msg.from_user.id)
    data["Куда"] = msg.text
    now = datetime.now()
    user = data["Имя"]
    day, month, year = now.day, now.month, now.year
    amount = data["Сумма"]
    from_acc = data["Откуда"]
    to_acc = data["Куда"]
    currency = account_currency_map.get(from_acc, "")
    data["Валюта"] = currency

    row1 = [user, day, month, year, -amount, currency, from_acc, "Перевод", "", "", ""]
    row2 = [user, day, month, year, amount, currency, to_acc, "Перевод", "", "", ""]

    sheet.append_row(row1)
    sheet.append_row(row2)

    await msg.answer("Перевод записан. Хочешь добавить ещё одну операцию? Нажми кнопку.")
    await msg.answer("Если хочешь ввести новую — выбери /start", reply_markup=start_kb)
    user_data.pop(msg.from_user.id)
     
@dp.message_handler(lambda msg: msg.text in payment_methods and user_data.get(msg.from_user.id, {}).get("Тип") in ["Доход", "Расход"] and "Откуда" not in user_data.get(msg.from_user.id, {}))
async def step3_income_expense(msg: types.Message):
    data = user_data.get(msg.from_user.id)
    data["Способ"] = msg.text
    data["Валюта"] = account_currency_map.get(msg.text, "")
    cat_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if data["Тип"] == "Доход":
        for cat in income_cat1:
            cat_kb.add(KeyboardButton(cat))
    else:
        for cat in expense_categories.keys():
            cat_kb.add(KeyboardButton(cat))
    await msg.answer("Выберите категорию 1:", reply_markup=cat_kb)

    now = datetime.now()
    user = data["Имя"]
    day, month, year = now.day, now.month, now.year
    amount = data["Сумма"]
    from_acc = data["Откуда"]
    to_acc = data["Куда"]
    data["Валюта"] = account_currency_map.get(from_acc, "")
    currency = account_currency_map.get(from_acc, "")

    # Строка "откуда" — со знаком минус
    row1 = [user, day, month, year, -amount, currency, from_acc, "Перевод", "", "", ""]
    # Строка "куда" — со знаком плюс
    row2 = [user, day, month, year, amount, currency, to_acc, "Перевод", "", "", ""]

    sheet.append_row(row1)
    sheet.append_row(row2)

    await msg.answer("Перевод записан. Хочешь добавить ещё одну операцию? Нажми кнопку.")
    await msg.answer("Если хочешь ввести новую — выбери /start", reply_markup=start_kb)
    user_data.pop(msg.from_user.id)
    
@dp.message_handler()
async def step4(msg: types.Message):
    data = user_data.get(msg.from_user.id)
    if data.get("Тип") == "Перевод":
        return
    if "Категория 1" not in data:
        data["Категория 1"] = msg.text
        cat2_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        if data["Тип"] == "Доход":
            for c in income_cat2:
                cat2_kb.add(KeyboardButton(c))
        else:
            for c in expense_categories.get(msg.text, ["Прочее"]):
                cat2_kb.add(KeyboardButton(c))
        await msg.answer("Выберите категорию 2:", reply_markup=cat2_kb)
    elif "Категория 2" not in data:
        data["Категория 2"] = msg.text
        await msg.answer("Добавьте комментарий:")
    elif "Комментарий" not in data:
        data["Комментарий"] = msg.text
        now = datetime.now()
        row = [
            data["Имя"],
            now.day,
            now.month,
            now.year,
            data["Сумма"],
            data["Валюта"],
            data["Способ"],
            data["Тип"],
            data["Категория 1"],
            data["Категория 2"],
            data["Комментарий"]
        ]
        sheet.append_row(row)
        await msg.answer("Запись добавлена. Хочешь добавить ещё одну? Нажми кнопку.")
        await msg.answer("Если хочешь ввести новую - выбери /start", reply_markup=start_kb)
        user_data.pop(msg.from_user.id)

from aiogram import executor 

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)

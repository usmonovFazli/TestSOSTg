import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
import os
TOKEN = os.getenv("TOKEN")


bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# 🔹 Загружаем структуру регионов из файла
with open("mapping.json", "r", encoding="utf-8") as f:
    REGION_MAP = json.load(f)

# 🔹 Временное хранилище (нет БД)
user_data = {}

# --------------------- ХЭНДЛЕРЫ ----------------------

@dp.message(CommandStart())
async def start(message: types.Message):
    kb = ReplyKeyboardBuilder()
    for region in REGION_MAP.keys():
        kb.button(text=region)
    kb.adjust(2)

    user_data[message.from_user.id] = {}

    await message.answer(
        "👋 Привет! Этот бот помогает связаться с участковым.\n\n"
        "Выберите область:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )


@dp.message(F.text.in_(list(REGION_MAP.keys())))
async def select_region(message: types.Message):
    region = message.text
    user_data[message.from_user.id]["region"] = region

    kb = ReplyKeyboardBuilder()
    for city in REGION_MAP[region].keys():
        kb.button(text=city)
    kb.adjust(2)

    await message.answer(
        f"🏙️ Область <b>{region}</b> выбрана.\nТеперь выберите город:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )


@dp.message()
async def select_city_or_mahalla(message: types.Message):
    uid = message.from_user.id

    if uid not in user_data or "region" not in user_data[uid]:
        return await message.answer("Сначала нажмите /start")

    region = user_data[uid]["region"]

    # Выбор города
    if message.text in REGION_MAP[region].keys():
        city = message.text
        user_data[uid]["city"] = city

        kb = ReplyKeyboardBuilder()
        for mahalla in REGION_MAP[region][city].keys():
            kb.button(text=mahalla)
        kb.adjust(2)

        await message.answer(
            f"🌆 Город <b>{city}</b> выбран.\nТеперь выберите махаллю:",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )
        return

    # Проверка, выбран ли город
    city = user_data[uid].get("city")
    if not city:
        return await message.answer("Сначала выберите город.")

    # Выбор махалли
    if message.text in REGION_MAP[region][city].keys():
        mahalla = message.text
        user_data[uid]["mahalla"] = mahalla
        user_data[uid]["attachments"] = []

        await message.answer(
            f"🏘️ Махалля <b>{mahalla}</b> выбрана.\n"
            "Теперь отправьте текст, фото или локацию.\n"
            "Когда будете готовы — нажмите <b>Отправить</b>",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Отправить")]],
                resize_keyboard=True
            )
        )
        return

    # Отправка данных участковому
    if message.text == "Отправить":
        mahalla = user_data[uid].get("mahalla")
        if not mahalla:
            return await message.answer("Сначала выберите махаллю.")

        chat_id = REGION_MAP[region][city][mahalla]  # ID участкового
        attachments = user_data[uid].get("attachments", [])

        if not attachments:
            return await message.answer("Вы не отправили ни текст, ни фото, ни локацию.")

        # Заголовок сообщения участковому
        await bot.send_message(
            chat_id,
            f"📩 Новое сообщение от гражданина:\n\n"
            f"🌍 Область: {region}\n"
            f"🏙️ Город: {city}\n"
            f"🏘️ Махалля: {mahalla}\n"
            f"👤 Пользователь: @{message.from_user.username or 'аноним'}"
        )

        # Отправляем вложения
        for item in attachments:
            if item["type"] == "text":
                await bot.send_message(chat_id, item["data"])
            elif item["type"] == "photo":
                await bot.send_photo(chat_id, item["data"])
            elif item["type"] == "location":
                await bot.send_location(chat_id, item["lat"], item["lon"])

        await message.answer(
            "✅ Сообщение успешно отправлено участковому!",
            reply_markup=types.ReplyKeyboardRemove()
        )

        del user_data[uid]
        return

    # Добавление вложений
    if message.photo:
        user_data[uid]["attachments"].append({
            "type": "photo",
            "data": message.photo[-1].file_id
        })
        return await message.answer("📷 Фото добавлено!")

    if message.location:
        user_data[uid]["attachments"].append({
            "type": "location",
            "lat": message.location.latitude,
            "lon": message.location.longitude
        })
        return await message.answer("📍 Локация добавлена!")

    # Обычный текст
    user_data[uid]["attachments"].append({
        "type": "text",
        "data": message.text
    })
    await message.answer("📝 Текст добавлен.")


# --------------------- ЗАПУСК ----------------------

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

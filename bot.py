import os
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router

logging.basicConfig(level=logging.INFO)

# -------------------------
#  TOKEN
# -------------------------
TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
rt = Router()
dp.include_router(rt)

# -------------------------
#  ЗАГРУЗКА РЕГИОНОВ
# -------------------------
with open("mapping.json", "r", encoding="utf-8") as f:
    REGION_MAP = json.load(f)

# -------------------------
#  FSM
# -------------------------
class Form(StatesGroup):
    region = State()
    district = State()
    village = State()
    content = State()

# Временное хранилище вложений
user_data = {}

# -------------------------
#  КНОПКИ
# -------------------------

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📨 Отправить обращение")],
    ],
    resize_keyboard=True
)

def make_kb(items):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=item)] for item in items],
        resize_keyboard=True
    )

# -------------------------
#  START
# -------------------------
@rt.message(Command("start"))
async def start_cmd(message: types.Message):
    user_data[message.from_user.id] = {}
    await message.answer("Выберите область:", reply_markup=make_kb(list(REGION_MAP.keys())))
    await dp.fsm.set_state(message.from_user.id, Form.region)

# -------------------------
#  ВЫБОР ОБЛАСТИ
# -------------------------
@rt.message(Form.region)
async def choose_region(message: types.Message, state: FSMContext):
    region = message.text
    if region not in REGION_MAP:
        return await message.answer("Неверная область, попробуйте снова.")

    user_data[message.from_user.id] = {"region": region}
    await state.set_state(Form.district)
    await message.answer("Теперь выберите район:", reply_markup=make_kb(list(REGION_MAP[region].keys())))

# -------------------------
#  ВЫБОР РАЙОНА
# -------------------------
@rt.message(Form.district)
async def choose_district(message: types.Message, state: FSMContext):
    region = user_data[message.from_user.id]["region"]
    district = message.text

    if district not in REGION_MAP[region]:
        return await message.answer("Неверный район, попробуйте снова.")

    user_data[message.from_user.id]["district"] = district
    villages = REGION_MAP[region][district]

    await state.set_state(Form.village)
    await message.answer("Выберите махаллю:", reply_markup=make_kb(villages))

# -------------------------
#  ВЫБОР МАХАЛЛИ
# -------------------------
@rt.message(Form.village)
async def choose_village(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    region = user_data[uid]["region"]
    district = user_data[uid]["district"]
    village = message.text

    if village not in REGION_MAP[region][district]:
        return await message.answer("Неверная махалля, попробуйте снова.")

    user_data[uid]["village"] = village
    user_data[uid]["attachments"] = []

    await state.set_state(Form.content)
    await message.answer(
        "Отправьте текст, фото, видео, голосовое или локацию.\n"
        "Когда будете готовы — нажмите «Отправить».",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отправить")]],
            resize_keyboard=True
        )
    )

# -------------------------
#  СБОР ВЛОЖЕНИЙ
# -------------------------
@rt.message(Form.content)
async def collect_content(message: types.Message, state: FSMContext):
    uid = message.from_user.id

    # Если нажато "Отправить"
    if message.text == "Отправить":
        attachments = user_data[uid]["attachments"]

        if not attachments:
            return await message.answer("Вы не отправили ни текста, ни медиа.")

        region = user_data[uid]["region"]
        district = user_data[uid]["district"]
        village = user_data[uid]["village"]

        summary = (
            f"Новое обращение:\n\n"
            f"📍 Область: {region}\n"
            f"📍 Район: {district}\n"
            f"📍 Махалля: {village}\n\n"
            f"Вложения: {len(attachments)} шт."
        )

        await message.answer(summary)

        # Отправляем назад пользователю (чтобы убедился, что всё собрано)
        for att in attachments:
            if att["type"] == "text":
                await message.answer(att["data"])
            elif att["type"] == "photo":
                await message.answer_photo(att["data"])
            elif att["type"] == "video":
                await message.answer_video(att["data"])
            elif att["type"] == "voice":
                await message.answer_voice(att["data"])
            elif att["type"] == "location":
                await message.answer_location(att["lat"], att["lon"])

        await state.clear()
        return await message.answer("Готово!", reply_markup=main_kb)

    # ---- ТЕКСТ ----
    if message.text and message.text != "Отправить":
        user_data[uid]["attachments"].append({
            "type": "text",
            "data": message.text
        })
        return await message.answer("Текст добавлен.")

    # ---- ФОТО ----
    if message.photo:
        user_data[uid]["attachments"].append({
            "type": "photo",
            "data": message.photo[-1].file_id
        })
        return await message.answer("Фото добавлено.")

    # ---- ВИДЕО ----
    if message.video:
        user_data[uid]["attachments"].append({
            "type": "video",
            "data": message.video.file_id
        })
        return await message.answer("Видео добавлено.")

    # ---- ГОЛОСОВЫЕ ----
    if message.voice:
        user_data[uid]["attachments"].append({
            "type": "voice",
            "data": message.voice.file_id
        })
        return await message.answer("Голосовое сообщение добавлено.")

    # ---- ЛОКАЦИЯ ----
    if message.location:
        user_data[uid]["attachments"].append({
            "type": "location",
            "lat": message.location.latitude,
            "lon": message.location.longitude
        })
        return await message.answer("Локация добавлена.")

    await message.answer("Этот тип сообщения не поддерживается.")

# -------------------------
#  ЗАПУСК БОТА
# -------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

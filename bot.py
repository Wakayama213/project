import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_ID, PAYMENT_GROUP_ID
from database import (
    init_db, add_user, get_user, is_subscribed,
    extend_subscription, create_payment, confirm_payment,
    get_active_subscribers,
)
import texts
import keyboards as kb

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Кто в режиме ожидания скрина оплаты
waiting_for_screenshot = set()

# Кто собирает скрины для задания
task_screenshots = {}   # {user_id: [file_id, file_id, ...]}


# ─────────────── /start ───────────────

@dp.message(CommandStart())
async def cmd_start(message: Message):
    add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await message.answer(
        texts.START.format(name=message.from_user.first_name),
        reply_markup=kb.main_menu(),
    )


# ─────────────── Меню ───────────────

@dp.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    task_screenshots.pop(call.from_user.id, None)
    await call.message.edit_text(
        texts.START.format(name=call.from_user.first_name),
        reply_markup=kb.main_menu(),
    )


@dp.callback_query(F.data == "how")
async def cb_how(call: CallbackQuery):
    await call.message.edit_text(
        texts.HOW_IT_WORKS,
        reply_markup=kb.back_to_menu(),
    )


@dp.callback_query(F.data == "example")
async def cb_example(call: CallbackQuery):
    await call.message.edit_text(
        texts.EXAMPLE,
        reply_markup=kb.back_to_menu(),
    )


# ─────────────── Подписка платная ───────────────

@dp.callback_query(F.data == "my_sub")
async def cb_my_sub(call: CallbackQuery):
    user = get_user(call.from_user.id)
    if is_subscribed(call.from_user.id):
        paid_until = datetime.fromisoformat(user["paid_until"])
        days_left = (paid_until - datetime.now()).days
        text = texts.SUB_ACTIVE.format(
            date=paid_until.strftime("%d.%m.%Y"),
            days=days_left,
        )
    else:
        text = texts.NO_SUB
    await call.message.edit_text(text, reply_markup=kb.back_to_menu())


@dp.callback_query(F.data == "subscribe")
async def cb_subscribe(call: CallbackQuery):
    if is_subscribed(call.from_user.id):
        await call.answer("У вас уже есть активная подписка ✅", show_alert=True)
        return
    await call.message.edit_text(
        texts.SUBSCRIBE.format(user_id=call.from_user.id),
        reply_markup=kb.payment_keyboard(),
    )


@dp.callback_query(F.data == "paid")
async def cb_paid(call: CallbackQuery):
    waiting_for_screenshot.add(call.from_user.id)
    await call.message.edit_text(
        texts.PAID_WAIT,
        reply_markup=kb.after_paid_keyboard(),
    )
    await call.answer()


# ─────────────── Подписка за услугу ───────────────

@dp.callback_query(F.data == "task_sub")
async def cb_task_sub(call: CallbackQuery):
    if is_subscribed(call.from_user.id):
        await call.answer("У вас уже есть активная подписка ✅", show_alert=True)
        return
    await call.message.edit_text(
        texts.TASK_INTRO,
        reply_markup=kb.task_start_keyboard(),
    )


@dp.callback_query(F.data == "task_send")
async def cb_task_send(call: CallbackQuery):
    task_screenshots[call.from_user.id] = []
    await call.message.edit_text(
        texts.TASK_WAIT,
        reply_markup=kb.task_cancel_keyboard(),
    )
    await call.answer()


@dp.callback_query(F.data == "task_finish")
async def cb_task_finish(call: CallbackQuery):
    user_id = call.from_user.id
    photos = task_screenshots.pop(user_id, [])

    if not photos:
        await call.answer(
            "Вы не отправили ни одного скриншота",
            show_alert=True,
        )
        return

    await send_task_request(
        user_id=user_id,
        username=call.from_user.username,
        first_name=call.from_user.first_name,
        photos=photos,
    )

    await call.message.edit_text(
        texts.TASK_FINISHED,
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


# ─────────────── Заявка на оплату ───────────────

async def send_payment_request(
    user_id: int,
    username: str | None,
    first_name: str,
    photo_file_id: str | None,
    from_chat_id: int,
):
    payment_id = create_payment(user_id)

    caption = (
        f"💰 <b>Новая оплата</b>\n\n"
        f"👤 {first_name} (@{username or 'без username'})\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🧾 Платёж #{payment_id}\n"
        f"📎 Скриншот: {'есть' if photo_file_id else 'нет'}\n\n"
        f"<i>Кто угодно из группы может подтвердить или отклонить.</i>"
    )

    try:
        if photo_file_id:
            await bot.send_photo(
                PAYMENT_GROUP_ID,
                photo=photo_file_id,
                caption=caption,
                reply_markup=kb.admin_confirm(user_id, payment_id),
            )
        else:
            await bot.send_message(
                PAYMENT_GROUP_ID,
                caption,
                reply_markup=kb.admin_confirm(user_id, payment_id),
            )
    except Exception as e:
        logging.error(f"Не удалось отправить в группу: {e}")
        try:
            if photo_file_id:
                await bot.send_photo(
                    ADMIN_ID,
                    photo=photo_file_id,
                    caption=caption + "\n\n⚠️ <i>В группу не ушло.</i>",
                    reply_markup=kb.admin_confirm(user_id, payment_id),
                )
            else:
                await bot.send_message(
                    ADMIN_ID,
                    caption + "\n\n⚠️ <i>В группу не ушло.</i>",
                    reply_markup=kb.admin_confirm(user_id, payment_id),
                )
        except Exception as e2:
            logging.error(f"Резервная отправка не удалась: {e2}")


# ─────────────── Заявка на подписку за услугу ───────────────

async def send_task_request(
    user_id: int,
    username: str | None,
    first_name: str,
    photos: list[str],
):
    payment_id = create_payment(user_id)
    total = len(photos)

    caption = (
        f"🎁 <b>Подписка за услугу</b>\n\n"
        f"👤 {first_name} (@{username or 'без username'})\n"
        f"🆔 <code>{user_id}</code>\n"
        f"🧾 Заявка #{payment_id}\n"
        f"📸 Скриншотов: <b>{total}</b>\n\n"
        f"<i>Проверьте комментарии и подтвердите или отклоните.</i>"
    )

    try:
        if total == 1:
            await bot.send_photo(
                PAYMENT_GROUP_ID,
                photo=photos[0],
                caption=caption,
                reply_markup=kb.admin_confirm(user_id, payment_id),
            )
        else:
            # Отправляем альбомом до 10 фото, потом — остальные по одному
            first_batch = photos[:10]
            media = [InputMediaPhoto(media=f) for f in first_batch]
            media[0].caption = caption
            media[0].parse_mode = ParseMode.HTML

            await bot.send_media_group(PAYMENT_GROUP_ID, media=media)

            # Кнопки — отдельным сообщением, потому что у media_group нет reply_markup
            await bot.send_message(
                PAYMENT_GROUP_ID,
                f"⬆️ Заявка #{payment_id} от {first_name}. "
                f"Скриншотов: {total}.",
                reply_markup=kb.admin_confirm(user_id, payment_id),
            )

            # Остальные фото (если больше 10)
            for f in photos[10:]:
                try:
                    await bot.send_photo(PAYMENT_GROUP_ID, photo=f)
                    await asyncio.sleep(0.05)
                except Exception as e:
                    logging.error(f"Не удалось отправить доп. фото: {e}")

    except Exception as e:
        logging.error(f"Не удалось отправить задание в группу: {e}")
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🎁 <b>Заявка за услугу</b>\n\n"
                f"👤 {first_name} (@{username or 'без username'})\n"
                f"🆔 <code>{user_id}</code>\n"
                f"🧾 Заявка #{payment_id}\n"
                f"📸 Скриншотов: <b>{total}</b>\n\n"
                f"⚠️ <i>В группу не ушло. Первое фото ниже.</i>",
                reply_markup=kb.admin_confirm(user_id, payment_id),
            )
            await bot.send_photo(ADMIN_ID, photo=photos[0])
        except Exception as e2:
            logging.error(f"Резервная отправка не удалась: {e2}")


# ─────────────── Приём фото (оплата или задание) ───────────────

@dp.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id

    # Сценарий 1: подписка за услугу — собираем скрины
    if user_id in task_screenshots:
        task_screenshots[user_id].append(message.photo[-1].file_id)
        count = len(task_screenshots[user_id])
        await message.answer(
            f"📸 Принято: <b>{count}</b>.\n\n"
            f"Продолжайте или нажмите <b>«🏁 Завершить и отправить»</b>.",
        )
        return

    # Сценарий 2: оплата со скрином
    if user_id in waiting_for_screenshot:
        waiting_for_screenshot.discard(user_id)
        await send_payment_request(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            photo_file_id=message.photo[-1].file_id,
            from_chat_id=message.chat.id,
        )
        await message.answer(
            "📨 Скриншот получен! Ожидайте подтверждения — обычно 1–2 часа.",
            reply_markup=kb.back_to_menu(),
        )


# ─────────────── Заявка без скрина ───────────────

@dp.callback_query(F.data.in_({"paid_no_photo", "send_no_photo"}))
async def cb_no_photo(call: CallbackQuery):
    await send_payment_request(
        user_id=call.from_user.id,
        username=call.from_user.username,
        first_name=call.from_user.first_name,
        photo_file_id=None,
        from_chat_id=call.message.chat.id,
    )
    waiting_for_screenshot.discard(call.from_user.id)
    await call.message.edit_text(
        texts.PAID_NO_PHOTO,
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


# ─────────────── Текст вместо скрина ───────────────

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    user_id = message.from_user.id

    # Если собирает скрины для задания — текст не считаем заявкой
    if user_id in task_screenshots:
        return

    if user_id not in waiting_for_screenshot:
        return

    waiting_for_screenshot.discard(user_id)
    await send_payment_request(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        photo_file_id=None,
        from_chat_id=message.chat.id,
    )
    await message.answer(
        texts.PAID_NO_PHOTO,
        reply_markup=kb.back_to_menu(),
    )


# ─────────────── Подтверждение из группы ───────────────

@dp.callback_query(F.data.startswith("confirm_"))
async def cb_confirm(call: CallbackQuery):
    if call.message.chat.id != PAYMENT_GROUP_ID and call.from_user.id != ADMIN_ID:
        await call.answer("Нет доступа", show_alert=True)
        return

    _, user_id, payment_id = call.data.split("_")
    user_id, payment_id = int(user_id), int(payment_id)

    until = extend_subscription(user_id)
    confirm_payment(payment_id)

    confirmer = call.from_user.first_name or "админ"

    try:
        if call.message.caption:
            await call.message.edit_caption(
                caption=call.message.caption + f"\n\n✅ <b>Подтверждено</b> ({confirmer})",
                reply_markup=None,
            )
        else:
            await call.message.edit_text(
                text=(call.message.text or "") + f"\n\n✅ <b>Подтверждено</b> ({confirmer})",
                reply_markup=None,
            )
    except Exception as e:
        logging.error(f"Не удалось обновить сообщение: {e}")

    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Подписка активирована!</b>\n\n"
            f"📅 Действует до: <b>{until.strftime('%d.%m.%Y')}</b>\n\n"
            "Прогнозы будут приходить автоматически.",
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить {user_id}: {e}")

    await call.answer("Подписка активирована")


@dp.callback_query(F.data.startswith("reject_"))
async def cb_reject(call: CallbackQuery):
    if call.message.chat.id != PAYMENT_GROUP_ID and call.from_user.id != ADMIN_ID:
        await call.answer("Нет доступа", show_alert=True)
        return

    _, user_id, payment_id = call.data.split("_")
    user_id = int(user_id)

    confirmer = call.from_user.first_name or "админ"

    try:
        if call.message.caption:
            await call.message.edit_caption(
                caption=call.message.caption + f"\n\n❌ <b>Отклонено</b> ({confirmer})",
                reply_markup=None,
            )
        else:
            await call.message.edit_text(
                text=(call.message.text or "") + f"\n\n❌ <b>Отклонено</b> ({confirmer})",
                reply_markup=None,
            )
    except Exception as e:
        logging.error(f"Не удалось обновить сообщение: {e}")

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Заявка не подтверждена.</b>\n\n"
            "Если вы уверены, что выполнили условия — напишите в поддержку.",
        )
    except Exception as e:
        logging.error(f"Не удалось уведомить {user_id}: {e}")

    await call.answer("Отклонено")


# ─────────────── Рассылка прогноза ───────────────

@dp.message(Command("send"))
async def cmd_send(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.answer(
            "⚠️ Ответьте на сообщение с картинкой прогноза и напишите /send"
        )
        return

    source = message.reply_to_message
    file_id = source.photo[-1].file_id
    caption = source.caption or "📊 Новый прогноз"

    subscribers = get_active_subscribers()
    sent, failed = 0, 0

    for user_id in subscribers:
        try:
            await bot.send_photo(user_id, photo=file_id, caption=caption)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Разослано: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>"
    )


# ─────────────── Запуск ───────────────

async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
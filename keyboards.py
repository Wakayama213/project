from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оформить подписку", callback_data="subscribe")],
        [InlineKeyboardButton(text="🎁 Подписка за услугу", callback_data="task_sub")],
        [InlineKeyboardButton(text="📈 Моя подписка", callback_data="my_sub")],
        [InlineKeyboardButton(text="ℹ️ Как это работает", callback_data="how")],
        [InlineKeyboardButton(text="📊 Пример прогноза", callback_data="example")],
    ])


def back_to_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu")],
    ])


def payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил (со скрином)", callback_data="paid")],
        [InlineKeyboardButton(text="📤 Отправить заявку без скрина", callback_data="paid_no_photo")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu")],
    ])


def after_paid_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить заявку без скрина", callback_data="send_no_photo")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu")],
    ])


def task_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Отправить скриншоты", callback_data="task_send")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu")],
    ])


def task_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏁 Завершить и отправить", callback_data="task_finish")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu")],
    ])


def admin_confirm(user_id, payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"confirm_{user_id}_{payment_id}",
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"reject_{user_id}_{payment_id}",
            ),
        ],
    ])
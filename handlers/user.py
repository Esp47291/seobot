# -*- coding: utf-8 -*-
"""Пользовательские хендлеры SeoJob / Отзовик."""
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS, SUPPORT_URL
from database import (
    AttemptRepository,
    BalanceRepository,
    ReferralRepository,
    SettingsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.admin import moderation_kb, withdraw_kb
from keyboards.user import cancel_attempt_kb, main_menu, operations_history_kb, platforms_kb, task_card_kb
from utils.fsm import UserFSM

BLOCKED_TEXT = (
    "вы заблокированы по решению администрации, для разблокировки обратитесь к владельцу - @Exxzest"
)

router = Router(name="user")


async def _show_task_card(
    message: Message,
    state: FSMContext,
    task_ids: list[int],
    index: int,
    session,
    city_display: str,
):
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_ids[index])
    if not task:
        await message.answer("Задание не найдено.")
        return
    await state.update_data(task_ids=task_ids, task_index=index, city_display=city_display)
    text = (
        f"Платформа: {task.platform}\n"
        f"Город: {city_display}\n"
        f"Сфера: {task.sphere}\n"
        f"Вознаграждение: {float(task.price):.2f} руб."
    )
    await message.answer(text, reply_markup=task_card_kb(task.id))


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, **data):
    await state.clear()
    session = data["session"]
    user_repo = UserRepository(session)
    settings_repo = SettingsRepository(session)
    user, created = await user_repo.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    settings = await settings_repo.get()
    if user.is_blocked:
        await message.answer(BLOCKED_TEXT, reply_markup=main_menu())
        return

    # Deep-link реферал: /start <referrer_user_id>
    # Telegram deep link вида: https://t.me/<bot>?start=<payload>
    # приходит как команду "/start <payload>"
    try:
        text = message.text or ""
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            payload = parts[1].strip()
            if payload.isdigit():
                referrer_id = int(payload)
                # Ставим 1 уровень только при первом входе пользователя в бота
                # (иначе он мог уже раньше зайти без реферала).
                if created:
                    ref_repo = ReferralRepository(session)
                    await ref_repo.set_referrer_if_first_time(
                        referee_user_id=message.from_user.id,
                        referrer_user_id=referrer_id,
                    )
    except Exception:
        # рефералы — бонус. Ошибки парсинга не ломают регистрацию пользователя
        pass

    await message.answer(settings.welcome_text, reply_markup=main_menu())


@router.message(F.text == "✍️ Приступить к заданию")
async def begin_tasks(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    task_repo = TaskItemRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    if not user:
        await message.answer("Нажмите /start.")
        return
    if not user.city:
        await state.set_state(UserFSM.choosing_city)
        await message.answer("Напишите ваш город:")
        return
    platforms = await task_repo.get_platforms_by_city(user.city)
    if not platforms:
        await message.answer("Для вашего города пока нет активных заданий.")
        return
    await state.set_state(UserFSM.choosing_platform)
    await message.answer("Выберите платформу:", reply_markup=platforms_kb(platforms))


@router.message(UserFSM.choosing_city, F.text)
async def choose_city(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    task_repo = TaskItemRepository(session)
    await user_repo.set_city(message.from_user.id, message.text.strip())
    platforms = await task_repo.get_platforms_by_city(message.text.strip())
    if not platforms:
        await state.clear()
        await message.answer("Город сохранен, но активных заданий пока нет.", reply_markup=main_menu())
        return
    await state.set_state(UserFSM.choosing_platform)
    await message.answer("Выберите платформу:", reply_markup=platforms_kb(platforms))


@router.callback_query(F.data.startswith("platform:"))
async def choose_platform(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    user_repo = UserRepository(session)
    task_repo = TaskItemRepository(session)
    user = await user_repo.get_by_user_id(cb.from_user.id)
    platform = cb.data.split(":", 1)[1]
    tasks = await task_repo.get_active_for_city_platform(user.city, platform)
    if not tasks:
        await cb.message.answer("По этой платформе нет активных заданий.")
        return
    task_ids = [t.id for t in tasks]
    await _show_task_card(cb.message, state, task_ids, 0, session, city_display=user.city or "-")


@router.callback_query(F.data.startswith("next_task:"))
async def next_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    state_data = await state.get_data()
    task_ids = state_data.get("task_ids", [])
    if not task_ids:
        return
    new_index = (state_data.get("task_index", 0) + 1) % len(task_ids)
    city_display = state_data.get("city_display") or "-"
    await _show_task_card(cb.message, state, task_ids, new_index, session, city_display=city_display)


@router.callback_query(F.data.startswith("skip_task:"))
async def skip_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer("Скрыто в текущей сессии")
    session = data["session"]
    state_data = await state.get_data()
    task_ids = state_data.get("task_ids", [])
    current_id = int(cb.data.split(":")[1])
    filtered = [tid for tid in task_ids if tid != current_id]
    if not filtered:
        await cb.message.answer("Больше заданий нет.")
        return
    city_display = state_data.get("city_display") or "-"
    await _show_task_card(cb.message, state, filtered, 0, session, city_display=city_display)


@router.callback_query(F.data.startswith("start_task:"))
async def start_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    task_id = int(cb.data.split(":")[1])
    task = await task_repo.get_by_id(task_id)
    if not task or not task.is_active:
        await cb.message.answer("Задание недоступно.")
        return
    attempt = await attempt_repo.create(cb.from_user.id, task_id)
    await state.set_state(UserFSM.waiting_account_screenshot)
    await state.update_data(attempt_id=attempt.id)
    await cb.message.answer(
        f"🔍 Этап 1/3: Для допуска к заданию пришлите скриншот вашего профиля на {task.platform}, "
        "где видно ваш никнейм и дату последнего отзыва."
    )


@router.message(UserFSM.waiting_account_screenshot, F.photo)
async def got_account_screenshot(message: Message, state: FSMContext, **data):
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    state_data = await state.get_data()
    attempt = await attempt_repo.get_by_id(state_data.get("attempt_id"))
    if not attempt:
        await state.clear()
        return
    file_id = message.photo[-1].file_id
    await attempt_repo.set_account_screenshot(attempt.id, file_id)
    task = await task_repo.get_by_id(attempt.task_item_id)
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    city_display = user.city if user and user.city else "-"
    admin_text = (
        f"🆕 Запрос на задание от @{message.from_user.username or message.from_user.id}\n"
        f"Задание: {task.platform} / {task.sphere} / {city_display}\n"
        f"Цена: {float(task.price):.2f} руб."
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(
                admin_id,
                file_id,
                caption=admin_text,
                reply_markup=moderation_kb(attempt.id, "pre"),
            )
        except Exception:
            pass
    await message.answer("Скриншот отправлен на модерацию. Ожидайте решение.")


@router.message(UserFSM.waiting_review_screenshot, F.photo)
async def got_review_screenshot(message: Message, state: FSMContext, **data):
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("attempt_id")
    attempt = await attempt_repo.submit_review(attempt_id, message.photo[-1].file_id)
    if not attempt:
        await state.clear()
        return
    await state.clear()
    await message.answer(
        "✅ Скриншот получен. Ожидайте проверки результата. Максимальный срок проверки: 3 дня.",
        reply_markup=main_menu(),
    )


@router.message(F.photo)
async def got_review_screenshot_without_state(message: Message, **data):
    """Поддержка кейса, когда админ допустил пользователя позже, без активного FSM-контекста."""
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt = await attempt_repo.get_last_by_user_status(message.from_user.id, "approved")
    if not attempt:
        return
    await attempt_repo.submit_review(attempt.id, message.photo[-1].file_id)
    await message.answer(
        "✅ Скриншот получен. Ожидайте проверки результата. Максимальный срок проверки: 3 дня.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "cancel_attempt")
async def cancel_attempt(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("attempt_id")
    if attempt_id:
        await attempt_repo.cancel(attempt_id)
    await state.clear()
    await cb.message.answer("Попытка отменена.", reply_markup=main_menu())


@router.message(F.text == "💰 Личный кабинет / Баланс")
async def cabinet(message: Message, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    attempt_repo = AttemptRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    completed = await attempt_repo.completed_count_by_user(message.from_user.id)
    await message.answer(
        f"Ваш ID: {user.user_id}\n"
        f"Username: @{user.username or '-'}\n"
        f"Баланс: {float(user.balance):.2f} руб.\n"
        f"Выполнено заданий: {completed}",
        reply_markup=operations_history_kb(),
    )


@router.callback_query(F.data == "cabinet_history")
async def cabinet_history(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    balance_repo = BalanceRepository(session)
    ops = await balance_repo.get_last_operations(cb.from_user.id)
    if not ops:
        await cb.message.answer("История операций пуста.")
        return
    text = "Последние операции:\n\n" + "\n".join(
        [f"{o.created_at:%d.%m %H:%M} | {o.operation_type} | {float(o.amount):+.2f} руб." for o in ops]
    )
    await cb.message.answer(text)


@router.message(F.text == "💸 Вывести средства")
async def withdraw_start(message: Message, state: FSMContext, **data):
    session = data["session"]
    settings_repo = SettingsRepository(session)
    user_repo = UserRepository(session)
    settings = await settings_repo.get()
    user = await user_repo.get_by_user_id(message.from_user.id)
    if Decimal(user.balance) < Decimal(settings.min_withdraw_amount):
        await message.answer(f"Минимальная сумма вывода — {settings.min_withdraw_amount} рублей.")
        return
    await state.set_state(UserFSM.waiting_withdraw_amount)
    await message.answer(f"Введите сумму для вывода (доступно {float(user.balance):.2f} руб.):")


@router.message(UserFSM.waiting_withdraw_amount, F.text)
async def withdraw_amount(message: Message, state: FSMContext, **data):
    session = data["session"]
    settings_repo = SettingsRepository(session)
    user_repo = UserRepository(session)
    settings = await settings_repo.get()
    user = await user_repo.get_by_user_id(message.from_user.id)
    try:
        amount = Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Введите число.")
        return
    if amount < settings.min_withdraw_amount or amount > Decimal(user.balance):
        await message.answer("Некорректная сумма.")
        return
    await state.update_data(withdraw_amount=float(amount))
    await state.set_state(UserFSM.waiting_withdraw_requisites)
    await message.answer("Введите ваши платежные реквизиты (номер карты, кошелек и т.д.):")


@router.message(UserFSM.waiting_withdraw_requisites, F.text)
async def withdraw_requisites(message: Message, state: FSMContext, **data):
    session = data["session"]
    wd_repo = WithdrawalRepository(session)
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    amount = (await state.get_data()).get("withdraw_amount")
    if not amount:
        await state.clear()
        return
    ok = await user_repo.sub_balance(message.from_user.id, amount)
    if not ok:
        await state.clear()
        await message.answer("Недостаточно средств.", reply_markup=main_menu())
        return
    wd = await wd_repo.create(message.from_user.id, amount, message.text.strip())
    await bal_repo.add_operation(message.from_user.id, -amount, "withdraw_request", f"Заявка #{wd.id}")
    await state.clear()
    await message.answer(f"✅ Заявка на вывод {amount:.2f} руб. создана. Ожидайте выплаты.", reply_markup=main_menu())
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"💰 Заявка на вывод!\n"
                f"От: @{message.from_user.username or message.from_user.id} (ID: {message.from_user.id})\n"
                f"Сумма: {amount:.2f} руб.\n"
                f"Реквизиты: {message.text.strip()}",
                reply_markup=withdraw_kb(wd.id),
            )
        except Exception:
            pass


@router.message(F.text == "👥 Реферальная программа")
async def referral_program(message: Message, **data):
    session = data["session"]
    ref_repo = ReferralRepository(session)
    income_total = await ref_repo.get_total_referral_income(message.from_user.id)

    me = await message.bot.get_me()
    bot_username = me.username or ""
    referral_link = (
        f"https://t.me/{bot_username}?start={message.from_user.id}" if bot_username else "—"
    )

    await message.answer(
        "РЕФЕРАЛЬНАЯ ПРОГРАММА\n\n"
        "❗️Реферал 1 уровня - это человек, который впервые заходит в бота по вашей ссылке. "
        "Когда человек зайдёт в бота по вашей ссылке, он навсегда становится вашим рефералом 1 уровня.\n"
        "- Когда ваш Реферал 1 уровня получает выплату за задание вы получаете 20% от его заработка на ваш баланс.\n\n"
        "❗️Реферал 2 уровня - это тот человек, который впервые заходит в бота по ссылке вашего Реферала 1 уровня.\n"
        "- Когда ваш Реферал 2 уровня получает выплату за задание вы получаете 5% от его заработка на ваш баланс.\n\n"
        "✅ Приглашайте новых пользователей и получайте пассивный доход от их заработка!\n\n"
        f"👁‍🗨 Ссылка для привлечения рефералов: {referral_link}\n\n"
        f"Доход заработанный с рефераллов всего: {income_total:.2f} руб."
    )


@router.message(F.text == "🆘 Помощь")
async def help_menu(message: Message, **data):
    session = data["session"]
    settings_repo = SettingsRepository(session)
    settings = await settings_repo.get()
    await message.answer(f"{settings.help_text}\n{SUPPORT_URL}")


@router.callback_query(F.data == "to_menu")
async def to_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Главное меню:", reply_markup=main_menu())


@router.message(UserFSM.waiting_account_screenshot)
@router.message(UserFSM.waiting_review_screenshot)
async def wrong_photo(message: Message):
    await message.answer("Пожалуйста, отправьте скриншот изображением.")

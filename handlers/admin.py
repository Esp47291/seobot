# -*- coding: utf-8 -*-
"""Админ-хендлеры для SeoJob / Отзовик."""
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sqlalchemy import select

from database.models import User
from database import (
    AttemptRepository,
    BalanceRepository,
    ReferralRepository,
    SettingsRepository,
    StatsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.admin import admin_main, users_manage_kb, withdraw_kb
from keyboards.user import cancel_attempt_kb
from utils.fsm import AdminFSM

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Админ-панель:", reply_markup=admin_main())


@router.callback_query(F.data == "admin:tasks")
async def tasks_menu(cb: CallbackQuery, **data):
    await cb.answer()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "⚙️ Управление заданиями",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить задание", callback_data="admin:tasks_add")],
                [InlineKeyboardButton(text="🗑️ Удалить задание", callback_data="admin:tasks_delete")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")],
            ]
        ),
    )


@router.callback_query(F.data == "admin:back_main")
async def admin_back_main(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Админ-панель:", reply_markup=admin_main())


@router.callback_query(F.data == "admin:tasks_add")
async def tasks_add_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "Шаг 1/4.\nВыберите платформу:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Яндекс карты", callback_data="admin:tasks_plat:yandex")],
                [InlineKeyboardButton(text="2ГИС", callback_data="admin:tasks_plat:2gis")],
                [InlineKeyboardButton(text="Google карты", callback_data="admin:tasks_plat:google")],
                [InlineKeyboardButton(text="Другая платформа", callback_data="admin:tasks_plat:other")],
            ]
        ),
    )


@router.callback_query(F.data == "admin:tasks_plat:yandex")
async def tasks_plat_yandex(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_price)
    await state.update_data(platform="Яндекс карты")
    await cb.message.answer("Шаг 2/4.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:2gis")
async def tasks_plat_2gis(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_price)
    await state.update_data(platform="2ГИС")
    await cb.message.answer("Шаг 2/4.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:google")
async def tasks_plat_google(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_price)
    await state.update_data(platform="Google карты")
    await cb.message.answer("Шаг 2/4.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:other")
async def tasks_plat_other(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_platform)
    await cb.message.answer("Шаг 1/4.\nНапишите название платформы.\n\nПример: `Яндекс карты`")


@router.message(AdminFSM.waiting_task_platform, F.text)
async def tasks_add_platform(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    await state.update_data(platform=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_price)
    await message.answer("Шаг 2/4.\nНапишите цену за отзыв (число). Например: 120")


@router.message(AdminFSM.waiting_task_price, F.text)
async def tasks_add_price(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    try:
        price = Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Некорректное число. Повторите: цена за отзыв (например 120).")
        return
    if price <= 0:
        await message.answer("Цена должна быть больше 0.")
        return
    # Проверка минимальной цены по платформе (равную можно, ниже — нельзя)
    session = data["session"]
    settings = await SettingsRepository(session).get()
    d = await state.get_data()
    platform = (d.get("platform") or "").strip()
    min_price = None
    if platform == "Яндекс карты":
        min_price = settings.min_review_price_yandex
    elif platform == "Google карты":
        min_price = settings.min_review_price_google
    elif platform == "2ГИС":
        min_price = settings.min_review_price_2gis

    if min_price is not None and price < min_price:
        await message.answer(f"Минимальная цена для {platform} = {min_price} руб. Ниже нельзя.")
        return

    await state.update_data(price=float(price))
    await state.set_state(AdminFSM.waiting_task_instruction)
    await message.answer("Шаг 3/4.\nНапишите инструкцию для исполнителя.")


@router.message(AdminFSM.waiting_task_instruction, F.text)
async def tasks_add_instruction(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    await state.update_data(instruction_text=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_venue_link)
    await message.answer("Шаг 4/4.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


@router.message(AdminFSM.waiting_task_venue_link, F.text)
async def tasks_add_venue_link(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    session = data["session"]
    d = await state.get_data()
    task_repo = TaskItemRepository(session)

    platform = (d.get("platform") or "").strip()
    instruction_text = (d.get("instruction_text") or "").strip()
    venue_url = message.text.strip()

    if not platform:
        await state.clear()
        await message.answer("Ошибка: платформа не указана.")
        return
    if not instruction_text:
        await state.clear()
        await message.answer("Ошибка: инструкция не указана.")
        return
    if not venue_url.startswith("http"):
        await message.answer("Ссылка должна начинаться с `http`/`https`.")
        return

    price = d.get("price")
    task = await task_repo.create(
        platform=platform,
        city="*",
        sphere="Отзывы",
        price=float(price),
        instruction_url=f"{instruction_text}\n\nСсылка на заведение для отзыва: {venue_url}",
    )
    await state.clear()
    await message.answer(
        f"✅ Задание создано.\nID: {task.id}",
        reply_markup=admin_main(),
    )


@router.callback_query(F.data == "admin:tasks_delete")
async def tasks_delete_menu(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    session = data["session"]
    task_repo = TaskItemRepository(session)
    items = await task_repo.get_all()
    items_sorted = sorted(items, key=lambda x: x.id)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    if not items_sorted:
        await cb.message.answer("Заданий пока нет.", reply_markup=admin_main())
        return

    lines = []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    # кнопки только с цифрами по порядку
    for idx, item in enumerate(items_sorted, start=1):
        label = f"{idx}"
        lines.append(f"{idx}) ID {item.id} | {item.platform} | {float(item.price):.2f} руб. | {'ON' if item.is_active else 'OFF'}")
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"admin:tasks_del:{item.id}")]
        )
    kb.inline_keyboard.append(
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")]
    )

    await cb.message.answer("Выберите задание для удаления:\n\n" + "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("admin:tasks_del:"))
async def tasks_delete_action(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task_id = int(cb.data.split(":")[2])
    await task_repo.delete(task_id)
    await state.clear()
    await cb.message.answer("✅ Задание удалено.")
    # Показать меню удаления повторно
    await tasks_delete_menu(cb, state, **data)


@router.callback_query(F.data == "admin:stats")
async def stats(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    s = await StatsRepository(session).summary()
    await cb.message.answer(
        "Статистика:\n"
        f"Всего пользователей: {s['users_total']}\n"
        f"Новых за 7 дней: {s['users_new_week']}\n"
        f"Выполнено заданий: {s['tasks_completed']}\n"
        f"Всего выплачено: {s['total_paid']:.2f}\n"
        f"Сумма балансов: {s['total_balances']:.2f}"
    )


@router.callback_query(F.data.startswith("admin:allow:"))
async def allow_attempt(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.approve(attempt_id)
    if not attempt:
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    await cb.bot.send_message(
        attempt.user_id,
        f"✅ Вы допущены! Ваша инструкция: {task.instruction_url}\n\n"
        "✍️ Этап 2/3: Напишите отзыв по инструкции. После публикации пришлите в чат скриншот готового отзыва.",
        reply_markup=cancel_attempt_kb(),
    )
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:decline:"))
async def decline_attempt_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    attempt_id = int(cb.data.split(":")[2])
    await state.set_state(AdminFSM.waiting_decline_reason)
    await state.update_data(decline_attempt_id=attempt_id)
    await cb.message.answer("Введите причину отказа:")


@router.message(AdminFSM.waiting_decline_reason, F.text)
async def decline_attempt_finish(message: Message, state: FSMContext, **data):
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("decline_attempt_id")
    attempt = await attempt_repo.decline(attempt_id, message.text.strip())
    await state.clear()
    if attempt:
        await message.bot.send_message(
            attempt.user_id,
            f"❌ Отказ в допуске. Причина: {message.text.strip()}",
        )
    await message.answer("Готово.")


@router.callback_query(F.data.startswith("admin:review_ok:"))
async def review_ok(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    ref_repo = ReferralRepository(session)
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.complete(attempt_id)
    if not attempt:
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    amount = float(task.price)
    await user_repo.add_balance(attempt.user_id, amount)
    await bal_repo.add_operation(attempt.user_id, amount, "task_reward", f"Задание {task.id}")

    # Реферальные начисления (1 уровень: 20%, 2 уровень: 5%)
    ref1_id = await ref_repo.get_referrer_for_referee(attempt.user_id)
    if ref1_id and ref1_id != attempt.user_id:
        comm1 = amount * 0.20
        await user_repo.add_balance(ref1_id, comm1)
        await bal_repo.add_operation(ref1_id, comm1, "referral_commission_l1", f"Комиссия за реферала (задание {task.id})")

        ref2_id = await ref_repo.get_referrer_for_referee(ref1_id)
        if ref2_id and ref2_id != ref1_id and ref2_id != attempt.user_id:
            comm2 = amount * 0.05
            await user_repo.add_balance(ref2_id, comm2)
            await bal_repo.add_operation(ref2_id, comm2, "referral_commission_l2", f"Комиссия за реферала 2 уровня (задание {task.id})")

    await cb.bot.send_message(attempt.user_id, f"✅ Ваш отзыв принят! На баланс зачислено {amount:.2f} руб.")
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:review_bad:"))
async def review_bad_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    attempt_id = int(cb.data.split(":")[2])
    await state.set_state(AdminFSM.waiting_reject_reason)
    await state.update_data(reject_attempt_id=attempt_id)
    await cb.message.answer("Введите причину отклонения:")


@router.message(AdminFSM.waiting_reject_reason, F.text)
async def review_bad_finish(message: Message, state: FSMContext, **data):
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("reject_attempt_id")
    attempt = await attempt_repo.reject(attempt_id, message.text.strip())
    await state.clear()
    if attempt:
        await message.bot.send_message(attempt.user_id, f"❌ Отзыв отклонен. Причина: {message.text.strip()}")
    await message.answer("Готово.")


@router.callback_query(F.data == "admin:withdrawals")
async def withdrawals_list(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    repo = WithdrawalRepository(session)
    items = await repo.get_pending()
    if not items:
        await cb.message.answer("Нет заявок на вывод.")
        return
    for item in items:
        await cb.message.answer(
            f"Заявка #{item.id}\nПользователь: {item.user_id}\nСумма: {float(item.amount):.2f}\nРеквизиты: {item.requisites}",
            reply_markup=withdraw_kb(item.id),
        )


@router.callback_query(F.data.startswith("admin:wd_paid:"))
async def wd_paid(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    wd_repo = WithdrawalRepository(session)
    wd = await wd_repo.mark_paid(int(cb.data.split(":")[2]))
    if wd:
        await cb.bot.send_message(wd.user_id, "✅ Ваша заявка на вывод выплачена.")
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:wd_rej:"))
async def wd_rej(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    wd_repo = WithdrawalRepository(session)
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    wd = await wd_repo.mark_rejected(int(cb.data.split(":")[2]))
    if wd:
        amount = float(wd.amount)
        await user_repo.add_balance(wd.user_id, amount)
        await bal_repo.add_operation(wd.user_id, amount, "withdraw_return", f"Возврат заявки #{wd.id}")
        await cb.bot.send_message(wd.user_id, "❌ Заявка отклонена, сумма возвращена на баланс.")
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "📢 Рассылка",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="массовая рассылка", callback_data="admin:broadcast_all")],
                [
                    InlineKeyboardButton(
                        text="личная рассылка через /sendmessage (айди или юзернейм) (текст сообщения)",
                        callback_data="admin:broadcast_personal",
                    )
                ],
            ]
        ),
    )


@router.message(AdminFSM.waiting_broadcast_content, F.text)
async def broadcast_send(message: Message, state: FSMContext, **data):
    session = data["session"]
    state_data = await state.get_data()
    mode = state_data.get("broadcast_mode")

    if mode == "all":
        text = message.text.strip()
        if not text:
            await message.answer("Текст не может быть пустым.")
            return

        # Отправляем всем активным (не заблокированным) пользователям
        result = await session.execute(select(User).where(User.is_blocked == False))
        users = list(result.scalars().all())
        sent = 0
        for u in users:
            try:
                await message.bot.send_message(u.user_id, text)
                sent += 1
            except Exception:
                pass

        await message.answer(f"Рассылка завершена. Отправлено: {sent}")
        await state.clear()
        return

    if mode == "personal":
        raw = (message.text or "").strip()
        if not raw.startswith("/sendmessage"):
            await message.answer("Используйте формат: /sendmessage <id|@username> <текст>")
            return

        # Пример: /sendmessage 5324231382 Привет
        parts = raw.split(maxsplit=2)
        if len(parts) < 3:
            await message.answer("Формат: /sendmessage <id|@username> <текст>")
            return

        target = parts[1]
        text = parts[2]
        user_repo = UserRepository(session)
        user = await user_repo.get_by_username(target) if target.startswith("@") else await user_repo.get_by_user_id(int(target))
        if not user:
            await message.answer("Пользователь не найден.")
            return

        await message.bot.send_message(user.user_id, text)
        await message.answer("Отправлено пользователю.")
        await state.clear()
        return

    await state.clear()
    await message.answer("Ошибка режима рассылки. Начните заново: admin → Массовая рассылка.")


@router.callback_query(F.data == "admin:broadcast_all")
async def broadcast_all_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_broadcast_content)
    await state.update_data(broadcast_mode="all")
    await cb.message.answer("Отправьте текст рассылки.")


@router.callback_query(F.data == "admin:broadcast_personal")
async def broadcast_personal_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_broadcast_content)
    await state.update_data(broadcast_mode="personal")
    await cb.message.answer("Отправьте сообщение в формате: /sendmessage <id|@username> <текст>")


@router.callback_query(F.data == "admin:users")
async def users_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("👤 Управление пользователями:", reply_markup=users_manage_kb())


@router.callback_query(F.data == "admin:user_block")
async def users_block_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_user_query)
    await state.update_data(admin_user_action="ban")
    await cb.message.answer(
        "Введите команду (строго с пробелами):\n"
        "`/ban <id>` или `/ban <@username>`\n"
        "Пример: `/ban 5324231382`"
    )


@router.callback_query(F.data == "admin:user_unblock")
async def users_unblock_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_user_query)
    await state.update_data(admin_user_action="unban")
    await cb.message.answer(
        "Введите команду (строго с пробелами):\n"
        "`/unban <id>` или `/unban <@username>`\n"
        "Пример: `/unban @someuser`"
    )


@router.callback_query(F.data == "admin:user_balance_add")
async def users_balance_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_balance_change)
    await state.update_data(admin_balance_action="add")
    await cb.message.answer(
        "Введите команду (строго с пробелами):\n"
        "`/balance +100 <id>` или `/balance +100 <@username>`\n"
        "Пример: `/balance +100 @someuser`"
    )


@router.callback_query(F.data == "admin:user_balance_sub")
async def users_balance_sub_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_balance_change)
    await state.update_data(admin_balance_action="sub")
    await cb.message.answer(
        "Введите команду (строго с пробелами):\n"
        "`/balance -100 <id>` или `/balance -100 <@username>`\n"
        "Пример: `/balance -100 5324231382`"
    )


def _parse_target_token(tokens: list[str]) -> str | None:
    if not tokens:
        return None
    first = tokens[0].strip()
    cmd = first.lstrip("/").lower()
    if cmd in {"ban", "unban"}:
        return tokens[1] if len(tokens) >= 2 else None
    if cmd in {"balance"}:
        return tokens[2] if len(tokens) >= 3 else None
    # если команда не указана — считаем, что первый токен и есть target
    return tokens[1] if len(tokens) >= 2 and (tokens[0].startswith("+") or tokens[0].startswith("-")) else tokens[0]


@router.message(AdminFSM.waiting_user_query, F.text)
async def users_block_unblock_finish(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)

    text = (message.text or "").strip()
    tokens = text.split()
    state_data = await state.get_data()
    action = state_data.get("admin_user_action")

    if action not in {"ban", "unban"}:
        await state.clear()
        await message.answer("Ошибка: действие не задано.", reply_markup=users_manage_kb())
        return

    target_token = None
    if tokens:
        first_cmd = tokens[0].lstrip("/").lower()
        if first_cmd in {"ban", "unban"}:
            target_token = tokens[1] if len(tokens) >= 2 else None
        else:
            # разрешим ввод только таргета
            target_token = tokens[0]

    if not target_token:
        await message.answer("Не понял команду. Повторите: /ban <id|@username> или /unban <id|@username>")
        return

    if target_token.startswith("@") or not target_token.isdigit():
        user = await user_repo.get_by_username(target_token)
    else:
        user = await user_repo.get_by_user_id(int(target_token))

    if not user:
        await message.answer("Пользователь не найден. Проверьте ID/username.")
        return

    await user_repo.set_blocked(user.user_id, action == "ban")
    await state.clear()

    await message.answer(
        f"Готово: пользователь {'заблокирован' if action == 'ban' else 'разблокирован'}.\n"
        f"@{user.username or '-'} (ID: {user.user_id})",
        reply_markup=users_manage_kb(),
    )


@router.message(AdminFSM.waiting_balance_change, F.text)
async def users_balance_finish(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)

    text = (message.text or "").strip()
    tokens = text.split()
    state_data = await state.get_data()
    bal_action = state_data.get("admin_balance_action")

    if bal_action not in {"add", "sub"}:
        await state.clear()
        await message.answer("Ошибка: действие не задано.", reply_markup=users_manage_kb())
        return

    # Ожидаем: /balance +100 <target> (или без /balance)
    amount_token = None
    target_token = None
    if tokens and tokens[0].lstrip("/").lower() in {"balance"}:
        if len(tokens) < 3:
            await message.answer("Формат: /balance +100 <id|@username>")
            return
        amount_token = tokens[1]
        target_token = tokens[2]
    else:
        if len(tokens) < 2:
            await message.answer("Формат: /balance +100 <id|@username>")
            return
        amount_token = tokens[0]
        target_token = tokens[1]

    try:
        amount_value = int(amount_token.replace("+", ""))
        # если число пришло со знаком минус — int даст отрицательное только если есть '-'
        if amount_token.strip().startswith("-"):
            amount_value = -abs(amount_value)
    except Exception:
        await message.answer("Сумма должна быть числом, например +100 или -100.")
        return

    if bal_action == "add" and amount_value <= 0:
        await message.answer("Для добавления используйте положительное число, например +100.")
        return
    if bal_action == "sub" and amount_value >= 0:
        await message.answer("Для уменьшения используйте отрицательное число, например -100.")
        return

    # target
    if target_token.startswith("@") or not target_token.isdigit():
        user = await user_repo.get_by_username(target_token)
    else:
        user = await user_repo.get_by_user_id(int(target_token))

    if not user:
        await message.answer("Пользователь не найден. Проверьте ID/username.")
        return

    amount_abs = abs(amount_value)
    if bal_action == "add":
        await user_repo.add_balance(user.user_id, amount_abs)
        await bal_repo.add_operation(user.user_id, float(amount_abs), "admin_balance_add", f"Операция администратора")
        await state.clear()
        await message.answer(
            f"Готово: +{amount_abs} руб. добавлено.\n@{user.username or '-'} (ID: {user.user_id})",
            reply_markup=users_manage_kb(),
        )
        return

    # sub
    ok = await user_repo.sub_balance(user.user_id, amount_abs)
    if not ok:
        await message.answer("Недостаточно средств на балансе пользователя.")
        return
    await bal_repo.add_operation(user.user_id, -float(amount_abs), "admin_balance_sub", f"Операция администратора")
    await state.clear()
    await message.answer(
        f"Готово: -{amount_abs} руб. списано.\n@{user.username or '-'} (ID: {user.user_id})",
        reply_markup=users_manage_kb(),
    )


@router.callback_query(F.data == "admin:settings")
async def settings_show(cb: CallbackQuery, **data):
    await cb.answer()
    settings = await SettingsRepository(data["session"]).get()
    await cb.message.answer(
        "Настройки:\n"
        f"min_withdraw_amount={settings.min_withdraw_amount}\n"
        "Минимальная оплата за отзыв:\n"
        f"Яндекс карты: {settings.min_review_price_yandex}\n"
        f"Google карты: {settings.min_review_price_google}\n"
        f"2ГИС: {settings.min_review_price_2gis}\n"
        "Команды (полная замена):\n"
        "set_welcome <текст>\n"
        "set_help <текст>\n"
        "set_min_withdraw <число>\n"
        "set_min_review_yandex <число>\n"
        "set_min_review_google <число>\n"
        "set_min_review_2gis <число>"
    )


@router.message(F.text.startswith("set_welcome "))
async def set_welcome(message: Message, **data):
    # Полная замена: старый текст полностью удаляется, вставляется новый.
    payload = message.text[len("set_welcome ") :].strip()
    await SettingsRepository(data["session"]).set_field("welcome_text", payload)
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_help "))
async def set_help(message: Message, **data):
    # Полная замена: старый текст полностью удаляется, вставляется новый.
    payload = message.text[len("set_help ") :].strip()
    await SettingsRepository(data["session"]).set_field("help_text", payload)
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_withdraw "))
async def set_min_withdraw(message: Message, **data):
    await SettingsRepository(data["session"]).set_field("min_withdraw_amount", int(message.text.split()[1]))
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_yandex "))
async def set_min_review_yandex(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_yandex", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_google "))
async def set_min_review_google(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_google", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_2gis "))
async def set_min_review_2gis(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_2gis", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")


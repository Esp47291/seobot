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
    SettingsRepository,
    StatsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.admin import admin_main, withdraw_kb
from keyboards.user import cancel_attempt_kb
from utils.fsm import AdminFSM

router = Router(name="admin")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Админ-панель:", reply_markup=admin_main())


@router.callback_query(F.data == "admin:tasks")
async def tasks_menu(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskItemRepository(session)
    items = await task_repo.get_all()
    text = "Список заданий:\n\n" + "\n".join(
        [f"ID:{i.id} | {i.platform} | {i.city} | {i.sphere} | {float(i.price):.2f} | {'ON' if i.is_active else 'OFF'}" for i in items]
    )
    if not items:
        text = "Заданий пока нет."
    text += "\n\nКоманды: add_task, edit_task <id> <field>, toggle_task <id>, del_task <id>"
    await cb.message.answer(text)


@router.message(F.text == "add_task")
async def add_task_start(message: Message, state: FSMContext):
    await state.set_state(AdminFSM.waiting_task_platform)
    await message.answer("Введите платформу (например Yandex/2GIS/Google Maps):")


@router.message(AdminFSM.waiting_task_platform, F.text)
async def add_task_platform(message: Message, state: FSMContext):
    await state.update_data(platform=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_city)
    await message.answer("Введите город:")


@router.message(AdminFSM.waiting_task_city, F.text)
async def add_task_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_sphere)
    await message.answer("Введите сферу:")


@router.message(AdminFSM.waiting_task_sphere, F.text)
async def add_task_sphere(message: Message, state: FSMContext):
    await state.update_data(sphere=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_price)
    await message.answer("Введите цену (число):")


@router.message(AdminFSM.waiting_task_price, F.text)
async def add_task_price(message: Message, state: FSMContext):
    try:
        Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Введите корректную цену.")
        return
    await state.update_data(price=message.text.strip().replace(",", "."))
    await state.set_state(AdminFSM.waiting_task_instruction)
    await message.answer("Введите ссылку на инструкцию:")


@router.message(AdminFSM.waiting_task_instruction, F.text)
async def add_task_instruction(message: Message, state: FSMContext, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    d = await state.get_data()
    task = await task_repo.create(
        platform=d["platform"],
        city=d["city"],
        sphere=d["sphere"],
        price=float(d["price"]),
        instruction_url=message.text.strip(),
    )
    await state.clear()
    await message.answer(f"Задание создано: ID {task.id}")


@router.message(F.text.startswith("toggle_task "))
async def toggle_task(message: Message, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task_id = int(message.text.split()[1])
    ok = await task_repo.toggle_active(task_id)
    await message.answer("Готово." if ok else "Не найдено.")


@router.message(F.text.startswith("del_task "))
async def del_task(message: Message, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task_id = int(message.text.split()[1])
    ok = await task_repo.delete(task_id)
    await message.answer("Удалено." if ok else "Не найдено.")


@router.message(F.text.startswith("edit_task "))
async def edit_task(message: Message, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("Формат: edit_task <id> <field> <value>")
        return
    ok = await task_repo.update_field(int(parts[1]), parts[2], parts[3])
    await message.answer("Обновлено." if ok else "Ошибка.")


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
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.complete(attempt_id)
    if not attempt:
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    amount = float(task.price)
    await user_repo.add_balance(attempt.user_id, amount)
    await bal_repo.add_operation(attempt.user_id, amount, "task_reward", f"Задание {task.id}")
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
    await state.set_state(AdminFSM.waiting_broadcast_content)
    await cb.message.answer("Отправьте текст рассылки.")


@router.message(AdminFSM.waiting_broadcast_content, F.text)
async def broadcast_send(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    target = message.text.strip()
    if target.startswith("/to "):
        dest = target.split(maxsplit=1)[1]
        user = await user_repo.get_by_username(dest) if dest.startswith("@") else await user_repo.get_by_user_id(int(dest))
        if user:
            await message.bot.send_message(user.user_id, "📢 " + target)
            await message.answer("Отправлено пользователю.")
    elif target.startswith("/confirm"):
        users_total = await StatsRepository(session).summary()
        await message.answer(f"Готово для отправки всем ({users_total['users_total']} пользователей). Команда: /sendall <текст>")
    elif target.startswith("/sendall "):
        text = target.split(maxsplit=1)[1]
        users = []
        result = await data["session"].execute(select(User))
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
    else:
        await message.answer("Используйте: /confirm, /sendall <текст>, /to <id|@username>")


@router.callback_query(F.data == "admin:users")
async def users_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_user_query)
    await cb.message.answer("Введите ID или @username пользователя:")


@router.message(AdminFSM.waiting_user_query, F.text)
async def users_find(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    attempt_repo = AttemptRepository(session)
    text = message.text.strip()
    user = await user_repo.get_by_username(text) if text.startswith("@") else await user_repo.get_by_user_id(int(text))
    if not user:
        await message.answer("Не найден.")
        return
    completed = await attempt_repo.completed_count_by_user(user.user_id)
    await state.update_data(target_user_id=user.user_id)
    await message.answer(
        f"Пользователь @{user.username or '-'}\n"
        f"ID: {user.user_id}\n"
        f"Баланс: {float(user.balance):.2f}\n"
        f"Дата регистрации: {user.registered_at:%d.%m.%Y %H:%M}\n"
        f"Выполнено: {completed}\n\n"
        "Команды: block, unblock, balance +10, balance -5"
    )


@router.message(F.text.in_({"block", "unblock"}))
async def users_block_toggle(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    user_id = (await state.get_data()).get("target_user_id")
    if not user_id:
        return
    await user_repo.set_blocked(user_id, message.text == "block")
    await message.answer("Статус обновлён.")


@router.message(F.text.startswith("balance "))
async def users_change_balance(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    user_id = (await state.get_data()).get("target_user_id")
    if not user_id:
        return
    value = float(message.text.split()[1])
    if value >= 0:
        await user_repo.add_balance(user_id, value)
    else:
        await user_repo.sub_balance(user_id, abs(value))
    await bal_repo.add_operation(user_id, value, "admin_adjust", "Ручная корректировка")
    await message.answer("Баланс изменен.")


@router.callback_query(F.data == "admin:settings")
async def settings_show(cb: CallbackQuery, **data):
    await cb.answer()
    settings = await SettingsRepository(data["session"]).get()
    await cb.message.answer(
        "Настройки:\n"
        f"min_withdraw_amount={settings.min_withdraw_amount}\n"
        "Команды:\n"
        "set_welcome <текст>\n"
        "set_help <текст>\n"
        "set_min_withdraw <число>"
    )


@router.message(F.text.startswith("set_welcome "))
async def set_welcome(message: Message, **data):
    await SettingsRepository(data["session"]).set_field("welcome_text", message.text.split(" ", 1)[1])
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_help "))
async def set_help(message: Message, **data):
    await SettingsRepository(data["session"]).set_field("help_text", message.text.split(" ", 1)[1])
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_withdraw "))
async def set_min_withdraw(message: Message, **data):
    await SettingsRepository(data["session"]).set_field("min_withdraw_amount", int(message.text.split()[1]))
    await message.answer("Обновлено.")


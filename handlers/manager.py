# -*- coding: utf-8 -*-
"""Панель менеджера: /manager — свои задания, личная рассылка, выплаты исполнителям по кнопке «Оплатил»."""
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_IDS
from database import (
    AttemptRepository,
    BalanceRepository,
    SettingsRepository,
    StatsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.manager import manager_main, manager_withdraw_kb
from services.task_payout import grant_task_completion_rewards
from utils.fsm import ManagerFSM

router = Router(name="manager")


@router.message(Command("manager"))
async def cmd_manager(message: Message):
    await message.answer("Панель менеджера:", reply_markup=manager_main())


@router.callback_query(F.data == "mgr:back_main")
async def mgr_back_main(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Панель менеджера:", reply_markup=manager_main())


# --- Задания (только свои) ---


@router.callback_query(F.data == "mgr:tasks")
async def mgr_tasks_menu(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer(
        "⚙️ Управление вашими заданиями",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить задание", callback_data="mgr:tasks_add")],
                [InlineKeyboardButton(text="🗑️ Удалить задание", callback_data="mgr:tasks_delete")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="mgr:back_main")],
            ]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_add")
async def mgr_tasks_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer(
        "Шаг 1/6.\nВыберите платформу:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Яндекс карты", callback_data="mgr:tasks_plat:yandex")],
                [InlineKeyboardButton(text="2ГИС", callback_data="mgr:tasks_plat:2gis")],
                [InlineKeyboardButton(text="Google карты", callback_data="mgr:tasks_plat:google")],
                [InlineKeyboardButton(text="Другая платформа", callback_data="mgr:tasks_plat:other")],
            ]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_plat:yandex")
async def mgr_tasks_plat_yandex(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_price)
    await state.update_data(platform="Яндекс карты")
    await cb.message.answer("Шаг 2/6.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:2gis")
async def mgr_tasks_plat_2gis(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_price)
    await state.update_data(platform="2ГИС")
    await cb.message.answer("Шаг 2/6.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:google")
async def mgr_tasks_plat_google(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_price)
    await state.update_data(platform="Google карты")
    await cb.message.answer("Шаг 2/6.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:other")
async def mgr_tasks_plat_other(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_platform)
    await cb.message.answer("Шаг 1/6.\nНапишите название платформы.\n\nПример: `Яндекс карты`")


@router.message(ManagerFSM.waiting_task_platform, F.text)
async def mgr_tasks_add_platform(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    await state.update_data(platform=message.text.strip())
    await state.set_state(ManagerFSM.waiting_task_price)
    await message.answer("Шаг 2/6.\nНапишите цену за отзыв (число). Например: 120")


@router.message(ManagerFSM.waiting_task_price, F.text)
async def mgr_tasks_add_price(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    try:
        price = Decimal(message.text.strip().replace(",", "."))
    except Exception:
        await message.answer("Некорректное число. Повторите: цена за отзыв (например 120).")
        return
    if price <= 0:
        await message.answer("Цена должна быть больше 0.")
        return
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
    await state.set_state(ManagerFSM.waiting_task_venue_city)
    await message.answer(
        "Шаг 3/6.\nУкажите <b>город организации</b> (где находится заведение). "
        "Это увидит исполнитель на карточке задания.\n\n"
        "Пример: Москва, Казань",
        parse_mode="HTML",
    )


@router.message(ManagerFSM.waiting_task_venue_city, F.text)
async def mgr_tasks_add_venue_city(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    venue_city = message.text.strip()
    if len(venue_city) < 2:
        await message.answer("Город слишком короткий. Напишите название города.")
        return
    await state.update_data(venue_city=venue_city)
    await state.set_state(ManagerFSM.waiting_task_sphere)
    await message.answer(
        "Шаг 4/6.\nУкажите <b>сферу бизнеса</b> организации (исполнитель увидит это на карточке).\n\n"
        "Пример: кафе, автосервис, стоматология, салон красоты",
        parse_mode="HTML",
    )


@router.message(ManagerFSM.waiting_task_sphere, F.text)
async def mgr_tasks_add_sphere(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    sphere = message.text.strip()
    if len(sphere) < 2:
        await message.answer("Сфера слишком короткая. Опишите сферу подробнее.")
        return
    await state.update_data(task_sphere=sphere)
    await state.set_state(ManagerFSM.waiting_task_instruction)
    await message.answer("Шаг 5/6.\nНапишите инструкцию для исполнителя.")


@router.message(ManagerFSM.waiting_task_instruction, F.text)
async def mgr_tasks_add_instruction(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    await state.update_data(instruction_text=message.text.strip())
    await state.set_state(ManagerFSM.waiting_task_venue_link)
    await message.answer("Шаг 6/6.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


@router.message(ManagerFSM.waiting_task_venue_link, F.text)
async def mgr_tasks_add_venue_link(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    session = data["session"]
    d = await state.get_data()
    task_repo = TaskItemRepository(session)

    platform = (d.get("platform") or "").strip()
    instruction_text = (d.get("instruction_text") or "").strip()
    venue_url = message.text.strip()
    venue_city = (d.get("venue_city") or "").strip()
    task_sphere = (d.get("task_sphere") or "").strip()

    if not platform:
        await state.clear()
        await message.answer("Ошибка: платформа не указана.")
        return
    if not venue_city:
        await state.clear()
        await message.answer("Ошибка: город организации не указан. Начните создание задания заново.")
        return
    if not task_sphere:
        await state.clear()
        await message.answer("Ошибка: сфера не указана. Начните создание задания заново.")
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
        sphere=task_sphere,
        venue_city=venue_city,
        price=float(price),
        instruction_url=f"{instruction_text}\n\nСсылка на заведение для отзыва: {venue_url}",
        created_by_user_id=message.from_user.id,
    )
    await state.clear()
    await message.answer(
        f"✅ Задание создано.\nID: {task.id}",
        reply_markup=manager_main(),
    )


@router.callback_query(F.data == "mgr:tasks_delete")
async def mgr_tasks_delete_menu(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    session = data["session"]
    task_repo = TaskItemRepository(session)
    items = await task_repo.get_by_creator(cb.from_user.id)
    items_sorted = sorted(items, key=lambda x: x.id)

    if not items_sorted:
        await cb.message.answer("У вас пока нет заданий.", reply_markup=manager_main())
        return

    lines = []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for idx, item in enumerate(items_sorted, start=1):
        label = f"{idx}"
        vc = (getattr(item, "venue_city", None) or "").strip() or "—"
        sp = (item.sphere or "").strip() or "—"
        sp_short = sp[:24] + "…" if len(sp) > 24 else sp
        lines.append(
            f"{idx}) ID {item.id} | {item.platform} | город: {vc} | {sp_short} | "
            f"{float(item.price):.2f} руб. | {'ON' if item.is_active else 'OFF'}"
        )
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=label, callback_data=f"mgr:tasks_del:{item.id}")]
        )
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="mgr:back_main")])

    await cb.message.answer("Выберите задание для удаления:\n\n" + "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("mgr:tasks_del:"))
async def mgr_tasks_delete_action(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task_id = int(cb.data.split(":")[2])
    task = await task_repo.get_by_id(task_id)
    if not task or task.created_by_user_id != cb.from_user.id:
        await cb.message.answer("Нельзя удалить чужое задание.")
        return
    await task_repo.delete(task_id)
    await state.clear()
    await cb.message.answer("✅ Задание удалено.")
    await mgr_tasks_delete_menu(cb, state, **data)


# --- Статистика ---


@router.callback_query(F.data == "mgr:stats")
async def mgr_stats(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    stats = StatsRepository(session)
    s = await stats.summary()
    mine = await stats.manager_completed_tasks(cb.from_user.id)
    await cb.message.answer(
        "📊 Статистика\n\n"
        f"✅ Выполнено заданий по вашим объявлениям: {mine}\n\n"
        "Общие показатели (вся система):\n"
        f"Пользователей: {s['users_total']}\n"
        f"Новых за 7 дней: {s['users_new_week']}\n"
        f"Выполнено заданий всего: {s['tasks_completed']}\n"
        f"Выплачено по заявкам: {s['total_paid']:.2f}\n"
        f"Сумма балансов: {s['total_balances']:.2f}"
    )


# --- Личная рассылка ---


@router.callback_query(F.data == "mgr:broadcast")
async def mgr_broadcast_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_broadcast_content)
    await state.update_data(broadcast_mode="personal")
    await cb.message.answer(
        "✉️ Личная рассылка\n\n"
        "Отправьте сообщение в формате:\n"
        "`/sendmessage <id|@username> <текст>`"
    )


@router.message(ManagerFSM.waiting_broadcast_content, F.text)
async def mgr_broadcast_send(message: Message, state: FSMContext, **data):
    session = data["session"]
    state_data = await state.get_data()
    if state_data.get("broadcast_mode") != "personal":
        await state.clear()
        await message.answer("Ошибка. Начните с панели: Личная рассылка.")
        return

    raw = (message.text or "").strip()
    if not raw.startswith("/sendmessage"):
        await message.answer("Используйте формат: /sendmessage <id|@username> <текст>")
        return

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


# --- Заявки на вывод ---


@router.callback_query(F.data == "mgr:withdrawals")
async def mgr_withdrawals_list(cb: CallbackQuery, **data):
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
            reply_markup=manager_withdraw_kb(item.id),
        )


@router.callback_query(F.data.startswith("mgr:wd_paid:"))
async def mgr_wd_paid(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    wd_repo = WithdrawalRepository(session)
    wd = await wd_repo.mark_paid(int(cb.data.split(":")[2]))
    if wd:
        await cb.bot.send_message(wd.user_id, "✅ Ваша заявка на вывод выплачена.")
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("mgr:wd_rej:"))
async def mgr_wd_rej(cb: CallbackQuery, **data):
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


# --- Менеджер подтвердил выплату исполнителю ---


@router.callback_query(F.data.startswith("mgr:outpay:"))
async def mgr_outpay(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.get_by_id(attempt_id)
    if not attempt or attempt.status != "completed" or attempt.balance_credited:
        await cb.message.answer("Уже обработано или недоступно.")
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    if not task or task.created_by_user_id != cb.from_user.id:
        await cb.message.answer("Это не ваше задание.")
        return

    amount = await grant_task_completion_rewards(session, attempt.user_id, task)
    await attempt_repo.mark_balance_credited(attempt_id)
    await UserRepository(session).clear_repeat_unlock_platform(attempt.user_id, task.platform)

    await cb.bot.send_message(
        attempt.user_id,
        f"✅ Отзыв оплачен заказчиком. На баланс зачислено {amount:.2f} руб.",
    )
    uname = cb.from_user.username or "-"
    for aid in ADMIN_IDS:
        try:
            await cb.bot.send_message(
                aid,
                "✅ Отзыв оплачен: менеджер нажал «Оплатить».\n"
                f"Менеджер: @{uname} (ID {cb.from_user.id})\n"
                f"Задание #{task.id} | {task.platform}\n"
                f"Исполнитель: {attempt.user_id}\n"
                f"Сумма: {amount:.2f} руб.",
            )
        except Exception:
            pass

    await cb.message.edit_reply_markup(reply_markup=None)

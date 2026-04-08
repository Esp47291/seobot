# -*- coding: utf-8 -*-
"""Админ-хендлеры для SeoJob / Отзовик."""
import json
import re
from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sqlalchemy import case, func, select

from config import ADMIN_IDS
from database.models import Attempt, User
from database import (
    AttemptRepository,
    BalanceRepository,
    SecondAccountReviewRepository,
    SettingsRepository,
    StatsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.admin import admin_back_main_kb, admin_main, moderation_kb, users_manage_kb, withdraw_kb
from keyboards.manager import manager_payout_kb
from keyboards.user import cancel_attempt_kb, main_menu
from services.task_payout import grant_task_completion_rewards
from utils.fsm import AdminFSM

router = Router(name="admin")

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    m = _URL_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(").,]>\"'")


def _human_timedelta(dt: datetime) -> str:
    delta = datetime.utcnow() - dt
    sec = int(delta.total_seconds())
    if sec < 0:
        sec = 0
    days = sec // 86400
    hours = (sec % 86400) // 3600
    minutes = (sec % 3600) // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days}д")
    if hours or days:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    return " ".join(parts)


@router.callback_query(F.data == "admin:admission_queue")
async def admission_queue(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskItemRepository(session)

    waiting = await session.execute(
        select(Attempt).where(Attempt.status == "waiting_approval").order_by(Attempt.id.desc())
    )
    waiting_attempts = list(waiting.scalars().all())

    if not waiting_attempts:
        await cb.message.answer("Нет активных заявок на допуск к заданиям.")
        return

    await cb.message.answer(f"🟡 Заявки на допуск к заданиям: {len(waiting_attempts)}")
    for at in waiting_attempts:
        task = await task_repo.get_by_id(at.task_item_id)
        platform = getattr(task, "platform", None) if task else None
        venue_city = getattr(task, "venue_city", None) if task else None
        sphere = getattr(task, "sphere", None) if task else None
        try:
            price = float(getattr(task, "price", 0) or 0)
        except Exception:
            price = 0.0
        text = (
            f"🧾 Заявка #{at.id}\n"
            f"Исполнитель ID: {at.user_id}\n"
            f"Задание: {platform or '—'} | город орг.: {(venue_city or '—').strip()}\n"
            f"Сфера: {sphere or '—'} | Вознаграждение: {price:.2f} руб."
        )
        file_id = (getattr(at, "account_screenshot_file_id", None) or "").strip()
        if file_id:
            await cb.message.answer_photo(
                photo=file_id,
                caption=text,
                reply_markup=moderation_kb(at.id, "pre"),
            )
        else:
            await cb.message.answer(text, reply_markup=moderation_kb(at.id, "pre"))


@router.callback_query(F.data == "admin:reviews_queue")
async def reviews_queue(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskItemRepository(session)

    review = await session.execute(
        select(Attempt).where(Attempt.status == "review_submitted").order_by(Attempt.id.desc())
    )
    review_attempts = list(review.scalars().all())
    if not review_attempts:
        await cb.message.answer("Нет отзывов на подтверждении.")
        return

    await cb.message.answer(f"🟢 Подтверждение отзывов: {len(review_attempts)}")
    for at in review_attempts:
        task = await task_repo.get_by_id(at.task_item_id)
        platform = getattr(task, "platform", None) if task else None
        venue_city = getattr(task, "venue_city", None) if task else None
        sphere = getattr(task, "sphere", None) if task else None
        try:
            price = float(getattr(task, "price", 0) or 0)
        except Exception:
            price = 0.0
        venue_url = _extract_first_url(getattr(task, "instruction_url", None) if task else None)
        text = (
            f"🧾 Отзыв на подтверждении #{at.id}\n"
            f"Исполнитель ID: {at.user_id}\n"
            f"Задание: {platform or '—'} | город орг.: {(venue_city or '—').strip()}\n"
            f"Сфера: {sphere or '—'} | Вознаграждение: {price:.2f} руб."
        )
        if venue_url:
            text += f"\n🔗 Ссылка: {venue_url}"

        review_file_id = (getattr(at, "review_screenshot_file_id", None) or "").strip()
        if review_file_id:
            await cb.message.answer_photo(
                photo=review_file_id,
                caption=text,
                reply_markup=moderation_kb(at.id, "review"),
            )
        else:
            await cb.message.answer(text, reply_markup=moderation_kb(at.id, "review"))


def _telegram_text_chunks(text: str, max_len: int = 3800) -> list[str]:
    """Разбить длинный текст на части под лимит Telegram (~4096)."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    cur_len = 0
    for line in text.split("\n"):
        add = len(line) + (1 if current else 0)
        if cur_len + add > max_len and current:
            chunks.append("\n".join(current))
            current = [line]
            cur_len = len(line)
        else:
            current.append(line)
            cur_len += add
    if current:
        chunks.append("\n".join(current))
    return chunks


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer("Админ-панель:", reply_markup=admin_main())


@router.callback_query(F.data == "admin:user_profile")
async def admin_user_profile_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_user_profile_query)
    await cb.message.answer(
        "Введите Telegram ID пользователя или @username.\n\nПримеры:\n`5263412842`\n`@someuser`",
        reply_markup=admin_back_main_kb(),
    )


@router.message(AdminFSM.waiting_user_profile_query, F.text)
async def admin_user_profile_show(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return

    token = raw.split()[0].strip()
    user: User | None = None
    if token.startswith("@") or not token.isdigit():
        user = await user_repo.get_by_username(token)
    else:
        user = await user_repo.get_by_user_id(int(token))

    if not user:
        await message.answer("Пользователь не найден. Проверьте ID/username.", reply_markup=admin_back_main_kb())
        return

    # агрегаты по попыткам
    by_status_rows = (
        await session.execute(
            select(Attempt.status, func.count())
            .where(Attempt.user_id == user.user_id)
            .group_by(Attempt.status)
        )
    ).all()
    status_map: dict[str, int] = {str(s): int(c or 0) for s, c in by_status_rows}
    total_attempts = sum(status_map.values())

    last_submitted_at = (
        await session.execute(
            select(func.max(Attempt.submitted_at)).where(
                Attempt.user_id == user.user_id,
                Attempt.submitted_at.is_not(None),
            )
        )
    ).scalar_one_or_none()

    last_review_line = "—"
    if last_submitted_at:
        last_review_line = _human_timedelta(last_submitted_at)

    # последние 5 попыток
    last_rows = (
        await session.execute(
            select(Attempt)
            .where(Attempt.user_id == user.user_id)
            .order_by(Attempt.id.desc())
            .limit(5)
        )
    ).scalars().all()

    task_repo = TaskItemRepository(session)
    attempt_lines: list[str] = []
    for at in last_rows:
        task = await task_repo.get_by_id(at.task_item_id)
        platform = getattr(task, "platform", None) if task else None
        venue_city = getattr(task, "venue_city", None) if task else None
        sphere = getattr(task, "sphere", None) if task else None
        price = float(getattr(task, "price", 0) or 0) if task else 0.0
        created = at.created_at.strftime("%d.%m.%Y %H:%M") if at.created_at else "—"
        attempt_lines.append(
            f"• #{at.id} [{at.status}] {created} | {platform or '—'} | {(venue_city or '—').strip()} | {sphere or '—'} | {price:.2f} руб."
        )

    uname = f"@{user.username}" if user.username else "—"
    name = (user.first_name or "").strip() or "—"
    city = (user.city or "").strip() or "—"
    req = (user.payout_requisites or "").strip() or "—"
    blocked = "да" if user.is_blocked else "нет"

    stats_lines = [
        "👤 <b>ЛК пользователя</b>",
        f"ID: <code>{user.user_id}</code>",
        f"Username: {uname}",
        f"Имя: {name}",
        f"Город: {city}",
        f"Баланс: <b>{float(user.balance or 0):.2f}</b> руб.",
        f"Заблокирован: <b>{blocked}</b>",
        f"Реквизиты: {req[:700]}",
        "",
        "📊 <b>Статистика</b>",
        f"Всего попыток: <b>{total_attempts}</b>",
        f"Completed: {status_map.get('completed', 0)} | Review_submitted: {status_map.get('review_submitted', 0)} | Rejected: {status_map.get('rejected', 0)}",
        f"Declined: {status_map.get('declined', 0)} | Canceled: {status_map.get('canceled', 0)} | Approved: {status_map.get('approved', 0)}",
        f"⏱️ С последнего скрина отзыва: <b>{last_review_line}</b>",
        "",
        "🧾 <b>Последние 5 попыток</b>",
        *(attempt_lines or ["—"]),
    ]

    await state.clear()
    await message.answer("\n".join(stats_lines), parse_mode="HTML", reply_markup=admin_main())


@router.callback_query(F.data == "admin:tasks")
async def tasks_menu(cb: CallbackQuery, **data):
    await cb.answer()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "⚙️ Управление заданиями",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить задание", callback_data="admin:tasks_add")],
                [InlineKeyboardButton(text="✏️ Изменить объявление", callback_data="admin:tasks_edit")],
                [InlineKeyboardButton(text="🗑️ Удалить задание", callback_data="admin:tasks_delete")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")],
            ]
        ),
    )


@router.callback_query(F.data == "admin:tasks_edit")
async def admin_tasks_edit_menu(cb: CallbackQuery, state: FSMContext, **data):
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
    for idx, item in enumerate(items_sorted, start=1):
        label = f"{idx}"
        vc = (getattr(item, "venue_city", None) or "").strip() or "—"
        sp = (item.sphere or "").strip() or "—"
        sp_short = sp[:24] + "…" if len(sp) > 24 else sp
        owner = "админ" if item.created_by_user_id is None else f"менеджер {item.created_by_user_id}"
        lines.append(
            f"{idx}) ID {item.id} | {item.platform} | {owner} | город: {vc} | {sp_short} | "
            f"{float(item.price):.2f} руб. | {'ON' if item.is_active else 'OFF'}"
        )
        kb.inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"admin:tasks_edit_pick:{item.id}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="admin:tasks")])

    await cb.message.answer("Выберите задание для изменения:\n\n" + "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("admin:tasks_edit_pick:"))
async def admin_tasks_edit_pick(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    task_id = int(cb.data.split(":")[2])
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task:
        await cb.message.answer("Задание не найдено.", reply_markup=admin_main())
        return

    await state.update_data(edit_task_id=task_id)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Цена", callback_data=f"admin:tasks_edit_field:{task_id}:price")],
            [InlineKeyboardButton(text="🏙️ Город организации", callback_data=f"admin:tasks_edit_field:{task_id}:venue_city")],
            [InlineKeyboardButton(text="🏷️ Сфера", callback_data=f"admin:tasks_edit_field:{task_id}:sphere")],
            [InlineKeyboardButton(text="📝 Инструкция/ссылка (полностью)", callback_data=f"admin:tasks_edit_field:{task_id}:instruction_url")],
            [InlineKeyboardButton(text="📆 Лимит в день", callback_data=f"admin:tasks_edit_field:{task_id}:daily_issue_count")],
            [InlineKeyboardButton(text="🔁 Вкл/выкл", callback_data=f"admin:tasks_edit_field:{task_id}:toggle_active")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="admin:tasks_edit")],
        ]
    )
    await cb.message.answer(
        f"✏️ Редактирование задания #{task.id}\n"
        f"{task.platform} | {(getattr(task, 'venue_city', '') or '—').strip()} | {(task.sphere or '—').strip()} | {float(task.price):.2f} руб.",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("admin:tasks_edit_field:"))
async def admin_tasks_edit_field(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    parts = cb.data.split(":")
    task_id = int(parts[2])
    field = parts[3]
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task:
        await state.clear()
        await cb.message.answer("Задание не найдено.", reply_markup=admin_main())
        return

    if field == "toggle_active":
        await task_repo.toggle_active(task_id)
        await state.clear()
        await cb.message.answer("✅ Готово: статус задания переключён.", reply_markup=admin_main())
        return

    await state.set_state(AdminFSM.waiting_task_edit_value)
    await state.update_data(edit_task_id=task_id, edit_field=field)

    prompt = "Введите новое значение."
    if field == "price":
        prompt = "Введите новую цену (число), например 130"
    elif field == "venue_city":
        prompt = "Введите новый город организации, например: Москва"
    elif field == "sphere":
        prompt = "Введите новую сферу, например: Стоматология"
    elif field == "instruction_url":
        prompt = "Введите новый текст инструкции (можно со ссылкой). Это полностью заменит текущую инструкцию."
    elif field == "daily_issue_count":
        prompt = "Введите лимит выдачи в день (1..10)."

    await cb.message.answer(prompt, reply_markup=admin_back_main_kb())


@router.message(AdminFSM.waiting_task_edit_value, F.text)
async def admin_tasks_edit_value_save(message: Message, state: FSMContext, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    settings = await SettingsRepository(session).get()

    d = await state.get_data()
    task_id = int(d.get("edit_task_id") or 0)
    field = (d.get("edit_field") or "").strip()
    task = await task_repo.get_by_id(task_id)
    if not task:
        await state.clear()
        await message.answer("Задание не найдено.", reply_markup=admin_main())
        return

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return

    # validation / mapping
    value = raw
    if field == "price":
        try:
            new_price = Decimal(raw.replace(",", "."))
        except Exception:
            await message.answer("Некорректное число. Повторите, например 130.")
            return
        if new_price <= 0:
            await message.answer("Цена должна быть больше 0.")
            return
        # минимальная цена по платформе
        min_price = None
        if task.platform == "Яндекс карты":
            min_price = settings.min_review_price_yandex
        elif task.platform == "Google карты":
            min_price = settings.min_review_price_google
        elif task.platform == "2ГИС":
            min_price = settings.min_review_price_2gis
        if min_price is not None and float(new_price) < float(min_price):
            await message.answer(f"Минимальная цена для {task.platform} = {min_price} руб. Ниже нельзя.")
            return
        value = str(new_price)
    elif field == "venue_city":
        if len(raw) < 2:
            await message.answer("Город слишком короткий.")
            return
    elif field == "sphere":
        if len(raw) < 2:
            await message.answer("Сфера слишком короткая.")
            return
    elif field == "daily_issue_count":
        try:
            n = int(raw)
        except Exception:
            await message.answer("Введите целое число 1..10.")
            return
        if n < 1 or n > 10:
            await message.answer("Число должно быть в диапазоне 1..10.")
            return
        value = str(n)

    ok = await task_repo.update_field(task_id, field, value)
    if not ok:
        await message.answer("Не удалось сохранить (проверьте значение).", reply_markup=admin_main())
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Изменение сохранено.", reply_markup=admin_main())


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
        "Шаг 1/8.\nВыберите платформу:",
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
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:2gis")
async def tasks_plat_2gis(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_price)
    await state.update_data(platform="2ГИС")
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:google")
async def tasks_plat_google(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_price)
    await state.update_data(platform="Google карты")
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "admin:tasks_plat:other")
async def tasks_plat_other(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(AdminFSM.waiting_task_platform)
    await cb.message.answer("Шаг 1/8.\nНапишите название платформы.\n\nПример: `Яндекс карты`")


@router.message(AdminFSM.waiting_task_platform, F.text)
async def tasks_add_platform(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    await state.update_data(platform=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_price)
    await message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


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
    await state.set_state(AdminFSM.waiting_task_venue_city)
    await message.answer(
        "Шаг 3/8.\nУкажите <b>город организации</b> (где находится заведение). "
        "Это увидит исполнитель на карточке задания.\n\n"
        "Пример: Москва, Казань",
        parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_task_venue_city, F.text)
async def tasks_add_venue_city(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    venue_city = message.text.strip()
    if len(venue_city) < 2:
        await message.answer("Город слишком короткий. Напишите название города.")
        return
    await state.update_data(venue_city=venue_city)
    await state.set_state(AdminFSM.waiting_task_sphere)
    await message.answer(
        "Шаг 4/8.\nУкажите <b>сферу бизнеса</b> организации (исполнитель увидит это на карточке).\n\n"
        "Пример: кафе, автосервис, стоматология, салон красоты",
        parse_mode="HTML",
    )


@router.message(AdminFSM.waiting_task_sphere, F.text)
async def tasks_add_sphere(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    sphere = message.text.strip()
    if len(sphere) < 2:
        await message.answer("Сфера слишком короткая. Опишите сферу подробнее.")
        return
    await state.update_data(task_sphere=sphere)
    await state.set_state(AdminFSM.waiting_task_instruction)
    await message.answer("Шаг 5/8.\nНапишите инструкцию для исполнителя.")


@router.message(AdminFSM.waiting_task_instruction, F.text)
async def tasks_add_instruction(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return
    await state.update_data(instruction_text=message.text.strip())
    await state.set_state(AdminFSM.waiting_task_prebuilt_mode)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await message.answer(
        "Шаг 6/8.\nДобавить готовые тексты для отзыва?\n\n"
        "После этого задания новые тексты добавить будет нельзя.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Готовые тексты", callback_data="admin:tasks_prebuilt_yes")],
                [InlineKeyboardButton(text="⏭️ Без готовых текстов", callback_data="admin:tasks_prebuilt_no")],
            ]
        ),
    )


@router.callback_query(F.data == "admin:tasks_prebuilt_yes")
async def tasks_prebuilt_yes(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.update_data(prebuilt_texts=[])
    await state.set_state(AdminFSM.waiting_task_prebuilt_texts)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="admin:tasks_prebuilt_done")]]
    )
    await cb.message.answer(
        "Шаг 6/8.\nОтправляйте готовые тексты по очереди: 1 текст = 1 сообщение.\n"
        "Каждый текст будет выдан только одному исполнителю.\n\n"
        "Когда закончите — нажмите «✅ Готово».",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "admin:tasks_prebuilt_no")
async def tasks_prebuilt_no(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.update_data(prebuilt_texts=[])
    await state.set_state(AdminFSM.waiting_task_prebuilt_mode)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "Шаг 7/8.\nСколько раз ваше задание нужно выдавать в день?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1", callback_data="admin:tasks_daily:1")],
                [InlineKeyboardButton(text="2", callback_data="admin:tasks_daily:2")],
                [InlineKeyboardButton(text="5", callback_data="admin:tasks_daily:5")],
                [InlineKeyboardButton(text="Свой вариант (1..10)", callback_data="admin:tasks_daily:custom")],
            ]
        ),
    )


@router.message(AdminFSM.waiting_task_prebuilt_texts, F.text)
async def tasks_prebuilt_texts_collect(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return

    text = message.text.strip()
    if not text:
        return

    d = await state.get_data()
    texts = list(d.get("prebuilt_texts") or [])
    texts.append(text)
    await state.update_data(prebuilt_texts=texts)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    done_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="admin:tasks_prebuilt_done")]]
    )
    await message.answer(
        f"✅ Текст добавлен (всего: {len(texts)}). Отправьте следующий или нажмите «✅ Готово».",
        reply_markup=done_kb,
    )


@router.callback_query(F.data == "admin:tasks_prebuilt_done")
async def tasks_prebuilt_done(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    d = await state.get_data()
    texts = list(d.get("prebuilt_texts") or [])
    if not texts:
        await cb.message.answer("Сначала добавьте хотя бы 1 готовый текст.")
        return

    await state.set_state(AdminFSM.waiting_task_prebuilt_mode)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    await cb.message.answer(
        "Шаг 7/8.\nСколько раз ваше задание нужно выдавать в день?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1", callback_data="admin:tasks_daily:1")],
                [InlineKeyboardButton(text="2", callback_data="admin:tasks_daily:2")],
                [InlineKeyboardButton(text="5", callback_data="admin:tasks_daily:5")],
                [InlineKeyboardButton(text="Свой вариант (1..10)", callback_data="admin:tasks_daily:custom")],
            ]
        ),
    )


@router.callback_query(F.data.in_(["admin:tasks_daily:1", "admin:tasks_daily:2", "admin:tasks_daily:5"]))
async def tasks_daily_fixed(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    value = int(cb.data.split(":")[-1])
    await state.update_data(daily_issue_count=value)
    await state.set_state(AdminFSM.waiting_task_venue_link)
    await cb.message.answer("Шаг 8/8.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


@router.callback_query(F.data == "admin:tasks_daily:custom")
async def tasks_daily_custom_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_task_daily_custom)
    await cb.message.answer("Введите число от 1 до 10.")


@router.message(AdminFSM.waiting_task_daily_custom, F.text)
async def tasks_daily_custom_finish(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main())
        return

    try:
        value = int(message.text.strip())
    except Exception:
        await message.answer("Введите целое число от 1 до 10.")
        return

    if value < 1 or value > 10:
        await message.answer("Число должно быть в диапазоне 1..10.")
        return

    await state.update_data(daily_issue_count=value)
    await state.set_state(AdminFSM.waiting_task_venue_link)
    await message.answer("Шаг 8/8.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


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
    daily_issue_count = d.get("daily_issue_count")
    prebuilt_texts = list(d.get("prebuilt_texts") or [])
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
    if daily_issue_count is None:
        await state.clear()
        await message.answer("Ошибка: лимит выдачи в день не задан.")
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
        daily_issue_count=int(daily_issue_count),
        prebuilt_texts_json=json.dumps(prebuilt_texts, ensure_ascii=False),
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
        vc = (getattr(item, "venue_city", None) or "").strip() or "—"
        sp = (item.sphere or "").strip() or "—"
        sp_short = sp[:24] + "…" if len(sp) > 24 else sp
        lines.append(
            f"{idx}) ID {item.id} | {item.platform} | город: {vc} | {sp_short} | "
            f"{float(item.price):.2f} руб. | {'ON' if item.is_active else 'OFF'}"
        )
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
    repo = StatsRepository(session)
    s = await repo.summary()
    ex = await repo.admin_dashboard_extras()

    global_lines = [
        "📊 <b>Общая статистика</b>",
        f"Пользователей: {s['users_total']} (новых за 7 дней: {s['users_new_week']})",
        f"Выполнено заданий (всего, все владельцы): {s['tasks_completed']}",
        f"Выплачено по заявкам на вывод (подтверждённые): {s['total_paid']:.2f} руб.",
        f"Сумма балансов пользователей в боте: {s['total_balances']:.2f} руб.",
        "",
        "📌 <b>Очереди и заявки</b>",
        f"Отзывов ждут решения админа (скрин отзыва): {ex['reviews_awaiting_admin']}",
        f"Профилей ждут допуска к заданию: {ex['profiles_awaiting_admin']}",
        f"Заявок на вывод в ожидании: {ex['pending_wd_count']} на сумму {ex['pending_wd_sum']:.2f} руб.",
        "",
        "📦 <b>Карточки заданий</b>",
        f"Всего заданий в базе: {ex['manager_tasks_total'] + ex['admin_tasks_total']} "
        f"(активных сейчас: {ex['tasks_active_any_owner']})",
        f"  • размещено <b>менеджерами</b>: {ex['manager_tasks_total']}",
        f"  • размещено <b>админом</b>: {ex['admin_tasks_total']}",
        "",
        f"🔗 Записей реферальных начислений в истории операций: {ex['referral_payout_ops_total']}",
    ]
    global_text = "\n".join(global_lines)
    for chunk in _telegram_text_chunks(global_text):
        await cb.message.answer(chunk, parse_mode="HTML")

    manager_ids = await repo.manager_ids_for_admin_report()
    if not manager_ids:
        await cb.message.answer("👔 <b>Менеджеры:</b> в .env нет MANAGER_IDS и нет заданий с владельцем-менеджером.", parse_mode="HTML")
        return

    await cb.message.answer(
        f"👔 <b>Менеджеры ({len(manager_ids)}):</b> детализация ниже — по одному сообщению на каждого.",
        parse_mode="HTML",
    )

    for mid in manager_ids:
        snap = await repo.per_manager_admin_snapshot(mid)
        uname_line = f"@{snap['username']}" if snap["username"] else "username не указан"
        mlines = [
            f"👤 <b>Менеджер</b> <code>{snap['user_id']}</code> ({uname_line})",
            "",
            f"📋 Заданий размещено: <b>{snap['tasks_total']}</b> (активных: {snap['tasks_active']})",
        ]
        if snap["task_lines"]:
            mlines.append("Список заданий:")
            mlines.extend(snap["task_lines"])
        else:
            mlines.append("Заданий пока нет.")
        mlines.extend(
            [
                "",
                f"✅ Завершённых выполнений по его заданиям: <b>{snap['executions_completed']}</b>",
                f"   └ Оплачено менеджером (кнопка «Оплатить»): "
                f"<b>{snap['paid_by_manager_count']}</b> шт. на <b>{snap['sum_paid_out_rub']:.2f}</b> руб.",
                f"   └ Ждут оплаты от менеджера исполнителю: "
                f"<b>{snap['awaiting_manager_payment_count']}</b> шт. на <b>{snap['sum_awaiting_manager_rub']:.2f}</b> руб.",
                "",
                f"🔄 Попыток сейчас в работе (модерация профиля / отзыв): <b>{snap['attempts_in_progress']}</b>",
            ]
        )
        mtext = "\n".join(mlines)
        for chunk in _telegram_text_chunks(mtext):
            await cb.message.answer(chunk, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:secacc_ok:"))
async def admin_secacc_ok(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    rid = int(cb.data.split(":")[2])
    sar = SecondAccountReviewRepository(session)
    rev = await sar.approve(rid)
    if not rev:
        await cb.message.answer("Уже обработано или заявка не найдена.")
        return
    await UserRepository(session).set_repeat_unlock_platform(rev.user_id, rev.platform, True)
    try:
        await cb.bot.send_message(
            rev.user_id,
            "✅ Второй аккаунт подтверждён. Снова нажмите «Приступить к заданию», выберите эту платформу и возьмите задание.",
        )
    except Exception:
        pass
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:secacc_reject:"))
async def admin_secacc_reject(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    rid = int(cb.data.split(":")[2])
    sar = SecondAccountReviewRepository(session)
    rev = await sar.reject(rid, None)
    if not rev:
        await cb.message.answer("Уже обработано или заявка не найдена.")
        return
    try:
        await cb.bot.send_message(
            rev.user_id,
            "❌ Проверка второго аккаунта не пройдена. Повторные задания на этой площадке недоступны.",
        )
    except Exception:
        pass
    await cb.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("admin:allow:"))
async def allow_attempt(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.get_by_id(attempt_id)
    if not attempt:
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    if not task:
        return

    selected_prebuilt_text: str | None = None

    # Если у задания есть готовые тексты — выдаём их по очереди по одному исполнителю.
    prebuilt_texts: list[str] = []
    try:
        prebuilt_texts = json.loads(getattr(task, "prebuilt_texts_json", "[]") or "[]")
        if not isinstance(prebuilt_texts, list):
            prebuilt_texts = []
    except Exception:
        prebuilt_texts = []

    cursor = int(getattr(task, "prebuilt_text_cursor", 0) or 0)
    if prebuilt_texts and cursor < len(prebuilt_texts):
        selected_prebuilt_text = prebuilt_texts[cursor]
        task.prebuilt_text_cursor = cursor + 1

        # Когда тексты закончатся — отключаем задание и уведомляем владельца.
        if task.prebuilt_text_cursor >= len(prebuilt_texts):
            task.is_active = False
            if task.created_by_user_id is not None and not getattr(task, "prebuilt_texts_exhausted_notified", False):
                task.prebuilt_texts_exhausted_notified = True
                try:
                    await cb.bot.send_message(
                        task.created_by_user_id,
                        "⚠️ Ваши готовые тексты для задания закончились.\n"
                        f"Задание #{task.id} больше не будет выдаваться.\n\n"
                        "Пожалуйста, удалите это задание и создайте новое с новыми текстами.",
                    )
                except Exception:
                    pass

        await session.flush()
    elif prebuilt_texts and cursor >= len(prebuilt_texts):
        # Тексты уже закончились: не одобряем попытку.
        if task.created_by_user_id is not None:
            if not getattr(task, "prebuilt_texts_exhausted_notified", False):
                task.prebuilt_texts_exhausted_notified = True
            task.is_active = False
            try:
                await cb.bot.send_message(
                    task.created_by_user_id,
                    "⚠️ Ваши готовые тексты для задания уже закончились.\n"
                    f"Задание #{task.id} отключено.",
                )
            except Exception:
                pass

        await attempt_repo.decline(attempt_id, "Готовые тексты для задания закончились.")
        await cb.message.edit_reply_markup(reply_markup=None)
        try:
            await cb.bot.send_message(
                attempt.user_id,
                "К сожалению, готовые тексты для этого задания закончились. Попробуйте выбрать другое задание в меню.",
                reply_markup=main_menu(),
            )
        except Exception:
            pass
        return

    attempt = await attempt_repo.approve(attempt_id)
    if not attempt:
        return
    text = (
        f"✅ Вы допущены! Ваша инструкция: {task.instruction_url}\n\n"
        "✍️ Этап 2/3: Опубликуйте отзыв по инструкции и пришлите сюда скриншот готового отзыва.\n"
    )
    if selected_prebuilt_text:
        text += f"\n📝 Готовый текст для отзыва:\n{selected_prebuilt_text}\n"
    text += "\n❗️ Перед отправкой скрина укажите реквизиты для выплаты: «💰 Личный кабинет / Баланс» → «✏️ Редактировать реквизиты»."

    await cb.bot.send_message(attempt.user_id, text, reply_markup=cancel_attempt_kb())
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
    attempt_id = int(cb.data.split(":")[2])
    attempt = await attempt_repo.complete(attempt_id)
    if not attempt:
        return
    task = await task_repo.get_by_id(attempt.task_item_id)
    if not task:
        return

    # Задание менеджера: деньги после нажатия «Оплатил» у менеджера
    if task.created_by_user_id is not None:
        req = (attempt.payout_requisites or "").strip() or "не указаны"
        mgr_id = task.created_by_user_id
        notify = (
            "✅ Отзыв по вашему заданию подтверждён проверяющим.\n"
            f"Задание #{task.id} | {task.platform}\n"
            f"Сумма к выплате: {float(task.price):.2f} руб.\n\n"
            f"Реквизиты исполнителя:\n{req}\n\n"
            "Вы оплатили этот отзыв✅"
        )
        try:
            await cb.bot.send_message(mgr_id, notify, reply_markup=manager_payout_kb(attempt_id))
        except Exception:
            pass
        await cb.bot.send_message(
            attempt.user_id,
            "✅ Отзыв принят проверяющим. После оплаты от заказчика вознаграждение будет зачислено на баланс.",
        )
        await cb.message.edit_reply_markup(reply_markup=None)
        return

    amount = await grant_task_completion_rewards(session, attempt.user_id, task)
    await attempt_repo.mark_balance_credited(attempt_id)
    await cb.bot.send_message(attempt.user_id, f"✅ Ваш отзыв принят и оплачен! На баланс зачислено {amount:.2f} руб.")
    for aid in ADMIN_IDS:
        try:
            await cb.bot.send_message(
                aid,
                "✅ Отзыв оплачен (вознаграждение зачислено исполнителю на баланс в боте).\n"
                f"Исполнитель ID: {attempt.user_id}\n"
                f"Задание #{task.id} | {task.platform}\n"
                f"Сумма: {amount:.2f} руб.",
            )
        except Exception:
            pass
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


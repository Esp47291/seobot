# -*- coding: utf-8 -*-
"""Админ-панель: модерация отзывов, ссылки, обучение, рассылка."""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import (
    UserRepository,
    LinkRepository,
    ReviewTextRepository,
    TrainingMessageRepository,
    TaskRepository,
    AdminActionRepository,
)
from keyboards.admin import (
    kb_admin_main,
    kb_admin_back,
    kb_task_approve_reject,
    kb_task_paid,
    kb_links_manage,
    kb_edit_training_step,
    ADMIN_BACK,
    ADMIN_UNVERIFIED,
    ADMIN_APPROVED_UNPAID,
    ADMIN_LINKS,
    ADMIN_TRAINING,
    ADMIN_WRITE_USER,
    ADMIN_APPROVE,
    ADMIN_REJECT,
    ADMIN_PAID,
    ADMIN_LINK_ADD,
    ADMIN_LINK_LIST,
    ADMIN_TRAINING_EDIT,
)
from utils.fsm import AdminFSM
from config import TRAINING_STEPS

router = Router(name="admin")


def _platform_label(platform: str) -> str:
    return "Яндекс" if platform == "yandex" else "2ГИС"


# ---------- /admin ----------
@router.message(Command("admin"))
async def cmd_admin(message: Message, **data):
    session = data["session"]
    await message.answer("Админ-панель:", reply_markup=kb_admin_main())


# ---------- Назад ----------
@router.callback_query(F.data == ADMIN_BACK)
async def admin_back(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    if cb.message.photo:
        await cb.message.delete()
    try:
        await cb.message.edit_text("Админ-панель:", reply_markup=kb_admin_main())
    except Exception:
        await cb.message.answer("Админ-панель:", reply_markup=kb_admin_main())


# ---------- Непроверенные отзывы ----------
def _build_unverified_kb(tasks):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t in tasks:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"#{t.id} {t.user.username or t.user_id}",
                callback_data=f"admin_task:{t.id}",
            )
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)])
    return kb


@router.callback_query(F.data == ADMIN_UNVERIFIED)
async def admin_unverified_list(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskRepository(session)
    tasks = await task_repo.get_pending()
    if not tasks:
        text = "Нет непроверенных отзывов."
        reply_markup = kb_admin_back()
    else:
        lines = []
        for t in tasks:
            user = t.user
            link = t.link
            uname = f"@{user.username}" if user and user.username else str(t.user_id)
            lines.append(f"• #{t.id} — {uname} — {link.url[:50]}... — {t.created_at.strftime('%d.%m %H:%M')}")
        text = "Непроверенные отзывы:\n\n" + "\n".join(lines)
        reply_markup = _build_unverified_kb(tasks)
    if cb.message.photo:
        await cb.message.delete()
        await cb.message.answer(text, reply_markup=reply_markup)
    else:
        await cb.message.edit_text(text, reply_markup=reply_markup)


@router.callback_query(F.data.startswith("admin_task:"))
async def admin_task_detail(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_id = int(cb.data.split(":")[1])
    task_repo = TaskRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task:
        await cb.answer("Задание не найдено.", show_alert=True)
        return
    if task.status != "pending":
        await cb.answer("Задание уже обработано.", show_alert=True)
        return
    user = task.user
    link = task.link
    text_content = task.review_text.text if task.review_text else "—"
    uname = f"@{user.username}" if user and user.username else str(task.user_id)
    body = (
        f"Задание #{task.id}\n"
        f"Пользователь: {uname} (ID: {task.user_id})\n"
        f"Платформа: {_platform_label(link.platform)}\n"
        f"Ссылка: {link.url}\n\n"
        f"Текст отзыва:\n{text_content}\n\n"
        f"Реквизиты: {task.payment_details or '—'}"
    )
    if task.screenshot_file_id:
        await cb.message.answer_photo(
            task.screenshot_file_id,
            caption=body,
            reply_markup=kb_task_approve_reject(task_id),
        )
    else:
        await cb.message.edit_text(body, reply_markup=kb_task_approve_reject(task_id))


@router.callback_query(F.data.startswith(f"{ADMIN_APPROVE}"))
async def admin_approve(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_id = int(cb.data.replace(ADMIN_APPROVE, ""))
    task_repo = TaskRepository(session)
    action_repo = AdminActionRepository(session)
    task = await task_repo.approve(task_id)
    if not task:
        await cb.answer("Ошибка или задание уже обработано.", show_alert=True)
        return
    await action_repo.log(cb.from_user.id, "approve", task_id)
    if cb.message.photo and cb.message.caption:
        await cb.message.edit_caption(caption=cb.message.caption + "\n\n✅ Подтверждено.")
    else:
        await cb.message.edit_text((cb.message.text or cb.message.caption or "") + "\n\n✅ Подтверждено.")
    await cb.message.edit_reply_markup(reply_markup=kb_admin_back())
    try:
        await cb.bot.send_message(
            task.user_id,
            "✅ Ваш отзыв одобрен. Ожидайте выплату — после перевода вам придёт уведомление.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith(ADMIN_REJECT))
async def admin_reject(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_id = int(cb.data.replace(ADMIN_REJECT, ""))
    task_repo = TaskRepository(session)
    action_repo = AdminActionRepository(session)
    task = await task_repo.reject(task_id)
    if not task:
        await cb.answer("Ошибка или задание уже обработано.", show_alert=True)
        return
    await action_repo.log(cb.from_user.id, "reject", task_id)
    if cb.message.photo and cb.message.caption:
        await cb.message.edit_caption(caption=cb.message.caption + "\n\n❌ Отклонено.")
    else:
        await cb.message.edit_text((cb.message.text or cb.message.caption or "") + "\n\n❌ Отклонено.")
    await cb.message.edit_reply_markup(reply_markup=kb_admin_back())
    try:
        await cb.bot.send_message(
            task.user_id,
            "❌ Ваш отзыв отклонён. Вы можете взять новое задание.",
        )
    except Exception:
        pass


# ---------- Подтверждённые, не оплаченные ----------
@router.callback_query(F.data == ADMIN_APPROVED_UNPAID)
async def admin_approved_unpaid_list(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_repo = TaskRepository(session)
    tasks = await task_repo.get_approved_unpaid()
    if not tasks:
        await cb.message.edit_text(
            "Нет подтверждённых неоплаченных заданий.",
            reply_markup=kb_admin_back(),
        )
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    lines = [f"• #{t.id} — @{t.user.username or t.user_id} — {t.payment_details[:30] if t.payment_details else '—'}..." for t in tasks]
    text = "Подтверждённые, не оплаченные:\n\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for t in tasks:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"#{t.id} Выплатить", callback_data=f"{ADMIN_PAID}{t.id}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)])
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith(ADMIN_PAID))
async def admin_mark_paid(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    task_id = int(cb.data.replace(ADMIN_PAID, ""))
    task_repo = TaskRepository(session)
    action_repo = AdminActionRepository(session)
    task = await task_repo.mark_paid(task_id)
    if not task:
        await cb.answer("Ошибка или задание уже оплачено.", show_alert=True)
        return
    await action_repo.log(cb.from_user.id, "paid", task_id)
    try:
        await cb.bot.send_message(
            task.user_id,
            "💰 Выплата выполнена. Спасибо за работу!",
        )
    except Exception:
        pass
    await cb.answer("Отмечено как выплачено. Пользователь уведомлён.", show_alert=True)
    # Обновить список
    tasks = await task_repo.get_approved_unpaid()
    if not tasks:
        await cb.message.edit_text(
            "Нет подтверждённых неоплаченных заданий.",
            reply_markup=kb_admin_back(),
        )
    else:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        lines = [f"• #{t.id} — @{t.user.username or t.user_id}" for t in tasks]
        text = "Подтверждённые, не оплаченные:\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for t in tasks:
            kb.inline_keyboard.append([
                InlineKeyboardButton(text=f"#{t.id} Выплатить", callback_data=f"{ADMIN_PAID}{t.id}")
            ])
        kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)])
        await cb.message.edit_text(text, reply_markup=kb)


# ---------- Управление ссылками ----------
@router.callback_query(F.data == ADMIN_LINKS)
async def admin_links_menu(cb: CallbackQuery, **data):
    await cb.answer()
    await cb.message.edit_text(
        "Управление ссылками: добавление, список, тексты к ссылкам.",
        reply_markup=kb_links_manage(),
    )


# ---------- Написать пользователю ----------
@router.callback_query(F.data == ADMIN_WRITE_USER)
async def admin_write_user_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_username)
    await state.update_data(admin_action="write_user_username")
    await cb.message.edit_text(
        "Введите @username пользователя (например @username или username).",
        reply_markup=kb_admin_back(),
    )


@router.callback_query(F.data == ADMIN_LINK_ADD)
async def admin_link_add_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_username)  # переиспользуем состояние: сначала платформа
    await state.update_data(admin_action="link_add_platform")
    await cb.message.edit_text(
        "Отправьте платформу: yandex или 2gis (одним сообщением).",
        reply_markup=kb_admin_back(),
    )


# Общий хендлер для ввода текста в админке (платформа → url → текст для ссылки; или username → сообщение)
@router.message(AdminFSM.waiting_username, F.text)
async def admin_fsm_text(message: Message, state: FSMContext, **data):
    session = data["session"]
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    d = await state.get_data()
    action = d.get("admin_action")

    if action == "link_add_platform":
        platform = (message.text or "").strip().lower()
        if platform not in ("yandex", "2gis"):
            await message.answer("Напишите yandex или 2gis.")
            return
        await state.update_data(link_platform=platform, admin_action="link_add_url")
        await message.answer("Теперь отправьте ссылку на бизнес (одним сообщением).")
        return

    if action == "link_add_url":
        url = (message.text or "").strip()
        if not url.startswith("http"):
            await message.answer("Отправьте корректную ссылку (начинается с http).")
            return
        link_repo = LinkRepository(session)
        existing = await link_repo.get_by_url(url)
        if existing:
            await message.answer("Такая ссылка уже есть.")
            await state.clear()
            return
        platform = d.get("link_platform", "yandex")
        link = await link_repo.create(platform=platform, url=url)
        await state.clear()
        await message.answer(f"Ссылка добавлена (ID: {link.id}). Добавить тексты отзывов можно в «Список ссылок».")
        return

    if action == "write_user_username":
        username = (message.text or "").strip().strip("@")
        if not username:
            await message.answer("Введите @username пользователя.")
            return
        user_repo = UserRepository(session)
        user = await user_repo.get_by_username(username)
        if not user:
            await message.answer("Пользователь с таким username не найден.")
            return
        await state.update_data(target_user_id=user.user_id, admin_action="write_user_message")
        await message.answer("Теперь отправьте текст сообщения для пользователя.")
        return

    if action == "write_user_message":
        target_user_id = d.get("target_user_id")
        if not target_user_id:
            await state.clear()
            return
        try:
            await message.bot.send_message(target_user_id, f"📩 Сообщение от администратора:\n\n{message.text}")
            await message.answer("Сообщение отправлено.")
        except Exception as e:
            await message.answer(f"Не удалось отправить: {e}")
        await state.clear()
        return

    await state.clear()


# Список ссылок с кнопками: выбрать ссылку → добавить/удалить текст, деактивировать ссылку
@router.callback_query(F.data == ADMIN_LINK_LIST)
async def admin_link_list(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    link_repo = LinkRepository(session)
    links = await link_repo.get_all()
    if not links:
        await cb.message.edit_text(
            "Нет ссылок. Добавьте через кнопку «Добавить ссылку».",
            reply_markup=kb_links_manage(),
        )
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for link in links:
        status = "✅" if link.is_active else "❌"
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status} #{link.id} {link.platform}",
                callback_data=f"admin_link_detail:{link.id}",
            )
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_LINKS)])
    text = "Ссылки (нажмите для управления текстами и активностью):\n\n" + "\n".join(
        [f"#{l.id} {l.platform} — {l.url[:60]}..." for l in links]
    )
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin_link_detail:"))
async def admin_link_detail(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    link_id = int(cb.data.split(":")[1])
    link_repo = LinkRepository(session)
    text_repo = ReviewTextRepository(session)
    link = await link_repo.get_by_id(link_id)
    if not link:
        await cb.answer("Ссылка не найдена.", show_alert=True)
        return
    texts = await text_repo.get_active_by_link_id(link_id)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    toggle_label = "❌ Деактивировать" if link.is_active else "✅ Активировать"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить текст отзыва", callback_data=f"admin_text_add:{link_id}")],
        [InlineKeyboardButton(text=toggle_label, callback_data=f"admin_link_toggle:{link_id}")],
        [InlineKeyboardButton(text="◀ К списку ссылок", callback_data=ADMIN_LINK_LIST)],
    ])
    text = f"Ссылка #{link.id} ({link.platform})\n{link.url}\nАктивна: {link.is_active}\n\nТексты ({len(texts)}):"
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin_link_toggle:"))
async def admin_link_toggle(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    link_id = int(cb.data.split(":")[1])
    link_repo = LinkRepository(session)
    link = await link_repo.get_by_id(link_id)
    if not link:
        await cb.answer("Ссылка не найдена.", show_alert=True)
        return
    await link_repo.set_active(link_id, not link.is_active)
    await cb.answer(f"Ссылка {'активна' if not link.is_active else 'деактивирована'}.", show_alert=True)
    # Обновить экран детали ссылки
    link = await link_repo.get_by_id(link_id)
    text_repo = ReviewTextRepository(session)
    texts = await text_repo.get_active_by_link_id(link_id)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    toggle_label = "❌ Деактивировать" if link.is_active else "✅ Активировать"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить текст отзыва", callback_data=f"admin_text_add:{link_id}")],
        [InlineKeyboardButton(text=toggle_label, callback_data=f"admin_link_toggle:{link_id}")],
        [InlineKeyboardButton(text="◀ К списку ссылок", callback_data=ADMIN_LINK_LIST)],
    ])
    text = f"Ссылка #{link.id} ({link.platform})\n{link.url}\nАктивна: {link.is_active}\n\nТексты ({len(texts)}):"
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("admin_text_add:"))
async def admin_text_add_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    link_id = int(cb.data.split(":")[1])
    await state.set_state(AdminFSM.waiting_message)
    await state.update_data(admin_action="text_add", text_add_link_id=link_id)
    await cb.message.edit_text("Отправьте текст отзыва (одним сообщением). Для отмены отправьте /cancel.")


@router.message(AdminFSM.waiting_message, F.text)
async def admin_fsm_message(message: Message, state: FSMContext, **data):
    session = data["session"]
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    d = await state.get_data()
    action = d.get("admin_action")
    if action == "text_add":
        link_id = d.get("text_add_link_id")
        if not link_id:
            await state.clear()
            return
        text_repo = ReviewTextRepository(session)
        await text_repo.create(link_id=link_id, text=message.text or "")
        await state.clear()
        await message.answer("Текст отзыва добавлен.")
        return
    if action == "training_edit":
        step = d.get("training_step")
        if step is None:
            await state.clear()
            return
        training_repo = TrainingMessageRepository(session)
        await training_repo.set_text(step, message.text or "")
        await state.clear()
        await message.answer(f"Текст шага {step} обновлён.")
        return
    await state.clear()


# ---------- Редактировать обучение ----------
@router.callback_query(F.data == ADMIN_TRAINING)
async def admin_training_menu(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    training_repo = TrainingMessageRepository(session)
    await training_repo.ensure_steps_exist()
    messages = await training_repo.get_all_ordered()
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for m in messages:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"Шаг {m.step_number}",
                callback_data=f"{ADMIN_TRAINING_EDIT}{m.step_number}",
            )
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)])
    text = "Редактирование обучения. Выберите шаг:"
    await cb.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith(ADMIN_TRAINING_EDIT))
async def admin_training_edit_step(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    step = int(cb.data.replace(ADMIN_TRAINING_EDIT, ""))
    await state.set_state(AdminFSM.waiting_message)
    await state.update_data(admin_action="training_edit", training_step=step)
    await cb.message.edit_text(f"Отправьте новый текст для шага {step}. Для отмены — /cancel.")


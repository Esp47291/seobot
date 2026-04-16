# -*- coding: utf-8 -*-
"""Панель менеджера: /manager — свои задания, личная рассылка, выплаты исполнителям по кнопке «Оплатил»."""
import json
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


def _is_image_document_for_preb(doc) -> bool:
    """Проверка, что документ — картинка (для готовых материалов с фото)."""
    if not doc:
        return False
    mt = (getattr(doc, "mime_type", None) or "").lower()
    if mt.startswith("image/"):
        return True
    name = (getattr(doc, "file_name", None) or "").lower()
    return any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"))

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
                [InlineKeyboardButton(text="✏️ Изменить объявление", callback_data="mgr:tasks_edit")],
                [InlineKeyboardButton(text="🗑️ Удалить задание", callback_data="mgr:tasks_delete")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="mgr:back_main")],
            ]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_edit")
async def mgr_tasks_edit_menu(cb: CallbackQuery, state: FSMContext, **data):
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
        kb.inline_keyboard.append([InlineKeyboardButton(text=label, callback_data=f"mgr:tasks_edit_pick:{item.id}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀ Назад", callback_data="mgr:tasks")])

    await cb.message.answer("Выберите задание для изменения:\n\n" + "\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("mgr:tasks_edit_pick:"))
async def mgr_tasks_edit_pick(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.clear()
    task_id = int(cb.data.split(":")[2])
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task or task.created_by_user_id != cb.from_user.id:
        await cb.message.answer("Задание не найдено или это не ваше задание.", reply_markup=manager_main())
        return

    await state.update_data(edit_task_id=task_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Цена", callback_data=f"mgr:tasks_edit_field:{task_id}:price")],
            [InlineKeyboardButton(text="🏙️ Город организации", callback_data=f"mgr:tasks_edit_field:{task_id}:venue_city")],
            [InlineKeyboardButton(text="🏷️ Сфера", callback_data=f"mgr:tasks_edit_field:{task_id}:sphere")],
            [InlineKeyboardButton(text="📝 Инструкция/ссылка (полностью)", callback_data=f"mgr:tasks_edit_field:{task_id}:instruction_url")],
            [InlineKeyboardButton(text="📆 Лимит в день", callback_data=f"mgr:tasks_edit_field:{task_id}:daily_issue_count")],
            [InlineKeyboardButton(text="🔁 Вкл/выкл", callback_data=f"mgr:tasks_edit_field:{task_id}:toggle_active")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="mgr:tasks_edit")],
        ]
    )
    await cb.message.answer(
        f"✏️ Редактирование задания #{task.id}\n"
        f"{task.platform} | {(getattr(task, 'venue_city', '') or '—').strip()} | {(task.sphere or '—').strip()} | {float(task.price):.2f} руб.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mgr:tasks_edit_field:"))
async def mgr_tasks_edit_field(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    parts = cb.data.split(":")
    task_id = int(parts[2])
    field = parts[3]
    session = data["session"]
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task or task.created_by_user_id != cb.from_user.id:
        await state.clear()
        await cb.message.answer("Задание не найдено или это не ваше задание.", reply_markup=manager_main())
        return

    if field == "toggle_active":
        await task_repo.toggle_active(task_id)
        await state.clear()
        await cb.message.answer("✅ Готово: статус задания переключён.", reply_markup=manager_main())
        return

    await state.set_state(ManagerFSM.waiting_task_edit_value)
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

    await cb.message.answer(prompt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="mgr:back_main")]]))


@router.message(ManagerFSM.waiting_task_edit_value, F.text)
async def mgr_tasks_edit_value_save(message: Message, state: FSMContext, **data):
    session = data["session"]
    task_repo = TaskItemRepository(session)
    settings = await SettingsRepository(session).get()

    d = await state.get_data()
    task_id = int(d.get("edit_task_id") or 0)
    field = (d.get("edit_field") or "").strip()
    task = await task_repo.get_by_id(task_id)
    if not task or task.created_by_user_id != message.from_user.id:
        await state.clear()
        await message.answer("Задание не найдено или это не ваше задание.", reply_markup=manager_main())
        return

    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return

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
        await message.answer("Не удалось сохранить (проверьте значение).", reply_markup=manager_main())
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Изменение сохранено.", reply_markup=manager_main())


@router.callback_query(F.data == "mgr:tasks_add")
async def mgr_tasks_add_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer(
        "Шаг 1/8.\nВыберите платформу:",
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
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:2gis")
async def mgr_tasks_plat_2gis(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_price)
    await state.update_data(platform="2ГИС")
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:google")
async def mgr_tasks_plat_google(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_price)
    await state.update_data(platform="Google карты")
    await cb.message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


@router.callback_query(F.data == "mgr:tasks_plat:other")
async def mgr_tasks_plat_other(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await state.set_state(ManagerFSM.waiting_task_platform)
    await cb.message.answer("Шаг 1/8.\nНапишите название платформы.\n\nПример: `Яндекс карты`")


@router.message(ManagerFSM.waiting_task_platform, F.text)
async def mgr_tasks_add_platform(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    await state.update_data(platform=message.text.strip())
    await state.set_state(ManagerFSM.waiting_task_price)
    await message.answer("Шаг 2/8.\nНапишите цену за отзыв (число). Например: 120")


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
        "Шаг 3/8.\nУкажите <b>город организации</b> (где находится заведение). "
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
        "Шаг 4/8.\nУкажите <b>сферу бизнеса</b> организации (исполнитель увидит это на карточке).\n\n"
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
    await message.answer("Шаг 5/8.\nНапишите инструкцию для исполнителя.")


@router.message(ManagerFSM.waiting_task_instruction, F.text)
async def mgr_tasks_add_instruction(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return
    await state.update_data(instruction_text=message.text.strip())
    await state.set_state(ManagerFSM.waiting_task_prebuilt_mode)

    await message.answer(
        "Шаг 6/8.\nДобавить готовые тексты для отзыва?\n\n"
        "После этого задания новые тексты добавить будет нельзя.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Готовые тексты", callback_data="mgr:tasks_prebuilt_yes")],
                [InlineKeyboardButton(text="✅ Готовые тексты с фото", callback_data="mgr:tasks_prebuilt_yes_photo")],
                [InlineKeyboardButton(text="⏭️ Без готовых текстов", callback_data="mgr:tasks_prebuilt_no")],
            ]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_prebuilt_yes")
async def mgr_tasks_prebuilt_yes(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(prebuilt_texts=[])
    await state.set_state(ManagerFSM.waiting_task_prebuilt_texts)
    await cb.message.answer(
        "Шаг 6/8.\nОтправляйте готовые тексты по очереди: 1 текст = 1 сообщение.\n"
        "Каждый текст будет выдан только одному исполнителю.\n\n"
        "Когда закончите — нажмите «✅ Готово».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="mgr:tasks_prebuilt_done")]]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_prebuilt_yes_photo")
async def mgr_tasks_prebuilt_yes_photo(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(prebuilt_texts=[])
    await state.set_state(ManagerFSM.waiting_task_prebuilt_texts_with_photo)
    await cb.message.answer(
        "Шаг 6/8.\nОтправляйте материалы по очереди: 1 сообщение = 1 готовый вариант для отзыва.\n\n"
        "Можно так:\n"
        "• фото с подписью (текстом)\n"
        "• просто фото\n"
        "• просто текст\n\n"
        "Каждый вариант будет выдан только одному исполнителю.\n"
        "Когда закончите — нажмите «✅ Готово».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="mgr:tasks_prebuilt_done")]]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_prebuilt_no")
async def mgr_tasks_prebuilt_no(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(prebuilt_texts=[])
    await state.set_state(ManagerFSM.waiting_task_prebuilt_mode)

    await cb.message.answer(
        "Шаг 7/8.\nСколько раз ваше задание нужно выдавать в день?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1", callback_data="mgr:tasks_daily:1")],
                [InlineKeyboardButton(text="2", callback_data="mgr:tasks_daily:2")],
                [InlineKeyboardButton(text="5", callback_data="mgr:tasks_daily:5")],
                [InlineKeyboardButton(text="Свой вариант (1..10)", callback_data="mgr:tasks_daily:custom")],
            ]
        ),
    )


@router.message(ManagerFSM.waiting_task_prebuilt_texts, F.text)
async def mgr_tasks_prebuilt_texts_collect(message: Message, state: FSMContext, **data):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return

    text = message.text.strip()
    if not text:
        return

    d = await state.get_data()
    texts = list(d.get("prebuilt_texts") or [])
    texts.append(text)
    await state.update_data(prebuilt_texts=texts)

    await message.answer(
        f"✅ Текст добавлен (всего: {len(texts)}). Отправьте следующий или нажмите «✅ Готово».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="mgr:tasks_prebuilt_done")]]
        ),
    )


@router.message(ManagerFSM.waiting_task_prebuilt_texts_with_photo)
async def mgr_tasks_prebuilt_texts_with_photo_collect_any(message: Message, state: FSMContext, **data):
    """
    Общий обработчик для режима "готовые тексты с фото" у менеджера.
    Telegram иногда присылает картинку как Document, иногда как Photo — либо в нестандартном виде при paste.
    Этот хендлер гарантирует ответ и корректный сбор материалов.
    """
    # Общий /cancel (на случай, если пользователь введёт его текстом)
    if (message.text or "").strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return

    d = await state.get_data()
    texts = list(d.get("prebuilt_texts") or [])

    caption = (message.caption or "").strip()
    if caption == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
        return

    item: dict[str, str] | None = None
    if message.text:
        raw = message.text.strip()
        if raw:
            item = {"text": raw}
    elif message.photo:
        item = {"photo_file_id": message.photo[-1].file_id}
        if caption:
            item["text"] = caption
    elif message.document:
        if not _is_image_document_for_preb(message.document):
            await message.answer("Пришлите картинку (PNG/JPG) либо текст.")
            return
        item = {"photo_file_id": message.document.file_id}
        if caption:
            item["text"] = caption

    if not item:
        await message.answer("Пришлите картинку (PNG/JPG) или текст для готового варианта.")
        return

    texts.append(item)
    await state.update_data(prebuilt_texts=texts)

    await message.answer(
        f"✅ Материал добавлен (всего: {len(texts)}). Отправьте следующий вариант или нажмите «✅ Готово».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="mgr:tasks_prebuilt_done")]]
        ),
    )


@router.callback_query(F.data == "mgr:tasks_prebuilt_done")
async def mgr_tasks_prebuilt_done(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    d = await state.get_data()
    texts = list(d.get("prebuilt_texts") or [])
    if not texts:
        await cb.message.answer("Сначала добавьте хотя бы 1 готовый вариант (текст/фото).")
        return

    await state.set_state(ManagerFSM.waiting_task_prebuilt_mode)

    await cb.message.answer(
        "Шаг 7/8.\nСколько раз ваше задание нужно выдавать в день?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1", callback_data="mgr:tasks_daily:1")],
                [InlineKeyboardButton(text="2", callback_data="mgr:tasks_daily:2")],
                [InlineKeyboardButton(text="5", callback_data="mgr:tasks_daily:5")],
                [InlineKeyboardButton(text="Свой вариант (1..10)", callback_data="mgr:tasks_daily:custom")],
            ]
        ),
    )


@router.callback_query(F.data.in_(["mgr:tasks_daily:1", "mgr:tasks_daily:2", "mgr:tasks_daily:5"]))
async def mgr_tasks_daily_fixed(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    value = int(cb.data.split(":")[-1])
    await state.update_data(daily_issue_count=value)
    await state.set_state(ManagerFSM.waiting_task_venue_link)
    await cb.message.answer("Шаг 8/8.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


@router.callback_query(F.data == "mgr:tasks_daily:custom")
async def mgr_tasks_daily_custom_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(ManagerFSM.waiting_task_daily_custom)
    await cb.message.answer("Введите число от 1 до 10.")


@router.message(ManagerFSM.waiting_task_daily_custom, F.text)
async def mgr_tasks_daily_custom_finish(message: Message, state: FSMContext):
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=manager_main())
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
    await state.set_state(ManagerFSM.waiting_task_venue_link)
    await message.answer("Шаг 8/8.\nДобавьте ссылку на заведение, где нужно оставить отзыв.")


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


@router.callback_query(F.data == "mgr:tasks_analytics")
async def mgr_tasks_analytics(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    rows = await StatsRepository(session).tasks_analytics_rows(
        owner_filter="manager",
        manager_user_id=cb.from_user.id,
        limit=40,
    )
    lines = ["📈 <b>Ваши задания</b>", ""]
    if not rows:
        lines.append("У вас пока нет заданий.")
    else:
        for item in rows:
            t = item["task"]
            lines.append(
                f"#{t.id} {t.platform} | {item['venue_city_short']} | {item['sphere_short']}\n"
                f"   активно: {'да' if t.is_active else 'нет'}\n"
                f"   попыток: {item['attempts_total']} | completed: {item['completed_n']} | "
                f"ждут вашей оплаты: {item['awaiting_manager_pay']} | вы отметили оплату: {item['paid_by_manager']}\n"
            )
    text = "\n".join(lines)
    max_len = 3800
    if len(text) <= max_len:
        await cb.message.answer(text, parse_mode="HTML")
        return
    chunk: list[str] = []
    cur = 0
    for line in text.split("\n"):
        add = len(line) + (1 if chunk else 0)
        if cur + add > max_len and chunk:
            await cb.message.answer("\n".join(chunk), parse_mode="HTML")
            chunk = [line]
            cur = len(line)
        else:
            chunk.append(line)
            cur += add
    if chunk:
        await cb.message.answer("\n".join(chunk), parse_mode="HTML")


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

# -*- coding: utf-8 -*-
"""Хендлеры пользователя: старт, обучение, взятие задания, отправка на проверку."""

import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from database import (
    UserRepository,
    LinkRepository,
    ReviewTextRepository,
    TrainingMessageRepository,
    TaskRepository,
)
from keyboards.user import (
    kb_next_training,
    kb_after_training,
    kb_take_task,
    kb_sent_for_review,
    CALLBACK_NEXT,
    CALLBACK_TAKE,
    CALLBACK_SENT,
)
from utils.fsm import UserFSM
from config import TRAINING_STEPS

router = Router(name="user")


def _platform_label(platform: str) -> str:
    return "Яндекс Карты" if platform == "yandex" else "2ГИС"


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, **data):
    await state.clear()
    session = data["session"]
    repo = UserRepository(session)
    user = await repo.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    training_repo = TrainingMessageRepository(session)
    await training_repo.ensure_steps_exist()
    first = await training_repo.get_by_step(1)
    if not first:
        await message.answer("Настройте обучение в админ-панели.")
        return
    await state.set_state(UserFSM.training_step)
    await state.update_data(training_step=1)
    await message.answer(
        first.text,
        reply_markup=kb_next_training(1, TRAINING_STEPS),
    )


@router.callback_query(F.data.startswith(f"{CALLBACK_NEXT}:"))
async def training_next(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    step = int(cb.data.split(":")[1])
    next_step = step + 1
    training_repo = TrainingMessageRepository(session)
    if next_step > TRAINING_STEPS:
        await state.clear()
        await cb.message.edit_text(
            "Обучение завершено. Можете брать задание.",
            reply_markup=kb_after_training(),
        )
        return
    msg = await training_repo.get_by_step(next_step)
    if not msg:
        await state.clear()
        await cb.message.edit_text("Ошибка: шаг обучения не найден.", reply_markup=kb_after_training())
        return
    await state.update_data(training_step=next_step)
    await cb.message.edit_text(
        msg.text,
        reply_markup=kb_next_training(next_step, TRAINING_STEPS),
    )


@router.callback_query(F.data == CALLBACK_TAKE)
async def take_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    await state.clear()
    user_id = cb.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if not user:
        await cb.message.answer("Сначала нажмите /start")
        return

    link_repo = LinkRepository(session)
    text_repo = ReviewTextRepository(session)
    task_repo = TaskRepository(session)

    # Проверяем лимиты по платформам и выбираем доступную
    yandex_links = await link_repo.get_active_by_platform("yandex")
    twogis_links = await link_repo.get_active_by_platform("2gis")
    available_links = []
    if yandex_links and task_repo.can_take_task(user.last_yandex_review, "yandex"):
        available_links.extend(yandex_links)
    if twogis_links and task_repo.can_take_task(user.last_2gis_review, "2gis"):
        available_links.extend(twogis_links)

    if not available_links:
        parts = []
        if yandex_links and not task_repo.can_take_task(user.last_yandex_review, "yandex"):
            parts.append("Яндекс Карты: лимит 1 раз в 24 ч.")
        if twogis_links and not task_repo.can_take_task(user.last_2gis_review, "2gis"):
            parts.append("2ГИС: лимит 1 раз в 2 ч.")
        if not yandex_links and not twogis_links:
            await cb.message.answer("Нет доступных заданий. Попробуйте позже.")
        else:
            await cb.message.answer(
                "Сейчас вы не можете взять задание:\n" + "\n".join(parts) + "\n\nПопробуйте позже."
            )
        return

    link = random.choice(available_links)
    texts = await text_repo.get_active_by_link_id(link.id)
    if not texts:
        await cb.message.answer(
            "У выбранной ссылки нет текстов отзывов. Попробуйте позже или сообщите админу."
        )
        return
    review_text = random.choice(texts)
    task = await task_repo.create(user_id=user_id, link_id=link.id, text_id=review_text.id)
    await state.set_state(UserFSM.waiting_screenshot)
    await state.update_data(task_id=task.id)

    platform_label = _platform_label(link.platform)
    text_for_user = (
        f"📌 Платформа: {platform_label}\n\n"
        f"🔗 Ссылка: {link.url}\n\n"
        f"📝 Текст отзыва:\n\n{review_text.text}"
    )
    await cb.message.answer(
        text_for_user,
        reply_markup=kb_sent_for_review(),
    )


@router.callback_query(F.data == CALLBACK_SENT)
async def sent_review(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    if not data.get("task_id"):
        await cb.message.answer("Задание не найдено. Нажмите «Взять задание» заново.")
        await state.clear()
        return
    await cb.message.edit_reply_markup(reply_markup=None)
    await state.set_state(UserFSM.waiting_screenshot)
    await cb.message.answer("Отправьте скриншот отзыва (одним фото).")


@router.message(UserFSM.waiting_screenshot, F.photo)
async def got_screenshot(message: Message, state: FSMContext, **data):
    file_id = message.photo[-1].file_id
    await state.update_data(screenshot_file_id=file_id)
    await state.set_state(UserFSM.waiting_payment_details)
    await message.answer(
        "Скриншот принят. Теперь отправьте реквизиты для выплаты: "
        "номер карты, ник в Яндекс/2ГИС, телефон — в одном сообщении."
    )


@router.message(UserFSM.waiting_screenshot)
async def wrong_screenshot(message: Message):
    await message.answer("Отправьте, пожалуйста, фото (скриншот).")


@router.message(UserFSM.waiting_payment_details, F.text)
async def got_payment_details(message: Message, state: FSMContext, **data):
    session = data["session"]
    state_data = await state.get_data()
    task_id = state_data.get("task_id")
    screenshot_file_id = state_data.get("screenshot_file_id")
    if not task_id or not screenshot_file_id:
        await message.answer("Ошибка. Начните заново: нажмите «Взять задание».")
        await state.clear()
        return
    task_repo = TaskRepository(session)
    user_repo = UserRepository(session)
    task = await task_repo.get_by_id(task_id)
    if not task or task.status != "pending":
        await message.answer("Задание уже обработано или не найдено.")
        await state.clear()
        return
    await task_repo.update_submission(task_id, screenshot_file_id, message.text)
    link_repo = LinkRepository(session)
    link = await link_repo.get_by_id(task.link_id)
    platform = link.platform if link else "?"
    await user_repo.update_last_review(message.from_user.id, platform)
    await state.clear()
    await message.answer(
        "✅ Ваш отзыв отправлен на проверку. После одобрения и выплаты вы получите уведомление."
    )
    # Уведомление админу отправим в main через bot — нужен bot instance. Передадим через ответ админам в admin handler при показе списка или через отдельный уведомитель.
    # Проще: в admin handler при открытии "Непроверенные" мы просто показываем список. Реальное уведомление админу можно слать из здесь, но нужен bot. Передадим bot в data через middleware или получим из event.bot.
    from aiogram import Bot
    bot = message.bot
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 Новый отзыв на проверку.\n"
                f"Задание #{task_id}, пользователь @{message.from_user.username or message.from_user.id}.",
            )
        except Exception:
            pass


@router.message(UserFSM.waiting_payment_details)
async def wrong_payment_details(message: Message):
    await message.answer("Отправьте реквизиты текстом.")


# Главное меню после обучения: кнопка "Взять задание"
@router.message(F.text == "Взять задание")
async def menu_take_task(message: Message, state: FSMContext, **data):
    session = data["session"]
    await state.clear()
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    if not user:
        await message.answer("Нажмите /start для начала.")
        return
    await message.answer("Нажмите кнопку ниже:", reply_markup=kb_take_task())


# Копировать текст — отправляем текст отдельным сообщением (в Telegram нельзя копировать из бота в буфер)
@router.callback_query(F.data == "copy_text")
async def copy_text(cb: CallbackQuery):
    await cb.answer("Текст уже в сообщении выше — выделите и скопируйте.")

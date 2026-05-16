# -*- coding: utf-8 -*-
"""Пользовательские хендлеры SeoJob / Отзовик."""
import re
from datetime import timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    ADMIN_IDS,
    MANAGER_IDS,
    SUPPORT_URL,
    WELCOME_BONUS_AMOUNT,
    welcome_bonus_start_datetime_utc,
)
from database import (
    AttemptRepository,
    BalanceRepository,
    ReferralRepository,
    SecondAccountReviewRepository,
    SettingsRepository,
    TaskItemRepository,
    UserRepository,
    WithdrawalRepository,
)
from keyboards.admin import moderation_kb, second_account_moderation_kb, withdraw_kb
from keyboards.user import (
    cabinet_back_kb,
    cabinet_reviews_nav_kb,
    continue_attempt_kb,
    cancel_attempt_kb,
    main_menu,
    operations_history_kb,
    platforms_kb,
    task_card_kb,
    task_venue_cities_kb,
    tasks_all_done_kb,
    welcome_start_kb,
)
from utils.telegram_safe import send_screenshot_or_document
from services.executor_repeat_reminder import schedule_executor_repeat_reminder
from services.geocoding import distance_km, geocode_city
from services.review_admin_instant import notify_admins_review_screenshot_received
from utils.fsm import UserFSM
from middlewares.rules import RULES_ACCEPT_CALLBACK_DATA

NEWS_CHANNEL_URL = "https://t.me/Jobinsidenews"
NEWS_PROMPT_TEXT = (
    "Чтобы всегда быть в курсе событий, цен и обновлений, подпишитесь на наш новостной канал.\n\n"
    "После подписки нажмите кнопку «✍️ Приступить к заданию»."
)

BLOCKED_TEXT = (
    "вы заблокированы по решению администрации, для разблокировки обратитесь к владельцу - @Exxzest"
)

# Не сохранять как город, если пользователь нажал кнопку меню вместо ввода города
MAIN_MENU_TEXTS = frozenset(
    {
        "✍️ Приступить к заданию",
        "💰 Личный кабинет / Баланс",
        "💸 Вывести средства",
        "👥 Реферальная программа",
        "🆘 Помощь",
    }
)

router = Router(name="user")

# Маркер в venue_pick_list: задания с пустым venue_city (старые карточки)
TASK_VENUE_EMPTY = "__TASK_VENUE_EMPTY__"

_REVIEW_HISTORY_PAGE_SIZE = 5
_REVIEW_HISTORY_MAX = 30
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    m = _URL_RE.search(text)
    if not m:
        return None
    return m.group(0).rstrip(").,]>\"'")


def _review_status_line(attempt) -> str:
    st = attempt.status or ""
    if st == "completed":
        return "✅ Отзыв принят"
    if st == "rejected":
        line = "❌ Отзыв отклонён"
        reason = (getattr(attempt, "reject_reason", None) or "").strip()
        if reason:
            line += f"\nПричина: {reason}"
        return line
    if st == "review_submitted":
        return "⏸ Отзыв на проверке"
    return f"Статус: {st}"


def _format_user_review_caption(attempt, task) -> str:
    platform = getattr(task, "platform", None) if task else None
    venue_city = getattr(task, "venue_city", None) if task else None
    sphere = getattr(task, "sphere", None) if task else None
    try:
        price = float(getattr(task, "price", 0) or 0) if task else 0.0
    except Exception:
        price = 0.0
    venue_url = _extract_first_url(getattr(task, "instruction_url", None) if task else None)
    submitted_line = "—"
    if getattr(attempt, "submitted_at", None):
        submitted_line = attempt.submitted_at.strftime("%d.%m.%Y %H:%M") + " UTC"
    lines = [
        _review_status_line(attempt),
        "",
        f"🧾 Заявка #{attempt.id}",
        f"Дата отправки скрина: {submitted_line}",
        f"Задание: {platform or '—'} | город орг.: {(venue_city or '—').strip() if venue_city else '—'}",
        f"Сфера: {sphere or '—'} | Вознаграждение: {price:.2f} руб.",
    ]
    if venue_url:
        lines.append(f"🔗 Ссылка: {venue_url}")
    if attempt.status == "completed" and getattr(attempt, "updated_at", None):
        lines.append(f"Дата решения: {attempt.updated_at.strftime('%d.%m.%Y %H:%M')} UTC")
    text = "\n".join(lines)
    if len(text) > 1000:
        text = text[:997] + "…"
    return text


def _rotate_tasks_round_robin(tasks_sorted: list, last_started_task_id: int | None) -> list:
    """Сдвигает порядок: после последнего взятого задания следующее становится первым в карусели."""
    if not tasks_sorted:
        return []
    n = len(tasks_sorted)
    if last_started_task_id is None:
        return list(tasks_sorted)
    ids = [t.id for t in tasks_sorted]
    if last_started_task_id not in ids:
        return list(tasks_sorted)
    idx = ids.index(last_started_task_id)
    return [tasks_sorted[(idx + 1 + k) % n] for k in range(n)]


def _task_card_venue_sphere(task) -> tuple[str, str]:
    """Город и сфера с карточки задания (заполняет админ/менеджер), не профиль исполнителя."""
    v = (getattr(task, "venue_city", None) or "").strip()
    s = (task.sphere or "").strip() if task else ""
    return (v if v else "—", s if s else "—")


def _gender_label(value: str) -> str:
    if value == "male":
        return "👨 Мужской"
    if value == "female":
        return "👩 Женский"
    return "👥 Без разницы"


def _msk_dt_str(dt) -> str:
    if not dt:
        return "—"
    try:
        msk = dt + timedelta(hours=3)
        return msk.strftime("%d.%m.%y %H:%M")
    except Exception:
        return "—"


def _task_matches_gender(task_gender: str | None, user_gender: str | None) -> bool:
    tg = (task_gender or "any").strip()
    ug = (user_gender or "any").strip()
    if tg == "any" or ug == "any":
        return True
    return tg == ug


def _platforms_kb_with_prices(rows: list[tuple[str, float]]) -> InlineKeyboardMarkup:
    btn_rows = []
    for platform, price in rows:
        btn_rows.append([InlineKeyboardButton(text=f"{platform} [{price:.0f} руб.]", callback_data=f"platform:{platform}")])
    btn_rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=btn_rows)


async def _grant_welcome_bonus_if_needed(session, user_id: int) -> bool:
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if not user:
        return False
    if getattr(user, "welcome_bonus_credited", False):
        return False
    if getattr(user, "registered_at", None) and user.registered_at < welcome_bonus_start_datetime_utc():
        return False
    await user_repo.add_balance(user_id, float(WELCOME_BONUS_AMOUNT))
    await bal_repo.add_operation(
        user_id,
        float(WELCOME_BONUS_AMOUNT),
        "welcome_bonus",
        f"Приветственный бонус {WELCOME_BONUS_AMOUNT} руб.",
    )
    await user_repo.mark_welcome_bonus_credited(user_id)
    return True


async def _get_nearest_tasks_for_platform(session, user, platform: str):
    task_repo = TaskItemRepository(session)
    all_tasks = await task_repo.get_active_for_platform(platform, user.city if user else None)
    if not all_tasks:
        return []
    user_point = await geocode_city(user.city or "")
    if not user_point:
        return all_tasks

    weighted = []
    for t in all_tasks:
        venue = (getattr(t, "venue_city", None) or "").strip()
        if not venue:
            weighted.append((999999.0, t.id, t))
            continue
        p = await geocode_city(venue)
        if not p:
            weighted.append((999999.0, t.id, t))
            continue
        weighted.append((distance_km(user_point, p), t.id, t))
    weighted.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in weighted]


async def _build_platform_rows_for_user(session, user, user_id: int) -> list[tuple[str, float]]:
    task_repo = TaskItemRepository(session)
    attempt_repo = AttemptRepository(session)
    user_repo = UserRepository(session)
    rows = await task_repo.get_platforms_with_min_price(user.city if user else None)
    completed_ids = await attempt_repo.completed_task_item_ids(user_id)
    unlock_map = await user_repo.get_repeat_unlock_map(user_id)
    out: list[tuple[str, float]] = []
    for platform, min_price in rows:
        tasks = await _get_nearest_tasks_for_platform(session, user, platform)
        tasks = [t for t in tasks if _task_matches_gender(getattr(t, "allowed_gender", "any"), user.account_gender)]
        if unlock_map.get(platform):
            available = tasks
        else:
            available = [t for t in tasks if t.id not in completed_ids]
        if available:
            out.append((platform, min_price))
    return out


def _instruction_login_block(task) -> str:
    return (
        "⚙⚙️ Ознакомься с инструкцией и приступай к работе 👇🏻\n\n"
        "📑 ОТКРЫТЬ ИНСТРУКЦИЮ\n"
        f"{task.instruction_url}\n"
        "‼️‼️‼️‼️‼️‼️‼️‼️‼️‼️\n"
        f"✍🏻 Напиши свой логин из профиля аккаунта на платформе {task.platform} и отправь боту"
    )


async def _open_venue_city_choice(message: Message, state: FSMContext, session, user) -> bool:
    """Показать инлайн-города с заданиями. False — нечего показать."""
    task_repo = TaskItemRepository(session)
    profile_city = user.city if user else None
    cities, has_empty = await task_repo.get_venue_city_pick_list(profile_city)
    pick_list = list(cities)
    if has_empty:
        pick_list.append(TASK_VENUE_EMPTY)
    if not pick_list:
        await message.answer("Сейчас нет активных заданий.")
        return False
    await state.set_state(UserFSM.choosing_venue_city)
    await state.update_data(venue_pick_list=pick_list, selected_venue_city=None)
    await message.answer(
        "Выберите город из предложенных — он должен быть максимально близким к вам.\n\n"
        "Так мы снижаем риск отклонения от алгоритмов Яндекса: если вы территориально, например, в Сибири, "
        "а оставляете отзыв на заведение в Краснодаре, отзыв может быть отклонён.",
        reply_markup=task_venue_cities_kb(pick_list, TASK_VENUE_EMPTY),
    )
    return True


async def submit_executor_review_photo(
    message: Message,
    state: FSMContext,
    session,
    attempt,
    file_id: str,
) -> bool:
    """
    Принять скрин опубликованного отзыва (статус попытки — approved).
    Реквизиты берутся из профиля пользователя.
    """
    user_repo = UserRepository(session)
    attempt_repo = AttemptRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    reqs = (user.payout_requisites or "").strip() if user else ""
    if len(reqs) < 4:
        await message.answer(
            "❗️ Укажите реквизиты для выплат: "
            "«💰 Личный кабинет / Баланс» → «✏️ Редактировать реквизиты», "
            "затем снова пришлите скриншот отзыва сюда."
        )
        return False
    updated = await attempt_repo.submit_review(attempt.id, file_id, reqs)
    if not updated:
        await message.answer(
            "Не удалось сохранить скрин. Убедитесь, что модератор уже одобрил ваш профиль по этому заданию."
        )
        return False

    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(updated.task_item_id)
    if task:
        await notify_admins_review_screenshot_received(
            message.bot,
            review_file_id=file_id,
            attempt_user_id=updated.user_id,
            executor_username=message.from_user.username,
            task_platform=task.platform,
            task_sphere=task.sphere,
            task_price=float(task.price),
            profile_login=(getattr(updated, "profile_login", None) or "").strip() or None,
        )
        anchor = getattr(updated, "submitted_at", None)
        if anchor:
            await schedule_executor_repeat_reminder(session, updated.user_id, task.platform, anchor=anchor)

    await state.clear()
    await message.answer("✅ Скриншот получен. Ожидайте проверки.", reply_markup=main_menu())
    return True


async def _show_task_card(
    message: Message,
    state: FSMContext,
    task_ids: list[int],
    index: int,
    session,
):
    task_repo = TaskItemRepository(session)
    task = await task_repo.get_by_id(task_ids[index])
    if not task:
        await message.answer("Задание не найдено.")
        return
    await state.update_data(task_ids=task_ids, task_index=index)
    city_org, sphere_org = _task_card_venue_sphere(task)
    text = (
        f"✍🏻 Вы выбрали задание {task.platform}\n\n"
        f"🏘 Город: {city_org}\n"
        f"♻️ Сфера: {sphere_org}\n"
        f"💰 Цена: {float(task.price):.2f} ₽\n"
        "⏰ Выполнение задания занимает около 5-10 минут!"
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

    got_bonus = await _grant_welcome_bonus_if_needed(session, message.from_user.id)
    await message.answer(settings.welcome_text, reply_markup=main_menu())
    if got_bonus:
        await message.answer(f"🎁 Приветственный бонус: +{WELCOME_BONUS_AMOUNT} руб. уже на вашем балансе.")
    await message.answer("Чтобы начать, нажмите кнопку ниже 👇", reply_markup=welcome_start_kb())

    active = await AttemptRepository(session).get_active_pipeline_attempt(message.from_user.id)
    if active and active.status in {"approved", "waiting_approval", "login_screenshot"}:
        task = await TaskItemRepository(session).get_by_id(active.task_item_id)
        if task:
            await state.set_state(UserFSM.waiting_profile_login)
            await state.update_data(attempt_id=active.id)
            await message.answer(
                "📝 У тебя есть незаконченное задание:\n\n"
                f"— Платформа: {task.platform}\n"
                f"— Время начала: {_msk_dt_str(active.created_at)} (МСК)\n"
                f"— 📖 ОТКРЫТЬ ИНСТРУКЦИЮ\n{task.instruction_url}\n\n"
                "Нажми кнопку «Продолжить выполнение»",
                reply_markup=continue_attempt_kb(),
            )


@router.callback_query(F.data == RULES_ACCEPT_CALLBACK_DATA)
async def accept_rules(cb: CallbackQuery, state: FSMContext, **data):
    """Accept rules and unlock the bot (equivalent to starting the bot)."""
    await cb.answer()
    session = data["session"]

    user_repo = UserRepository(session)
    settings_repo = SettingsRepository(session)
    user, _created = await user_repo.get_or_create(
        user_id=cb.from_user.id,
        username=cb.from_user.username,
        first_name=cb.from_user.first_name,
    )

    if user.is_blocked and cb.from_user.id not in ADMIN_IDS:
        await cb.message.answer(BLOCKED_TEXT)
        return

    user.rules_accepted = True
    user.rules_prompted = True
    await session.flush()

    await state.clear()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    settings = await settings_repo.get()
    got_bonus = await _grant_welcome_bonus_if_needed(session, cb.from_user.id)
    await cb.message.answer(settings.welcome_text, reply_markup=main_menu())
    if got_bonus:
        await cb.message.answer(f"🎁 Приветственный бонус: +{WELCOME_BONUS_AMOUNT} руб. уже на вашем балансе.")
    await cb.message.answer("Чтобы начать, нажмите кнопку ниже 👇", reply_markup=welcome_start_kb())


@router.message(Command("menu"))
async def menu_cmd(message: Message, state: FSMContext, **data):
    """Alias for /start (return to main menu)."""
    await state.clear()
    session = data["session"]
    user_repo = UserRepository(session)
    settings_repo = SettingsRepository(session)

    user, _created = await user_repo.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    settings = await settings_repo.get()

    if user.is_blocked:
        await message.answer(BLOCKED_TEXT, reply_markup=main_menu())
        return

    await message.answer(settings.welcome_text, reply_markup=main_menu())
    await message.answer("Чтобы начать, нажмите кнопку ниже 👇", reply_markup=welcome_start_kb())


def _gender_pick_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨 Мужской", callback_data="gender:set:male")],
            [InlineKeyboardButton(text="👩 Женский", callback_data="gender:set:female")],
        ]
    )


@router.callback_query(F.data == "welcome:start_work")
async def welcome_start_work(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    user = await UserRepository(session).get_by_user_id(cb.from_user.id)
    if not user:
        await cb.message.answer("Нажмите /start.")
        return
    if (getattr(user, "account_gender", "any") or "any") == "any":
        await cb.message.answer("🧑 Для работы выберите пол аккаунта на платформе:", reply_markup=_gender_pick_kb())
        return
    await state.set_state(UserFSM.choosing_city)
    await cb.message.answer("🗺 Напишите ваш город, чтобы подобрать ближайшие задания.")


@router.callback_query(F.data.startswith("gender:set:"))
async def gender_set(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    gender = cb.data.split(":")[-1]
    if gender not in {"male", "female"}:
        await cb.message.answer("Некорректный выбор пола.")
        return
    session = data["session"]
    await UserRepository(session).set_account_gender(cb.from_user.id, gender)
    await state.set_state(UserFSM.choosing_city)
    await cb.message.answer(
        f"✅ Пол аккаунта сохранён: {_gender_label(gender)}\n\n🗺 Теперь напишите ваш город, чтобы подобрать ближайшие задания."
    )


@router.callback_query(F.data == "attempt:continue")
async def attempt_continue(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    active = await attempt_repo.get_active_pipeline_attempt(cb.from_user.id)
    if not active:
        await cb.message.answer("Активного задания не найдено. Нажмите «✍️ Приступить к заданию».")
        return
    task = await task_repo.get_by_id(active.task_item_id)
    if not task:
        await cb.message.answer("Задание не найдено. Нажмите «✍️ Приступить к заданию».")
        return
    if active.status == "review_submitted":
        await cb.message.answer("По этому заданию отзыв уже отправлен на проверку. Ожидайте решения администратора.")
        return
    if (getattr(active, "profile_login", None) or "").strip():
        await state.set_state(UserFSM.waiting_review_screenshot)
        await state.update_data(attempt_id=active.id)
        await cb.message.answer("🔜 Следующий этап - НАПИСАНИЕ ОТЗЫВА\n✍🏻 Напиши отзыв и отправь скриншот отзыва боту")
        return
    await state.set_state(UserFSM.waiting_profile_login)
    await state.update_data(attempt_id=active.id)
    await cb.message.answer(_instruction_login_block(task))


@router.message(F.text == "✍️ Приступить к заданию")
async def begin_tasks(message: Message, state: FSMContext, **data):
    session = data["session"]
    user_repo = UserRepository(session)
    user = await user_repo.get_by_user_id(message.from_user.id)
    if not user:
        await message.answer("Нажмите /start.")
        return

    if (getattr(user, "account_gender", "any") or "any") == "any":
        await message.answer("🧑 Для работы выберите пол аккаунта на платформе:", reply_markup=_gender_pick_kb())
        return
    await state.set_state(UserFSM.choosing_city)
    await message.answer("🗺 Напишите ваш город, чтобы подобрать ближайшие задания.")


@router.message(UserFSM.choosing_city, F.text)
async def choose_city(message: Message, state: FSMContext, **data):
    raw = message.text.strip()
    if raw in MAIN_MENU_TEXTS:
        await message.answer("Сначала напишите название вашего города текстом (не кнопку меню).")
        return
    session = data["session"]
    user_repo = UserRepository(session)
    await user_repo.set_city(message.from_user.id, raw)
    user = await user_repo.get_by_user_id(message.from_user.id)
    if not user:
        await state.clear()
        return
    rows = await _build_platform_rows_for_user(session, user, message.from_user.id)
    if not rows:
        await message.answer(
            "Сейчас нет доступных заданий для выбранного города и вашего профиля.\n"
            "Попробуйте другой город чуть крупнее или зайдите позже.",
            reply_markup=main_menu(),
        )
        await state.clear()
        return
    await state.set_state(UserFSM.choosing_platform)
    await message.answer(
        "↓ Доступные платформы для заданий\n❗ Недоступно = нет заданий или недавно выполняли\n♻️ Выберите платформу для работы",
        reply_markup=_platforms_kb_with_prices(rows),
    )


@router.callback_query(F.data.startswith("taskvenue:"))
async def pick_task_venue(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    user_repo = UserRepository(session)
    task_repo = TaskItemRepository(session)
    try:
        idx = int(cb.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await cb.message.answer("Некорректный выбор. Нажмите «Приступить к заданию» снова.")
        return
    d = await state.get_data()
    pick_list = d.get("venue_pick_list") or []
    if idx < 0 or idx >= len(pick_list):
        await cb.message.answer("Список городов устарел. Нажмите «Приступить к заданию» снова.")
        return
    raw_label = pick_list[idx]
    await state.update_data(selected_venue_city=raw_label)
    user = await user_repo.get_by_user_id(cb.from_user.id)
    venue_for_query = None if raw_label == TASK_VENUE_EMPTY else raw_label
    platforms = await task_repo.get_platforms_for_venue(venue_for_query, user.city if user else None)
    if not platforms:
        await state.update_data(selected_venue_city=None)
        await cb.message.answer("Для этого города нет заданий ни на одной платформе. Выберите другой город.")
        return
    await state.set_state(UserFSM.choosing_platform)
    await cb.message.answer("Выберите платформу:", reply_markup=platforms_kb(platforms, show_back_venue=True))


@router.callback_query(F.data.in_(["back_task_venue", "secacc:back_platforms"]))
async def back_task_venue(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.update_data(secacc_offer_platform=None, secacc_platform=None, selected_venue_city=None)
    await state.set_state(UserFSM.choosing_city)
    await cb.message.answer("🗺 Напишите ваш город, чтобы подобрать ближайшие задания.")


@router.message(UserFSM.choosing_venue_city, F.text)
async def remind_pick_venue_by_button(message: Message, **data):
    if (message.text or "").strip() in MAIN_MENU_TEXTS:
        return
    await message.answer("Выберите город кнопками в предыдущем сообщении или «🔙 В главное меню».")


@router.message(UserFSM.choosing_platform, F.text)
async def remind_pick_platform_by_button(message: Message, **data):
    if (message.text or "").strip() in MAIN_MENU_TEXTS:
        return
    await message.answer("Выберите платформу кнопкой ниже.")


@router.callback_query(F.data.startswith("platform:"))
async def choose_platform(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    user_repo = UserRepository(session)
    task_repo = TaskItemRepository(session)
    attempt_repo = AttemptRepository(session)
    user = await user_repo.get_by_user_id(cb.from_user.id)
    platform = cb.data.split(":", 1)[1]
    if not user or not (user.city or "").strip():
        await cb.message.answer("Сначала укажите город. Нажмите «✍️ Приступить к заданию».")
        return
    all_tasks = await _get_nearest_tasks_for_platform(session, user, platform)
    all_tasks = [t for t in all_tasks if _task_matches_gender(getattr(t, "allowed_gender", "any"), user.account_gender)]
    if not all_tasks:
        await cb.message.answer("По этой платформе нет активных заданий.")
        return

    completed_ids = await attempt_repo.completed_task_item_ids(cb.from_user.id)
    unlock_map = await user_repo.get_repeat_unlock_map(cb.from_user.id)
    has_unlock = bool(unlock_map.get(platform))

    if has_unlock:
        available = list(all_tasks)
    else:
        available = [t for t in all_tasks if t.id not in completed_ids]

    if not available:
        await state.update_data(secacc_offer_platform=platform)
        await cb.message.answer(
            "По этой платформе вы уже выполнили все доступные задания в выбранном городе.\n\n"
            "Если у вас есть второй аккаунт на этой площадке — пройдите короткую проверку. "
            "Или выберите другую платформу / другой город.",
            reply_markup=tasks_all_done_kb(),
        )
        return

    rot = await user_repo.get_task_rotation_map(cb.from_user.id)
    last_id = rot.get(platform)
    ordered = _rotate_tasks_round_robin(available, last_id)
    task_ids = [t.id for t in ordered]
    await _show_task_card(cb.message, state, task_ids, 0, session)


@router.callback_query(F.data == "secacc:want")
async def secacc_want_second_account(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    d = await state.get_data()
    platform = d.get("secacc_offer_platform")
    if not platform:
        await cb.message.answer("Сначала откройте платформу из списка заданий (где больше нет доступных карточек).")
        return
    sar = SecondAccountReviewRepository(session)
    if await sar.get_pending_for_user(cb.from_user.id):
        await cb.message.answer("Заявка на проверку второго аккаунта уже отправлена. Ожидайте решения.")
        return
    await state.set_state(UserFSM.waiting_second_account_screenshot)
    await state.update_data(secacc_platform=platform)
    await cb.message.answer(
        "Пришлите <b>скриншот профиля второго аккаунта</b> на этой площадке, "
        "где видно никнейм и что это отдельный аккаунт.",
        parse_mode="HTML",
    )


@router.message(UserFSM.waiting_second_account_screenshot, F.photo)
async def second_account_screenshot(message: Message, state: FSMContext, **data):
    session = data["session"]
    d = await state.get_data()
    platform = d.get("secacc_platform")
    if not platform:
        await state.clear()
        return
    sar = SecondAccountReviewRepository(session)
    if await sar.get_pending_for_user(message.from_user.id):
        await message.answer("Заявка уже на проверке. Ожидайте.")
        return
    fid = message.photo[-1].file_id
    rev = await sar.create(message.from_user.id, platform, fid)
    cap = (
        "🧾 <b>Проверка второго аккаунта</b>\n"
        f"Исполнитель: @{message.from_user.username or message.from_user.id}\n"
        f"ID: <code>{message.from_user.id}</code>\n"
        f"Платформа: {platform}"
    )
    for aid in ADMIN_IDS:
        try:
            await message.bot.send_photo(
                aid,
                fid,
                caption=cap,
                parse_mode="HTML",
                reply_markup=second_account_moderation_kb(rev.id),
            )
        except Exception:
            pass
    await state.clear()
    await message.answer(
        "✅ Скриншот получен. Ваш аккаунт на проверке у модератора. Ожидайте решения.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data.startswith("next_task:"))
async def next_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    state_data = await state.get_data()
    task_ids = state_data.get("task_ids", [])
    if not task_ids:
        return
    new_index = (state_data.get("task_index", 0) + 1) % len(task_ids)
    await _show_task_card(cb.message, state, task_ids, new_index, session)


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
    await _show_task_card(cb.message, state, filtered, 0, session)


@router.callback_query(F.data.startswith("start_task:"))
async def start_task(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    user_repo = UserRepository(session)
    task_id = int(cb.data.split(":")[1])
    task = await task_repo.get_by_id(task_id)
    if not task or not task.is_active:
        await cb.message.answer("Задание недоступно.")
        return

    user = await user_repo.get_by_user_id(cb.from_user.id)
    if user and not _task_matches_gender(getattr(task, "allowed_gender", "any"), getattr(user, "account_gender", "any")):
        await cb.message.answer("Это задание недоступно для выбранного пола аккаунта. Выберите другое.")
        return

    completed_ids = await attempt_repo.completed_task_item_ids(cb.from_user.id)
    unlock_map = await user_repo.get_repeat_unlock_map(cb.from_user.id)
    if task_id in completed_ids and not unlock_map.get(task.platform):
        await cb.message.answer("Это задание вы уже успешно выполнили. Выберите другое или другую платформу.")
        return

    active = await attempt_repo.get_active_pipeline_attempt(cb.from_user.id)
    if active:
        if active.task_item_id != task_id:
            await cb.message.answer(
                "У вас уже есть незавершённое задание (модерация профиля или отзыва).\n"
                "Дождитесь решения или нажмите «Отменить» под сообщением бота, затем начните новое."
            )
            return
        if active.status == "review_submitted":
            await cb.message.answer("По этому заданию отзыв уже отправлен на проверку. Ожидайте решения администратора.")
            return
        if active.status == "approved":
            if (getattr(active, "profile_login", None) or "").strip():
                await state.set_state(UserFSM.waiting_review_screenshot)
                await state.update_data(attempt_id=active.id)
                await cb.message.answer(
                    "🔜 Следующий этап - НАПИСАНИЕ ОТЗЫВА\n"
                    "✍🏻 Напиши отзыв и отправь скриншот отзыва боту"
                )
            else:
                await state.set_state(UserFSM.waiting_profile_login)
                await state.update_data(attempt_id=active.id)
                await cb.message.answer(_instruction_login_block(task))
            return
        if active.status in ("login_screenshot", "waiting_approval"):
            await state.set_state(UserFSM.waiting_profile_login)
            await state.update_data(attempt_id=active.id)
            await cb.message.answer(_instruction_login_block(task))
            return

    attempt = await attempt_repo.create(cb.from_user.id, task_id)
    await attempt_repo.approve(attempt.id)
    await user_repo.set_last_started_task_for_platform(cb.from_user.id, task.platform, task_id)
    await state.set_state(UserFSM.waiting_profile_login)
    await state.update_data(attempt_id=attempt.id)
    await cb.message.answer(_instruction_login_block(task))


@router.message(UserFSM.waiting_profile_login, F.text)
async def got_profile_login(message: Message, state: FSMContext, **data):
    login = (message.text or "").strip()
    if len(login) < 2:
        await message.answer("Логин слишком короткий. Отправьте логин из профиля (минимум 2 символа).")
        return
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("attempt_id")
    attempt = await attempt_repo.get_by_id(attempt_id)
    if not attempt or attempt.user_id != message.from_user.id:
        await state.clear()
        return
    await attempt_repo.set_profile_login(attempt.id, login)
    await state.set_state(UserFSM.waiting_review_screenshot)
    await state.update_data(attempt_id=attempt.id)
    await message.answer(
        "🔜 Следующий этап - НАПИСАНИЕ ОТЗЫВА\n"
        "✍🏻 Напиши отзыв и отправь скриншот отзыва боту"
    )


def _is_image_document(doc: Document | None) -> bool:
    if not doc:
        return False
    mt = (doc.mime_type or "").lower()
    if mt.startswith("image/"):
        return True
    name = (doc.file_name or "").lower()
    return any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"))


async def _process_account_screenshot_file(
    message: Message, state: FSMContext, session, file_id: str, photo_for_review_fallback: str | None
) -> None:
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    state_data = await state.get_data()
    aid = state_data.get("attempt_id")
    if aid is None:
        await state.clear()
        return
    attempt = await attempt_repo.get_by_id(aid)
    if not attempt:
        await state.clear()
        return
    if attempt.user_id != message.from_user.id:
        await state.clear()
        return

    if attempt.status == "review_submitted":
        await message.answer("Скрин отзыва уже принят. Ожидайте решения администратора.")
        return

    # Профиль уже одобрен, но FSM остался на этапе 1 — принимаем скрин как отзыв
    if attempt.status == "approved":
        fid = photo_for_review_fallback or file_id
        await state.set_state(UserFSM.waiting_review_screenshot)
        await state.update_data(attempt_id=attempt.id)
        await submit_executor_review_photo(message, state, session, attempt, fid)
        return

    if attempt.account_screenshot_file_id is not None:
        await message.answer(
            "Скрин профиля уже отправлен. Дождитесь решения модератора.\n"
            "После одобрения пришлите сюда скриншот готового отзыва."
        )
        return

    await attempt_repo.set_account_screenshot(attempt.id, file_id)
    task = await task_repo.get_by_id(attempt.task_item_id)
    city_org, sphere_org = _task_card_venue_sphere(task)
    admin_text = (
        "🆕 <b>Новая заявка на допуск</b>\n"
        f"Заявка (attempt) #{attempt.id}\n"
        f"Исполнитель ID: <code>{attempt.user_id}</code>\n"
        f"Задание: {task.platform} | город орг.: {city_org} | сфера: {sphere_org} | {float(task.price):.2f} руб.\n\n"
        "Откройте: /admin → «✅ Допуск к заданиям» (там будет скрин и кнопки)."
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_text, parse_mode="HTML")
        except Exception:
            pass
    await message.answer("Скриншот отправлен на модерацию. Ожидайте решение.")


@router.message(UserFSM.waiting_account_screenshot, F.photo)
async def got_account_screenshot(message: Message, state: FSMContext, **data):
    session = data["session"]
    file_id = message.photo[-1].file_id
    await _process_account_screenshot_file(message, state, session, file_id, photo_for_review_fallback=file_id)


@router.message(UserFSM.waiting_review_screenshot, F.photo)
async def got_review_screenshot(message: Message, state: FSMContext, **data):
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt_id = (await state.get_data()).get("attempt_id")
    attempt = await attempt_repo.get_by_id(attempt_id)
    if not attempt or attempt.user_id != message.from_user.id:
        await state.clear()
        return
    await submit_executor_review_photo(message, state, session, attempt, message.photo[-1].file_id)


@router.message(UserFSM.waiting_profile_requisites, F.photo)
async def profile_requisites_no_photo(message: Message):
    await message.answer("Пришлите реквизиты одним текстовым сообщением, без фото.")


def _allow_executor_fallback_media(message: Message) -> bool:
    """Не перехватывать фото/файлы админов и менеджеров — их обрабатывают другие роутеры."""
    uid = message.from_user.id
    return uid not in ADMIN_IDS and uid not in MANAGER_IDS


@router.message(F.photo, _allow_executor_fallback_media)
async def got_review_screenshot_without_state(message: Message, state: FSMContext, **data):
    """Если FSM сбросился, но есть одобренная попытка — принимаем скрин отзыва."""
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    attempt = await attempt_repo.get_last_by_user_status(message.from_user.id, "approved")
    if not attempt or attempt.user_id != message.from_user.id:
        return
    await state.set_state(UserFSM.waiting_review_screenshot)
    await state.update_data(attempt_id=attempt.id)
    await submit_executor_review_photo(message, state, session, attempt, message.photo[-1].file_id)


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


async def _cabinet_summary_text(session, user_id: int) -> str:
    user_repo = UserRepository(session)
    attempt_repo = AttemptRepository(session)
    user = await user_repo.get_by_user_id(user_id)
    if not user:
        return "Профиль не найден."
    completed = await attempt_repo.completed_count_by_user(user_id)
    pr = (user.payout_requisites or "").strip()
    pr_line = pr if pr else "не указаны (нужны для выплат за задания)"
    return (
        f"Ваш ID: {user.user_id}\n"
        f"Username: @{user.username or '-'}\n"
        f"Пол аккаунта: {_gender_label(getattr(user, 'account_gender', 'any'))}\n"
        f"Баланс: {float(user.balance):.2f} руб.\n"
        f"Выполнено заданий: {completed}\n\n"
        f"Реквизиты для выплат по заданиям:\n{pr_line}"
    )


@router.message(F.text == "💰 Личный кабинет / Баланс")
async def cabinet(message: Message, **data):
    session = data["session"]
    text = await _cabinet_summary_text(session, message.from_user.id)
    await message.answer(text, reply_markup=operations_history_kb())


@router.callback_query(F.data == "cabinet_back")
async def cabinet_back(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    text = await _cabinet_summary_text(session, cb.from_user.id)
    await cb.message.answer(text, reply_markup=operations_history_kb())


@router.callback_query(F.data == "cabinet_reviews")
async def cabinet_reviews(cb: CallbackQuery, **data):
    await cb.answer()
    await _show_cabinet_review_history(cb, page=0, **data)


@router.callback_query(F.data.regexp(r"^cabinet_reviews:\d+$"))
async def cabinet_reviews_page(cb: CallbackQuery, **data):
    await cb.answer()
    page = int(cb.data.split(":")[-1])
    await _show_cabinet_review_history(cb, page=page, **data)


async def _show_cabinet_review_history(cb: CallbackQuery, page: int, **data) -> None:
    session = data["session"]
    attempt_repo = AttemptRepository(session)
    task_repo = TaskItemRepository(session)
    attempts = await attempt_repo.list_user_review_history(cb.from_user.id, limit=_REVIEW_HISTORY_MAX)
    if not attempts:
        await cb.message.answer(
            "Вы ещё не отправляли скриншоты отзывов на проверку.",
            reply_markup=cabinet_back_kb(),
        )
        return

    total_pages = max(1, (len(attempts) + _REVIEW_HISTORY_PAGE_SIZE - 1) // _REVIEW_HISTORY_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = attempts[page * _REVIEW_HISTORY_PAGE_SIZE : (page + 1) * _REVIEW_HISTORY_PAGE_SIZE]

    header = (
        f"📝 <b>История ваших отзывов</b>\n"
        f"Показано {len(chunk)} из {len(attempts)} (стр. {page + 1}/{total_pages})\n\n"
        "✅ — принят · ❌ — отклонён · ⏸ — на проверке"
    )
    await cb.message.answer(header, parse_mode="HTML", reply_markup=cabinet_reviews_nav_kb(page, total_pages))

    for at in chunk:
        task = await task_repo.get_by_id(at.task_item_id)
        caption = _format_user_review_caption(at, task)
        file_id = (getattr(at, "review_screenshot_file_id", None) or "").strip()
        if file_id:
            await send_screenshot_or_document(
                cb.bot,
                cb.message.chat.id,
                file_id,
                caption=caption,
            )
        else:
            await cb.message.answer(caption)

    await cb.message.answer("◀ Вернуться в личный кабинет:", reply_markup=cabinet_back_kb())


@router.callback_query(F.data == "cabinet_edit_requisites")
async def cabinet_edit_requisites_start(cb: CallbackQuery, state: FSMContext, **data):
    await cb.answer()
    await state.set_state(UserFSM.waiting_profile_requisites)
    await cb.message.answer(
        "Напишите свои реквизиты в свободной форме одним сообщением "
        "(номер телефона и банк / номер карты / СБП и т.д.). "
        "Они будут переданы заказчику после того, как администратор примет ваш отзыв."
    )


@router.message(UserFSM.waiting_profile_requisites, F.text)
async def cabinet_edit_requisites_save(message: Message, state: FSMContext, **data):
    text = (message.text or "").strip()
    if len(text) < 4:
        await message.answer("Слишком коротко. Напишите реквизиты подробнее одним сообщением.")
        return
    session = data["session"]
    user_repo = UserRepository(session)
    await user_repo.set_profile_payout_requisites(message.from_user.id, text)
    await state.clear()
    await message.answer("✅ Реквизиты сохранены. Теперь можно отправлять скриншот отзыва по заданию.", reply_markup=main_menu())


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


# Cancel withdraw flow when user picks another main-menu item.
# This prevents parsing "menu text" as a withdrawal amount.
@router.message(UserFSM.waiting_withdraw_amount, F.text == "💰 Личный кабинет / Баланс")
async def withdraw_cancel_to_cabinet_from_amount(message: Message, state: FSMContext, **data):
    await state.clear()
    await cabinet(message, **data)


@router.message(UserFSM.waiting_withdraw_amount, F.text == "🆘 Помощь")
async def withdraw_cancel_to_help_from_amount(message: Message, state: FSMContext, **data):
    await state.clear()
    await help_menu(message, **data)


@router.message(UserFSM.waiting_withdraw_amount, F.text == "👥 Реферальная программа")
async def withdraw_cancel_to_ref_from_amount(message: Message, state: FSMContext, **data):
    await state.clear()
    await referral_program(message, **data)


@router.message(UserFSM.waiting_withdraw_amount, F.text == "✍️ Приступить к заданию")
async def withdraw_cancel_to_tasks_from_amount(message: Message, state: FSMContext, **data):
    await state.clear()
    await begin_tasks(message, state, **data)


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


@router.message(UserFSM.waiting_withdraw_requisites, F.text == "💰 Личный кабинет / Баланс")
async def withdraw_cancel_to_cabinet_from_requisites(message: Message, state: FSMContext, **data):
    await state.clear()
    await cabinet(message, **data)


@router.message(UserFSM.waiting_withdraw_requisites, F.text == "🆘 Помощь")
async def withdraw_cancel_to_help_from_requisites(message: Message, state: FSMContext, **data):
    await state.clear()
    await help_menu(message, **data)


@router.message(UserFSM.waiting_withdraw_requisites, F.text == "👥 Реферальная программа")
async def withdraw_cancel_to_ref_from_requisites(message: Message, state: FSMContext, **data):
    await state.clear()
    await referral_program(message, **data)


@router.message(UserFSM.waiting_withdraw_requisites, F.text == "✍️ Приступить к заданию")
async def withdraw_cancel_to_tasks_from_requisites(message: Message, state: FSMContext, **data):
    await state.clear()
    await begin_tasks(message, state, **data)


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
    # Не показываем "дефолтную" незавершенную ссылку.
    support_url = (SUPPORT_URL or "").strip()
    if support_url and support_url != "https://t.me/":
        await message.answer(f"{settings.help_text}\n{support_url}")
    else:
        await message.answer(settings.help_text)


@router.message(Command("help"))
async def help_cmd(message: Message, **data):
    """Alias for the '🆘 Помощь' button in the main menu."""
    await help_menu(message, **data)


@router.callback_query(F.data == "to_menu")
async def to_menu(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.clear()
    await cb.message.answer("Главное меню:", reply_markup=main_menu())


@router.message(UserFSM.waiting_account_screenshot)
@router.message(UserFSM.waiting_review_screenshot)
@router.message(UserFSM.waiting_profile_login)
@router.message(UserFSM.waiting_second_account_screenshot)
@router.message(UserFSM.waiting_profile_requisites)
async def wrong_input_task_flow(message: Message, state: FSMContext):
    st = await state.get_state()
    if st == UserFSM.waiting_profile_requisites.state:
        await message.answer("Пришлите реквизиты текстом одним сообщением.")
        return
    if st == UserFSM.waiting_profile_login.state:
        await message.answer("Пришлите логин профиля текстом (без фото).")
        return
    if st == UserFSM.waiting_second_account_screenshot.state:
        await message.answer("Пришлите скриншот профиля второго аккаунта одним фото.")
        return
    if st == UserFSM.waiting_account_screenshot.state:
        await message.answer("Пришлите скрин профиля фото или файлом изображения (PNG, JPG и т.д.).")
        return
    await message.answer("Пожалуйста, отправьте скриншот изображением.")

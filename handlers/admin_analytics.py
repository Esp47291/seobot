# -*- coding: utf-8 -*-
"""Аналитика, экспорт CSV, центр модерации, действия по менеджерам — только админы."""
import csv
import io
import os
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import APP_VERSION, DATABASE_URL, sqlite_db_file_path_from_url
from database import SecondAccountReviewRepository, StatsRepository, TaskItemRepository, UserRepository
from keyboards.admin import (
    admin_analytics_hub_kb,
    admin_export_menu_kb,
    admin_moderation_hub_kb,
    admin_tasks_analytics_root_kb,
    second_account_moderation_kb,
)
from services.bot_runtime import uptime_seconds
from utils.fsm import AdminFSM

router = Router(name="admin_analytics")


def _text_chunks(text: str, max_len: int = 3800) -> list[str]:
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


def _moderation_hub_html(counts: dict[str, int]) -> str:
    return (
        "📌 <b>Центр модерации</b>\n\n"
        f"• Заявки на допуск: <b>{counts['admission']}</b>\n"
        f"• Отзывы на проверке: <b>{counts['reviews']}</b>\n"
        f"• Второй аккаунт (ожидают): <b>{counts['second_account']}</b>\n"
        f"• Заявки на вывод (ожидают): <b>{counts['withdrawals']}</b>\n"
    )


def _parse_date_only(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return datetime(d.year, d.month, d.day)
        except ValueError:
            continue
    return None


def _end_of_utc_day(d: datetime) -> datetime:
    return d.replace(hour=23, minute=59, second=59, microsecond=999999)


def _export_attempts_csv_bytes(rows: list[dict]) -> bytes:
    headers = [
        "attempt_id",
        "task_id",
        "instruction_url",
        "owner_type",
        "owner_telegram_id",
        "owner_username",
        "platform",
        "venue_city",
        "executor_telegram_id",
        "executor_username",
        "task_price_rub",
        "balance_credited",
        "payout_requisites",
        "completed_at_utc",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(h, "") for h in headers])
    return buf.getvalue().encode("utf-8-sig")


def _export_wd_csv_bytes(rows: list[dict]) -> bytes:
    headers = [
        "withdrawal_id",
        "user_telegram_id",
        "username",
        "amount_rub",
        "status",
        "requisites",
        "created_at_utc",
        "processed_at_utc",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r.get(h, "") for h in headers])
    return buf.getvalue().encode("utf-8-sig")


def _tasks_analytics_message(rows: list[dict], title: str) -> str:
    lines = [title, ""]
    if not rows:
        lines.append("Нет заданий по выбранному фильтру.")
        return "\n".join(lines)
    for item in rows:
        t = item["task"]
        lines.append(
            f"#{t.id} {t.platform} | {item['venue_city_short']} | {item['sphere_short']}\n"
            f"   владелец: {item['owner_label']} | активно: {'да' if t.is_active else 'нет'}\n"
            f"   попыток всего: {item['attempts_total']} | completed: {item['completed_n']} | "
            f"ждут оплаты менедж.: {item['awaiting_manager_pay']} | оплачено менедж.: {item['paid_by_manager']}\n"
        )
    return "\n".join(lines)


@router.message(Command("status"))
async def cmd_status(message: Message):
    up = uptime_seconds()
    up_txt = f"{int(up)} с (~{int(up // 3600)} ч.)" if up is not None else "неизвестно (ещё не отмечен старт)"
    path = sqlite_db_file_path_from_url(DATABASE_URL)
    if path:
        db_note = "SQLite (файл)"
    elif ":memory:" in (DATABASE_URL or ""):
        db_note = "SQLite :memory:"
    else:
        db_note = "не файловая SQLite (или другой DSN)"
    await message.answer(
        f"🤖 <b>Статус</b>\n\n"
        f"Версия: <code>{APP_VERSION}</code>\n"
        f"Uptime: {up_txt}\n"
        f"БД: {db_note}\n",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:analytics_hub")
async def analytics_hub(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("📊 Аналитика и инструменты:", reply_markup=admin_analytics_hub_kb())


@router.callback_query(F.data == "admin:moderation_hub")
async def moderation_hub_open(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    counts = await StatsRepository(session).moderation_hub_counts()
    await cb.message.answer(
        _moderation_hub_html(counts),
        parse_mode="HTML",
        reply_markup=admin_moderation_hub_kb(),
    )


@router.callback_query(F.data == "admin:moderation_hub_refresh")
async def moderation_hub_refresh(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    counts = await StatsRepository(session).moderation_hub_counts()
    text = _moderation_hub_html(counts)
    try:
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=admin_moderation_hub_kb())
    except Exception:
        await cb.message.answer(text, parse_mode="HTML", reply_markup=admin_moderation_hub_kb())


@router.callback_query(F.data == "admin:secacc_queue")
async def secacc_queue(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    sar = SecondAccountReviewRepository(session)
    user_repo = UserRepository(session)
    pending = await sar.list_pending(40)
    if not pending:
        await cb.message.answer("Нет заявок на проверку второго аккаунта.")
        return
    await cb.message.answer(f"👤 Очередь «второй аккаунт»: {len(pending)}")
    for rev in pending:
        u = await user_repo.get_by_user_id(rev.user_id)
        un = f"@{u.username}" if u and u.username else "—"
        cap = f"Заявка #{rev.id}\nПользователь: {rev.user_id} {un}\nПлатформа: {rev.platform}"
        kb = second_account_moderation_kb(rev.id)
        if rev.screenshot_file_id:
            await cb.message.answer_photo(rev.screenshot_file_id, caption=cap, reply_markup=kb)
        else:
            await cb.message.answer(cap, reply_markup=kb)


@router.callback_query(F.data == "admin:export_menu")
async def export_menu(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("Выберите период и тип выгрузки:", reply_markup=admin_export_menu_kb())


def _rolling_window(days: int) -> tuple[datetime, datetime]:
    now = datetime.utcnow()
    return now - timedelta(days=days), now


@router.callback_query(F.data == "admin:export:attempts:custom")
async def export_attempts_custom_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_export_date_from)
    await state.update_data(export_target="attempts")
    await cb.message.answer(
        "Экспорт завершённых попыток.\nДата <b>начала</b> (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД).\nОтмена: /cancel",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:export:wd:custom")
async def export_wd_custom_start(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(AdminFSM.waiting_export_date_from)
    await state.update_data(export_target="withdrawals")
    await cb.message.answer(
        "Экспорт заявок на вывод.\nДата <b>начала</b> (ДД.ММ.ГГГГ или ГГГГ-ММ-ДД).\nОтмена: /cancel",
        parse_mode="HTML",
    )


@router.callback_query(F.data.regexp(r"^admin:export:attempts:(7|30|90)$"))
async def export_attempts_preset(cb: CallbackQuery, **data):
    await cb.answer()
    days = int(cb.data.split(":")[-1])
    session = data["session"]
    dt_from, dt_to = _rolling_window(days)
    rows = await StatsRepository(session).export_completed_attempts_rows(dt_from, dt_to)
    raw = _export_attempts_csv_bytes(rows)
    if len(rows) == 0:
        await cb.message.answer("Нет строк за выбранный период.")
        return
    fn = f"attempts_completed_{days}d_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    await cb.message.answer_document(
        BufferedInputFile(raw, filename=fn),
        caption=f"Завершённые попытки за {days} дн., строк: {len(rows)}",
    )


@router.callback_query(F.data.regexp(r"^admin:export:wd:(7|30|90)$"))
async def export_wd_preset(cb: CallbackQuery, **data):
    await cb.answer()
    days = int(cb.data.split(":")[-1])
    session = data["session"]
    dt_from, dt_to = _rolling_window(days)
    rows = await StatsRepository(session).export_withdrawal_rows(dt_from, dt_to)
    if len(rows) == 0:
        await cb.message.answer("Нет заявок на вывод за выбранный период.")
        return
    raw = _export_wd_csv_bytes(rows)
    fn = f"withdrawals_{days}d_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    await cb.message.answer_document(
        BufferedInputFile(raw, filename=fn),
        caption=f"Заявки на вывод (по дате создания) за {days} дн., строк: {len(rows)}",
    )


@router.message(AdminFSM.waiting_export_date_from, F.text)
async def export_date_from(message: Message, state: FSMContext, **data):
    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    d = _parse_date_only(raw)
    if not d:
        await message.answer("Не разобрал дату. Пример: 01.03.2026")
        return
    await state.update_data(export_date_from=d.isoformat())
    await state.set_state(AdminFSM.waiting_export_date_to)
    await message.answer("Дата <b>конца</b> периода (включительно):", parse_mode="HTML")


@router.message(AdminFSM.waiting_export_date_to, F.text)
async def export_date_to(message: Message, state: FSMContext, **data):
    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    d_to = _parse_date_only(raw)
    if not d_to:
        await message.answer("Не разобрал дату. Пример: 31.03.2026")
        return
    data_sd = await state.get_data()
    d_from_s = data_sd.get("export_date_from")
    target = data_sd.get("export_target") or "attempts"
    if not d_from_s:
        await state.clear()
        await message.answer("Сессия сбита. Откройте экспорт снова.")
        return
    d_from = datetime.fromisoformat(d_from_s)
    if d_to < d_from:
        await message.answer("Конец раньше начала. Введите дату конца ещё раз.")
        return
    dt_from = d_from
    dt_to = _end_of_utc_day(d_to)
    session = data["session"]
    stats = StatsRepository(session)
    await state.clear()
    if target == "withdrawals":
        rows = await stats.export_withdrawal_rows(dt_from, dt_to)
        raw = _export_wd_csv_bytes(rows)
        fn = f"withdrawals_custom_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        cap = f"Выводы с {d_from.date()} по {d_to.date()}, строк: {len(rows)}"
    else:
        rows = await stats.export_completed_attempts_rows(dt_from, dt_to)
        raw = _export_attempts_csv_bytes(rows)
        fn = f"attempts_completed_custom_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        cap = f"Completed попытки с {d_from.date()} по {d_to.date()}, строк: {len(rows)}"
    await message.answer_document(BufferedInputFile(raw, filename=fn), caption=cap)


@router.callback_query(F.data == "admin:tasks_analytics_menu")
async def tasks_analytics_menu(cb: CallbackQuery):
    await cb.answer()
    await cb.message.answer("Фильтр списка заданий:", reply_markup=admin_tasks_analytics_root_kb())


@router.callback_query(F.data == "admin:tan:all")
async def tasks_analytics_all(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    rows = await StatsRepository(session).tasks_analytics_rows(owner_filter=None, limit=40)
    text = _tasks_analytics_message(rows, "📈 <b>Все задания</b> (последние 40)")
    for chunk in _text_chunks(text):
        await cb.message.answer(chunk, parse_mode="HTML")


@router.callback_query(F.data == "admin:tan:admin")
async def tasks_analytics_admin(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    rows = await StatsRepository(session).tasks_analytics_rows(owner_filter="admin", limit=40)
    text = _tasks_analytics_message(rows, "📈 <b>Задания админа</b>")
    for chunk in _text_chunks(text):
        await cb.message.answer(chunk, parse_mode="HTML")


@router.callback_query(F.data == "admin:tan:pick_mgr")
async def tasks_analytics_pick_mgr(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    ids = await StatsRepository(session).manager_ids_for_admin_report()
    if not ids:
        await cb.message.answer("Менеджеров в базе не найдено.")
        return
    rows_kb: list[list[InlineKeyboardButton]] = []
    for mid in ids[:24]:
        rows_kb.append(
            [InlineKeyboardButton(text=f"ID {mid}", callback_data=f"admin:tan:mgr:{mid}")]
        )
    rows_kb.append([InlineKeyboardButton(text="◀ Назад", callback_data="admin:tasks_analytics_menu")])
    await cb.message.answer("Выберите менеджера:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows_kb))


@router.callback_query(F.data.startswith("admin:tan:mgr:"))
async def tasks_analytics_one_mgr(cb: CallbackQuery, **data):
    await cb.answer()
    mid = int(cb.data.split(":")[-1])
    session = data["session"]
    rows = await StatsRepository(session).tasks_analytics_rows(owner_filter="manager", manager_user_id=mid, limit=40)
    text = _tasks_analytics_message(rows, f"📈 <b>Задания менеджера</b> <code>{mid}</code>")
    for chunk in _text_chunks(text):
        await cb.message.answer(chunk, parse_mode="HTML")


@router.callback_query(F.data == "admin:manager_bulk_menu")
async def manager_bulk_menu(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    stats = StatsRepository(session)
    ids = await stats.manager_ids_for_admin_report()
    pending = {m: (c, s) for m, c, s in await stats.managers_pending_payment_summary()}
    if not ids:
        await cb.message.answer("Менеджеров нет.")
        return
    lines = ["👔 <b>Менеджеры</b>", ""]
    for mid in ids[:30]:
        pc = pending.get(mid)
        if pc:
            lines.append(f"• <code>{mid}</code> — ждут оплаты: {pc[0]} шт. на {pc[1]:.2f} руб.")
        else:
            lines.append(f"• <code>{mid}</code> — нет завершённых без оплаты")
    lines.append("")
    lines.append("Кнопки: выключить все активные задания или напомнить про оплату.")
    for chunk in _text_chunks("\n".join(lines)):
        await cb.message.answer(chunk, parse_mode="HTML")

    kb_rows: list[list[InlineKeyboardButton]] = []
    for mid in ids[:20]:
        kb_rows.append(
            [
                InlineKeyboardButton(text=f"⏹ {mid}", callback_data=f"admin:bulk_off:{mid}"),
                InlineKeyboardButton(text=f"✉️ {mid}", callback_data=f"admin:remind_mgr:{mid}"),
            ]
        )
    kb_rows.append([InlineKeyboardButton(text="✉️ Напомнить всем с долгом", callback_data="admin:remind_all_managers")])
    kb_rows.append([InlineKeyboardButton(text="◀ К аналитике", callback_data="admin:analytics_hub")])
    await cb.message.answer("Действия:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


@router.callback_query(F.data.startswith("admin:bulk_off:"))
async def bulk_off_manager(cb: CallbackQuery, **data):
    await cb.answer()
    mid = int(cb.data.split(":")[-1])
    session = data["session"]
    n = await TaskItemRepository(session).deactivate_all_for_manager(mid)
    await cb.message.answer(f"Выключено активных заданий у менеджера <code>{mid}</code>: <b>{n}</b>.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin:remind_mgr:"))
async def remind_one_manager(cb: CallbackQuery, **data):
    await cb.answer()
    mid = int(cb.data.split(":")[-1])
    session = data["session"]
    stats = StatsRepository(session)
    pending_list = await stats.managers_pending_payment_summary()
    found = next((x for x in pending_list if x[0] == mid), None)
    if not found:
        await cb.message.answer(f"У менеджера <code>{mid}</code> нет завершённых попыток без оплаты.", parse_mode="HTML")
        return
    _, cnt, sm = found
    text = (
        "Напоминание от администратора.\n\n"
        f"У вас <b>{cnt}</b> завершённых выполнений без отметки «Оплатил» "
        f"на сумму около <b>{sm:.2f}</b> руб. по ценам заданий.\n"
        "Пожалуйста, проверьте панель менеджера и нажмите «Оплатить» где нужно."
    )
    try:
        await cb.bot.send_message(mid, text, parse_mode="HTML")
        await cb.message.answer(f"Сообщение отправлено менеджеру <code>{mid}</code>.", parse_mode="HTML")
    except Exception:
        await cb.message.answer(f"Не удалось написать менеджеру <code>{mid}</code> (бот заблокирован?).", parse_mode="HTML")


@router.callback_query(F.data == "admin:remind_all_managers")
async def remind_all_managers(cb: CallbackQuery, **data):
    await cb.answer()
    session = data["session"]
    pending_list = await StatsRepository(session).managers_pending_payment_summary()
    if not pending_list:
        await cb.message.answer("Нет менеджеров с неоплаченными completed.")
        return
    ok = 0
    for mid, cnt, sm in pending_list:
        text = (
            "Напоминание от администратора.\n\n"
            f"У вас <b>{cnt}</b> завершённых выполнений без отметки «Оплатил» "
            f"на сумму около <b>{sm:.2f}</b> руб.\n"
            "Проверьте панель менеджера."
        )
        try:
            await cb.bot.send_message(mid, text, parse_mode="HTML")
            ok += 1
        except Exception:
            pass
    await cb.message.answer(f"Отправлено менеджерам: {ok} из {len(pending_list)}.")


@router.callback_query(F.data == "admin:bot_status")
async def bot_status_cb(cb: CallbackQuery):
    await cb.answer()
    up = uptime_seconds()
    up_txt = f"{int(up)} с" if up is not None else "—"
    path = sqlite_db_file_path_from_url(DATABASE_URL)
    db_note = "SQLite файл" if path else "не файловая SQLite / другой DSN"
    await cb.message.answer(
        f"🤖 Версия: <code>{APP_VERSION}</code>\nUptime: {up_txt}\nБД: {db_note}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:db_backup")
async def db_backup(cb: CallbackQuery):
    await cb.answer()
    path = sqlite_db_file_path_from_url(DATABASE_URL)
    if not path or not os.path.isfile(path):
        await cb.message.answer("Бэкап доступен только для файловой SQLite. Сейчас путь к файлу не найден.")
        return
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        await cb.message.answer(f"Не удалось прочитать файл БД: {e}")
        return
    fn = f"seobot_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    await cb.message.answer_document(
        BufferedInputFile(data, filename=fn),
        caption="Копия SQLite. Храните в безопасном месте.",
    )

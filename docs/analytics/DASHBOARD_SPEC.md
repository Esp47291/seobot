# Dashboard spec — админ

Сейчас: `/status`, analytics hub, CSV 7/30/90, статистика заданий. Это не daily product dashboard.

## Ежедневно (5 минут, телефон)

| Виджет | Зачем | Источник сегодня | Цель |
|---|---|---|---|
| Новые /start | Приток | users.registered_at | + start events |
| Дошли до task_take | Активация | attempts created | event |
| Сдали review | Работа идёт | review_submitted + completed за день | event |
| Pass % за 24ч | Качество/фрод | completed/(completed+rejected) | то же |
| Очередь старше SLA | Обещание людям | review_submitted.submitted_at | нужен SLA |
| Выводы pending ₽ и шт | Кассовый риск | withdrawal_requests pending | есть в репо |
| Напоминания sent | Не заспамили | executor_repeat_reminders | лимит |

## Еженедельно

| Виджет | Зачем |
|---|---|
| Воронка F1 по дням | Где дыра UX |
| Time-to-moderation p50/p90 | Штат модерации |
| Time-to-pay p50 | Доверие исполнителей |
| Repeat take (2+ задания / активные) | Удержание |
| Ref cost % от payout | Юнит |
| Топ причин reject | Copy + инструкция |
| Задания без слотов / exhausted texts | Снабжение |

## SQL-черновики daily (вклеить в админ-статы, не ждать Mixpanel)

Сейчас `admin.py:stats` — lifetime totals. Для «5 минут утром» нужны **срезы за 24ч / очередь с возрастом**. Ниже — что дописать в `StatsRepository` днём (issue, не ночной рефакторинг).

| Виджет | Черновик | Уже близко в коде |
|---|---|---|
| Новые | `COUNT users WHERE registered_at > now-24h` | есть только `users_new_week` |
| Take 24ч | `COUNT attempts WHERE created_at > now-24h` | нет |
| Submit 24ч | `COUNT attempts WHERE submitted_at > now-24h` | нет |
| Pass % 24ч | completed / (c+r) где `updated_at > now-24h` и status in (completed,rejected) | нет |
| Queue aged | review_submitted и `submitted_at < now-SLA` | есть count без возраста; сорт `id DESC` |
| WD pending | уже `pending_wd_count` + `pending_wd_sum` | да в extras; в moderation hub только шт |
| Mgr unpaid | `awaiting_manager_payment` по snapshot | **не в moderation hub** — inbox Q5 SQL |
| Admission truth | waiting_approval + login_screenshot | хаб считает только первый |
| Ref cost 7д | SUM l1+l2 / SUM task_reward за 7д | сейчас COUNT lifetime — **не показывать как ₽** |

Красные линии назначить после первого факта, не выдумывать %. Гипотеза очереди: 24ч (помечать ASSUMPTION в UI, пока нет медианы).

## Чего не показывать как «правду»

- Подписки на канал по `news_accepted` — это клик, не membership.
- «Активные пользователи» без определения (нужен: 1+ proof_submit за 7д — предложить).
- `referral_payout_ops_total` как «стоимость рефералки».
- `tasks_completed` lifetime как «сегодня сделали».
- CSV completed как воронка (там нет take/fail/view).
- `SUM(task_items.price)` как GMV/выручку — это P_ex (COGS). Выручки нет, пока нет P_c.

## MIRO-READY

| Частота | Метрика | Формула / поле | Красная линия (назначить) |
|---|---|---|---|
| День | Queue aged | submitted_at > 24ч (гипотеза) | SQL в FUNNELS / DAILY_INBOX |
| День | WD pending ₽ | sum pending | extras, не хаб шт |
| День | Admission truth | waiting_approval + login_screenshot | хаб занижает |
| День | Mgr unpaid ₽ | completed ¬credited × price | snapshot / Q5 SQL |
| День | Pass % 24ч | completed/(c+r) за сутки | нет в хабе |
| День | Take / submit 24ч | attempts created / submitted_at | нет в хабе |
| Неделя | Unbounded D7 proxy | took_within_7d / new | SQL; не news_accepted |
| Неделя | Ref cost | SUM l1+l2 / SUM task_reward | не COUNT ops |

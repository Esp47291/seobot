# Воронки и формулы

Цифр конверсий в репо нет. Все % ниже — **формулы**, не факты. Считать после событий или SQL по patch-15.

Окна (research: Fairview 7д на B2B-активацию; Amplitude N-day vs unbounded; Marketplace Guide — **не мешать** supply и demand):

| Воронка | Окно конверсии | Тип retention | Почему так |
|---|---|---|---|
| F1 Activation | 7 суток с `start(is_new)` | N-day D1 — диагноз онбординга | Если за 7 дней нет submit — активация не случилась |
| F2 Money | 14 суток с `proof_submit(review)` до pass; WD — 7 суток с request | — | Модерация+касса ручные |
| F3 Executor | Return **On or After** D7/D30 | Unbounded | Гиг эпизодический: N-day D7 занизит «вернулся на 9-й день» |
| F3 Manager/B2B | Unbounded D30 | отдельно | Другой ритм, другая «активность» |
| F4 Referral | 30 суток с join до first completed | — | Qualified ≠ регистрация |

«Активный исполнитель» = ≥1 `proof_submit` **или** `completed` за период. Не `news_accepted`, не любой `/start`.  
«Активный менеджер» = ≥1 действие: новое задание / outpay / WD. Не смешивать в один DAU.

## F1. Активация исполнителя (D0)

```
start(is_new) → rules_accept → onboarding_done(executor)
  → task_view → task_take → proof_submit(review)
```

| Шаг | Формула | Факт сейчас |
|---|---|---|
| CR rules | rules_accept / start(is_new) | ASSUMPTION: `users.rules_accepted` / новые за день |
| CR view | task_view / onboarding_done | нет события |
| CR take | task_take / task_view | attempts / ? |
| CR submit review | proof_submit(review) / task_take | submitted / started |

## F2. Качество и деньги

```
proof_submit(review) → moderation_pass(review) → balance_update(task_reward)
  → withdraw_request → withdraw_paid
```

| Метрика | Формула | Где снять |
|---|---|---|
| Pass rate | completed / (completed+rejected) по review | attempts |
| Time-to-moderation | median(updated_at − submitted_at) на completed/rejected | attempts |
| Withdraw CR | withdraw_paid / withdraw_request | withdrawal_requests |
| Time-to-pay | median(processed_at − created_at) paid | withdrawal_requests |
| Take-home | сумма task_reward − withdraw pending/paid за период | balance_operations |

## F3. Удержание

| Метрика | Формула | Комментарий |
|---|---|---|
| D1/D7 return | юзеры с любым событием в день 1/7 / коhort start | нет event log |
| Repeat take | users с ≥2 task_take / users с ≥1 | attempts |
| Post-fail return | task_view после moderation_fail за 72ч / fails | research: критично для T&S |
| Reminder lift | task_take за 24ч после reminder / reminders sent | executor_repeat_reminders |

## F4. Реферал

| Метрика | Формула |
|---|---|
| Invite CR | referral_join / users кто открыл экран рефералки (события нет) |
| Qualified | referees с ≥1 completed / joins |
| Ref cost | sum referral_l1+l2 / sum task_reward за период |

Полная цепочка L1+L2 = **25%** от цены задания сверх выплаты исполнителю (код `task_payout.py`). Это не выручка, это cost.

## F2b. Ловушка «completed ≠ деньги»

Задания менеджера (`task_items.created_by_user_id IS NOT NULL`): `review_ok` ставит `completed`, баланс — только `mgr:outpay` (`balance_credited=True`).

| Метрика | Формула | Ошибка, если забыть |
|---|---|---|
| Pass rate | completed / (completed+rejected) | ок как качество модерации |
| Paid-out rate | completed AND balance_credited / completed | ниже pass на менеджерских слотах |
| Take-home | sum `task_reward` в balance_operations | не sum(price) по всем completed |

## F5. B2B (будущее)

`biz_lead → qualify → first_brief → first_task_live → repeat_order`  
Сейчас воронки нет — нет сайта и сущности «заказчик».

Qualify (H4, руками в чате менеджера, пока нет CRM):

| Исход | Когда | Дальше |
|---|---|---|
| `take` | Q3 = процесс, Q4 = честный темп, город слотопригоден | бриф → `TaskItem` |
| `no_take` | рейтинг-квота, готовый текст, без визита, «чтобы не заметили» | скрипт 16; не «проигранная цена» и не скидка: EV ≤ 0 (UNIT H5) |
| `hold` | город без supply | **ASSUMPTION** не обещать дату; не создавать слот «в никуда» |

Формула когда появится таблица: `take / biz_lead`, `live_task / take`. Не делить live на все лиды вместе с no_take — иначе «конверсия продаж» врёт.

Исходы те же на **холодном** F5 (H6, нет `biz_lead`): знаменатель недели = `sent` (15 уникальных карточек), не «сделки». Смотреть `brief / replied` и доли take/no_take/hold после brief. Скидка, чтобы no_take стал take, ломает и F5, и CM1. Трекер: `docs/sales/ACQUISITION.md`.

## Операторские (ежедневно)

- Очередь: count review_submitted + waiting_approval старше SLA (SLA ещё не задан — назначить).
- Выводы pending: count + sum.
- Broadcast: sent vs click — click не измерить без кнопок.

## SQL-прокси на сегодня (SQLite / patch-15)

Цифр в репо нет — это запросы, чтобы владелец снял факт с прод-БД. Даты: подставить окно.

**F1 куски, которые есть:**

```sql
-- новые за день (прокси start is_new)
SELECT date(registered_at) AS d, COUNT(*) FROM users GROUP BY 1;

-- take за день
SELECT date(created_at) AS d, COUNT(*) FROM attempts GROUP BY 1;

-- submit review за день (прокси proof_submit kind=review)
SELECT date(submitted_at) AS d, COUNT(*) FROM attempts
WHERE submitted_at IS NOT NULL GROUP BY 1;

-- CR take→submit за календарный день (грубо: разные когорты смешаны)
-- лучше: take_day = date(created_at), submit в окне 7д
SELECT date(a.created_at) AS take_d,
       COUNT(*) AS takes,
       SUM(CASE WHEN a.submitted_at IS NOT NULL
                 AND a.submitted_at <= datetime(a.created_at, '+7 days')
                THEN 1 ELSE 0 END) AS submit_7d
FROM attempts a GROUP BY 1;
```

**Чего SQL не заменит:** `task_view`, повторный `start`, `source`, дневной `rules_accept` (флаг без ts), `channel_gate_ok` (self-click без ts).

**F2 pass + скорость модерации:**

```sql
SELECT
  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS passed,
  SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS failed,
  -- p50 в SQLite нет целиком; снять сырьё и посчитать снаружи
  AVG((julianday(updated_at)-julianday(submitted_at))*24) AS t_mod_hours_avg
FROM attempts
WHERE status IN ('completed','rejected') AND submitted_at IS NOT NULL;
```

ASSUMPTION: `updated_at` ≈ момент решения. Если админ правил запись позже — завысит. Факт: замерить на 20 строках глазами.

**F2 деньги / менеджерский лаг:**

```sql
SELECT
  SUM(CASE WHEN t.created_by_user_id IS NULL THEN 1 ELSE 0 END) AS admin_completed,
  SUM(CASE WHEN t.created_by_user_id IS NOT NULL THEN 1 ELSE 0 END) AS mgr_completed,
  SUM(CASE WHEN t.created_by_user_id IS NOT NULL AND a.balance_credited=1 THEN 1 ELSE 0 END) AS mgr_paid
FROM attempts a JOIN task_items t ON t.id=a.task_item_id
WHERE a.status='completed';
```

**F3 unbounded D7 (исполнитель, когорта регистрации):**

```sql
-- доля новичков дня D, у кого есть take ИЛИ submit в [D, D+7]
SELECT date(u.registered_at) AS cohort,
       COUNT(*) AS n,
       SUM(CASE WHEN EXISTS (
         SELECT 1 FROM attempts a
         WHERE a.user_id=u.user_id
           AND a.created_at <= datetime(u.registered_at, '+7 days')
       ) THEN 1 ELSE 0 END) AS took_within_7d
FROM users u GROUP BY 1;
```

Это **прокси** «дошёл до ценности», не классический Return On D7. Настоящий D1/D7 по шагам — после Phase 1 логов.

**F4 ref cost (не COUNT из админки):**

```sql
SELECT
  SUM(CASE WHEN operation_type='task_reward' THEN amount ELSE 0 END) AS payout,
  SUM(CASE WHEN operation_type IN ('referral_commission_l1','referral_commission_l2')
           THEN amount ELSE 0 END) AS ref_cost
FROM balance_operations
WHERE created_at >= datetime('now','-30 days');
-- ref_cost / payout ; админ-хаб показывает COUNT ops — не это
```

**Очередь старше гипотезы SLA 24ч:**

```sql
SELECT COUNT(*) FROM attempts
WHERE status='review_submitted'
  AND submitted_at < datetime('now','-1 day');
```

## MIRO-READY

| Воронка | Шаги | Ключевая конверсия | Источник факта |
|---|---|---|---|
| F1 Activation | start→view→take→submit (окно 7д) | submit_7d / start(new) | SQL take/submit есть; view/start — events |
| F2 Money | submit→pass→credited→wd_paid | pass%; paid-out%; t-pay | attempts + balance_credited |
| F3 Retention | supply vs demand; unbounded D7 | took_within_7d; D7 events | SQL proxy / events |
| F4 Referral | join→qualified→reward | qualified/join; ref_cost/payout | SUM ops, не COUNT |
| F5 B2B | lead→qualify(take/no_take/hold)→live task | take / biz_lead; live / take | нет сущности; qualify руками |

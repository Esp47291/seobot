# Daily inbox — OPS-01

Цель: 8–12 минут утром. Не «открыть хаб и увидеть красные цифры» — это не workflow (LOW/CODE, AppCloneLabs). Пройти **пять полос**, каждую с возрастом и следующим действием.

Код не нужен. Источник: `origin/patch-15` `a768bf3`. Цифр прод-БД в репо нет — SQL ниже снять с факта.

Не предлагаем обход ToS. Inbox чинит тишину, кассу и stuffing в продукте, не «чтобы площадка не заметила».

## Что уже есть vs чего не хватает

Хабы: `admin:moderation_hub` (`StatsRepository.moderation_hub_counts`) и extras (`admin_dashboard_extras`).

| Полоса | Где в UI сейчас | Что считает код | Дыра |
|---|---|---|---|
| Q1 Допуск | `admin:admission_queue` | Очередь: `waiting_approval` **и** `login_screenshot`. Хаб `admission` = **только** `waiting_approval` | Хаб занижает. Extras `profiles_awaiting_admin` ближе к правде |
| Q2 Отзыв | `admin:reviews_queue` | `review_submitted` | Count без возраста. Сорт `id DESC` = новые сверху, stale внизу |
| Q3 2-й аккаунт | `admin:secacc_queue` | `second_account_reviews.status=pending` | Без возраста; лимит 40 |
| Q4 Вывод | WD в хабе = шт | extras: `pending_wd_count` + `pending_wd_sum` | В хабе нет ₽. Нет hold «первый WD» |
| Q5 Mgr unpaid | спрятано в snapshot менеджера | `completed` AND `balance_credited=0` по `created_by_user_id IS NOT NULL` | **Нет в moderation hub.** Это касса, не «ещё одна модерация» |

Порядок в очередях: `Attempt.id DESC` — противоположность SLA. Сначала SQL aged, потом клики в UI.

## Severity, не один SLA

Один срок на всё врёт (gruv.ai). Гипотезы до медианы с прода — в UI и copy помечать ASSUMPTION. Не писать исполнителю «проверка 5 минут».

| Sev | Что | Гипотеза срока | Кто | Не делать |
|---|---|---|---|---|
| S0 | Жалоба площадки / юрист / «это накрутка» от клиента | стоп объёма сразу | владелец | спорить, маскировать, ускорять слоты |
| S1 | WD pending, **фондирован** (есть входящий P_c) | 24ч рабочих | admin | платить нефондированное «чтобы supply не ушёл» |
| S2 | `review_submitted` aged | 24ч (гипотеза FUNNELS) | admin/manager | молчание; фейковый таймер |
| S3 | допуск (аккаунт/логин) aged | 48ч | admin | путать с Q2: это ещё не отзыв |
| S4 | первый WD новичка (0 paid WD) | hold, не ускорять | admin | автовыплата; крупный первый вывод без сверки реквизитов |
| S5 | mgr unpaid (completed, не credited) | до P_c, не «до вчера» | manager | `mgr_outpay` в долг кассы |

UX-03 (текст после скрина) берёт ETA из **рабочих часов + S2**, не из желаемого маркетинга. Медиану — SQL `t_mod` в FUNNELS, когда снимете 20 строк глазами.

## Ритуал (порядок, 8–12 мин)

1. **S0 scan** — нет ли входящих претензий в Telegram staff. Есть → стоп новых take/слотов, разбор playbook в RISKS.  
2. **Q5 SQL** — mgr unpaid шт и ₽. Это дыра кассы: баланс ещё не создан, но человек уже «сдал».  
3. **Q4 SQL** — WD pending шт+₽, из них unfunded vs first-WD. Платить только фондированное; S4 — hold.  
4. **Q2 aged** — `review_submitted` старше 24ч. Разбирать **с конца**, не с новых.  
5. **Q1 aged** — допуск старше 48ч. Помнить: хаб `admission` без `login_screenshot`.  
6. **Q3** — second-acc. Новичок (0 completed) — всегда руками (TechVinta).  
7. **Prebuilt stop** — сегодня не жать `admin:allow` / mgr-allow на задании, где `prebuilt_texts_json` не `[]`. Диктовка уходит в чат исполнителю (C-15).  
8. **Deploy freeze** — если в Q1–Q4 кто-то в FSM (скрин, вывод, мастер задания): не рестартить бота. `MemoryStorage` сотрёт сдачу (TECH-01).

Конец ритуала: 4 числа в заметку владельца (не в git с персональными данными): aged Q2, WD pending ₽, mgr unpaid ₽, сколько allow без prebuilt.

## SQL — снять с прод-SQLite сегодня

Даты UTC как в моделях (`datetime.utcnow`). Не копировать реквизиты/file_id в docs и чаты вне staff.

**Полоса Q1 — хаб врёт, очередь нет**

```sql
-- хаб admission vs реальная очередь допуска
SELECT
  SUM(CASE WHEN status='waiting_approval' THEN 1 ELSE 0 END) AS hub_admission,
  SUM(CASE WHEN status='login_screenshot' THEN 1 ELSE 0 END) AS missing_from_hub,
  SUM(CASE WHEN status IN ('waiting_approval','login_screenshot') THEN 1 ELSE 0 END) AS queue_truth
FROM attempts;

-- aged допуск (S3, 48ч). submitted_at на этом шаге часто NULL → created_at
SELECT id, user_id, status, created_at
FROM attempts
WHERE status IN ('waiting_approval','login_screenshot')
  AND created_at < datetime('now','-2 days')
ORDER BY created_at ASC;
```

**Полоса Q2 — отзыв + возраст**

```sql
SELECT COUNT(*) AS reviews_now FROM attempts WHERE status='review_submitted';

SELECT id, user_id, task_item_id, submitted_at
FROM attempts
WHERE status='review_submitted'
  AND submitted_at < datetime('now','-1 day')
ORDER BY submitted_at ASC;
```

**Полоса Q3**

```sql
SELECT id, user_id, platform, created_at
FROM second_account_reviews
WHERE status='pending'
ORDER BY created_at ASC;
```

**Полоса Q4 — касса WD**

```sql
SELECT COUNT(*) AS n, ROUND(SUM(amount),2) AS rub
FROM withdrawal_requests WHERE status='pending';

-- первый WD пользователя (S4). ASSUMPTION: hold, пока нет paid по этому user_id
SELECT w.id, w.user_id, w.amount, w.created_at
FROM withdrawal_requests w
WHERE w.status='pending'
  AND NOT EXISTS (
    SELECT 1 FROM withdrawal_requests p
    WHERE p.user_id=w.user_id AND p.status='paid'
  )
ORDER BY w.created_at ASC;
```

**Полоса Q5 — mgr unpaid (нет в хабе)**

```sql
SELECT COUNT(*) AS n, ROUND(SUM(t.price),2) AS p_ex_rub
FROM attempts a
JOIN task_items t ON t.id=a.task_item_id
WHERE a.status='completed'
  AND a.balance_credited=0
  AND t.created_by_user_id IS NOT NULL;
```

Это **не** выручка. `price` = P_ex. Пока нет P_c — Q5+Q4 считать нефондированными (UNIT H5).

**Инвентарь stuffing (не слать, посчитать)**

```sql
SELECT COUNT(*) AS tasks_with_prebuilt
FROM task_items
WHERE is_active=1
  AND prebuilt_texts_json IS NOT NULL
  AND TRIM(prebuilt_texts_json) NOT IN ('[]','');
```

Секрет прокси из `middlewares/rules.py` **не** выгружать. Ротация — дневной TECH, не этот SQL.

## Кассовый шлюз перед «Выплачено»

Пока нет сущности счёта, шлюз бумажный. Перед `mark_paid`:

| Вопрос | Если нет | Действие |
|---|---|---|
| Клиент оплатил этот объём? (P_c вне БД) | WD = нефондировано | не `paid`; hold |
| Реквизиты = `users.payout_requisites` и не сменились перед WD? | риск перехвата | сверка, не авто |
| Это первый WD и 0 completed давно / новый аккаунт? | S4 | hold 24ч гипотеза |
| Q5 по тому же менеджеру растёт? | outpay в долг | сначала P_c, потом баланс, потом WD |

Не ускорять выплаты ради удержания исполнителей — это ускорение дыры кассы (gruv: friction на payout оправдан сильнее, чем на профиле).

## Prebuilt в inbox = ToS, не «копирайт»

При `admin:allow` (и аналог менеджера) исполнителю уходит блок «Готовый текст для отзыва» + опционально «прикрепите это фото». Исчерпание текстов **отключает задание** и может `decline` попытку.

Google Maps UGC: incentive за отзыв запрещён; апрель 2026 — отдельно запрет **диктовать содержание** и квоты на сбор. Это не чинится переименованием в «подсказку».

Операторское правило сегодня: allow без отправки шаблона. Код вырезать — дневной PR COPY-01, не ночной рефакторинг.

## Definition of done (OPS-01)

| Сейчас (этот run) | День (код, не ночь) |
|---|---|
| Ритуал + SQL есть; владелец гоняет руками | Хаб: admission = оба статуса; aged count; WD ₽; полоса Q5 |
| Сортировка в UI всё ещё DESC | Очереди `ORDER BY submitted_at/created_at ASC` |
| SLA = гипотеза 24/48 | После 20 фактов — медиана в UX-03 |
| Prebuilt stop = дисциплина allow | Не слать `selected_prebuilt_text` |

Не считать OPS-01 закрытым, пока хаб врёт по Q1 и молчит по Q5.

## MIRO-READY

### Inbox lanes

| ID | Полоса | Статус SQL | UI сегодня | Sev | Следующее действие |
|---|---|---|---|---|---|
| Q1 | Допуск | waiting_approval + login_screenshot | очередь оба; хаб только первый | S3 | aged 48ч с конца |
| Q2 | Отзыв | review_submitted | count, без возраста | S2 | aged 24ч с конца |
| Q3 | 2-й акк | secacc pending | до 40 шт | — | новичок всегда руками |
| Q4 | Вывод | WD pending шт+₽ | хаб без ₽ | S1/S4 | шлюз фондирования |
| Q5 | Mgr unpaid | completed ¬credited | snapshot менеджера | S5 | не outpay в долг |

### Ритуал 8 шагов

| # | Шаг | Стоп если |
|---|---|---|
| 1 | S0 претензия | стоп слотов |
| 2 | Q5 ₽ | нет P_c → не outpay |
| 3 | Q4 ₽ | unfunded / first WD |
| 4 | Q2 aged | тишина >24ч |
| 5 | Q1 aged | хаб ≠ очередь |
| 6 | Q3 | пачка second-acc |
| 7 | Prebuilt | не allow с шаблоном |
| 8 | Deploy freeze | активный FSM |

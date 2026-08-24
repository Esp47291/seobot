# Event taxonomy

Словарь целевых событий. **В коде patch-15 их нет как event-stream** — есть CSV выгрузки Attempt/Withdrawal и админ-хаб (снимки очередей + completed).  
Имена стабильные, snake_case. Не переименовывать из ТЗ ради «object-action»: ломает уже написанные journeys. Контекст — в properties.

Общие properties: `user_id`, `ts`, `role` (user|manager|admin), `city_selected`, `platform`, `source` (menu|deeplink|broadcast|reminder).

Аудит H2 (2026-08-24): CSV экспортирует **только completed** attempts; `rules_accepted` / `news_accepted` — флаги без timestamp; `/menu` визуально как `/start`, но это не новый вход. Реквизиты в CSV есть — в события **не копировать**.

| name | когда | properties |
|---|---|---|
| start | /start обработан | `is_new`, `has_ref`, `referrer_id?`, `role_intent?` |
| rules_accept | нажал «Принять правила» | — |
| onboarding_done | дошёл до меню роли | `path`: executor\|biz |
| channel_gate_ok | прошёл gate канала | `method`: self_click\|membership |
| venue_city_select | выбрал город точки | `city` |
| platform_select | выбрал площадку | `platform` |
| task_view | показал карточку | `task_id`, `price`, `platform`, `venue_city` |
| task_take | «Начать задание» / создан Attempt | `task_id`, `attempt_id` |
| task_skip | «Не интересно» / следующее | `task_id`, `reason`: skip\|next |
| proof_submit | принят скрин | `attempt_id`, `kind`: account\|review\|secacc |
| moderation_pass | ступень ок | `attempt_id`, `stage`: account\|review\|secacc, `actor_id` |
| moderation_fail | отказ/decline | `attempt_id`, `stage`, `reason_code`, `actor_id` |
| balance_update | баланс изменился | `delta`, `reason`: task_reward\|referral_l1\|referral_l2\|withdraw\|withdraw_return\|adjust |
| withdraw_request | создана заявка | `wd_id`, `amount` |
| withdraw_paid | отметили выплату | `wd_id`, `amount`, `actor_id` |
| withdraw_rejected | отказ заявки | `wd_id`, `amount` |
| referral_join | зафиксирован реферер | `referrer_id`, `referee_id` |
| referral_reward | комиссия начислена | `referrer_id`, `level`: 1\|2, `base_amount`, `commission` |
| broadcast_sent | рассылка ушла (сервер) | `mode`, `audience_size` |
| broadcast_click | клик по кнопке из рассылки | `campaign_id` (сейчас кнопок нет — добавить) |
| repeat_reminder_sent | напомнили «можно снова» | `platform` |
| biz_lead | заявка бизнеса | `source` |
| staff_open | /admin или /manager | `role` |
| withdraw_blocked_min | нажал вывод, баланс < min | `balance`, `min` — **не в ТЗ**, ловит friction кабинета |
| task_resume | «Начать» на уже живой Attempt | `attempt_id`, `status` — не путать с `task_take` |

Минимум из ТЗ покрыт: start, onboarding_done, task_view, task_take, proof_submit, moderation_pass/fail, balance_update, withdraw_request, withdraw_paid, referral_join, referral_reward, broadcast_click.

## Где взять факт сегодня (без событий)

| Вопрос | Таблица patch-15 |
|---|---|
| Новые люди | `users.registered_at` |
| Взяли задание | `attempts` created, status ≠ canceled |
| Сдали отзыв | `review_submitted` / submitted_at |
| Pass/fail | completed / rejected |
| Выводы | `withdrawal_requests` |
| Рефералы | `referrals` + `balance_operations` types referral_commission_l* |

## MIRO-READY

| event | trigger | must-have props | есть в коде? |
|---|---|---|---|
| start | /start | is_new, has_ref | нет |
| onboarding_done | меню роли | path | нет |
| task_view | карточка | task_id, price | нет |
| task_take | Attempt create | attempt_id | частично (строка БД) |
| proof_submit | скрин сохранён | kind | частично |
| moderation_pass | completed/approved | stage | частично |
| moderation_fail | rejected/declined | reason_code | частично |
| balance_update | операция | delta, reason | `balance_operations` |
| withdraw_request | insert WD | amount | строка БД |
| withdraw_paid | status paid | amount | строка БД |
| referral_join | set_referrer | referrer_id | строка БД |
| referral_reward | grant_* | level | balance_operations |
| broadcast_click | click | campaign_id | нет |

---

## Правила имени и свойств (чтобы завтра не разъехалось)

Research: object-action, без дат/id в имени, варианты — property, не новое событие ([handbook](https://productanalyticshandbook.com/blog/event-taxonomy-object-action/), [Fairview](https://getfairview.com/blog/product-analytics-setup-guide)).

| Правило | Для Job Inside |
|---|---|
| Имя = шаг, исход = property | Не плодить `moderation_pass_yandex`. Площадка в `platform` |
| Один event, если когда-нибудь нарисуем на одной линии | `proof_submit` + `kind`, не три имени скринов |
| Исключение ТЗ | `moderation_pass` / `moderation_fail` оставляем раздельно: это разные решения очереди, не «статус одного шага» |
| Enum, не свободный текст | `platform`, `stage`, `reason_code`, `source`, `role` |
| Деньги | `amount` числом, валюта отдельно (`currency=RUB`). Не строка «130 руб.» |
| PII | В событие: только `user_id`. Не писать реквизиты, username, first_name, текст отказа целиком (только `reason_code` + опционально hash) |
| Кардинальность | `task_id` / `attempt_id` ок в warehouse/SQLite. Не класть полный `instruction_url` в каждый view |

`reason_code` (черновик, не в коде): `account_unclear` · `account_mismatch` · `review_not_visible` · `review_not_match_brief` · `duplicate_proof` · `other`. Свободный текст админа — в Attempt, не в event.

---

## Куда вставить (patch-15) — не писать код ночью

Один хелпер `services/analytics.py` → `emit(name, user_id, **props)`. Phase 1 = structured log. Phase 2 = insert в `analytics_events`. Не размазывать `logger.info` по 20 файлам без обёртки.

### Фаза 0 — уже можно считать SQL (см. FUNNELS)

Без новых таблиц: users / attempts / withdrawal_requests / balance_operations / referrals.

### Фаза 1 — три лога (AN-01, маленький PR днём)

Хватает, чтобы увидеть дыру «пришли → взяли → сдали».

| # | event | Файл:функция | Когда стрелять | Когда НЕ стрелять |
|---|---|---|---|---|
| 1 | `start` | `handlers/user.py`:`start_cmd` после `get_or_create` | Каждый `/start`, даже повторный | `/menu` (`menu_cmd`) — это возврат в меню, `source` другой или тишина |
| 2 | `task_take` | `handlers/user.py`:`start_task` сразу после `attempt_repo.create` | Только новый Attempt | Resume уже живой попытки (`waiting_approval` / `approved` / `review_submitted`) — это `task_resume` |
| 3 | `proof_submit` | `handlers/user.py`:`submit_executor_review_photo` после успешного `submit_review` | `kind=review` | Отказ «нет реквизитов» (return False). Скрин аккаунта — отдельный вызов в `_process_account_screenshot_file`, `kind=account` |

Реферал на старте: если `created` и `set_referrer_if_first_time` ок → рядом `referral_join`. Не ждать Phase 2.

### Фаза 2 — полный словарь (после того как 3 лога живут неделю)

| event | Файл:функция | Триггер (факт кода) |
|---|---|---|
| `rules_accept` | `user.py`:`accept_rules` | после `rules_accepted=True` |
| `onboarding_done` | там же + первый показ меню роли | сейчас роли нет — `path=executor` по умолчанию; `path=biz` появится с UX-01 |
| `channel_gate_ok` | `user.py`:`begin_tasks` | когда ставят `news_accepted=True` (это self-click, property `method=self_click`) |
| `venue_city_select` | `user.py`:`pick_task_venue` | после `selected_venue_city` |
| `platform_select` | `user.py`:`choose_platform` | после парсинга `platform:` |
| `task_view` | `user.py`:`_show_task_card` | каждое показ карточки, в т.ч. next/skip |
| `task_skip` | `user.py`:`skip_task` / `next_task` | `reason=skip\|next` |
| `moderation_pass` stage=account | `admin.py`:`allow_attempt` | статус стал approved |
| `moderation_fail` stage=account | `admin.py`:`decline_attempt_finish` | decline |
| `moderation_pass` stage=review | `admin.py`:`review_ok` после `complete()` | **не равно выплате**, если `task.created_by_user_id` |
| `moderation_fail` stage=review | `admin.py`:`review_bad_finish` | reject + reason |
| `moderation_pass` stage=secacc | `admin.py`:`admin_secacc_ok` | second_account_reviews |
| `moderation_fail` stage=secacc | `admin.py`:`admin_secacc_reject` | |
| `balance_update` reason=task_reward / referral_l* | `services/task_payout.py`:`grant_task_completion_rewards` | вызывается из `review_ok` (админ-задание) **или** `manager.py`:`mgr_outpay` |
| `balance_update` reason=withdraw | `user.py`:`withdraw_requisites` вместе с `wd_repo.create` | тот же момент, что `withdraw_request` |
| `balance_update` reason=withdraw_return | `admin.py`:`wd_rej` / `manager.py`:`mgr_wd_rej` | |
| `withdraw_request` | `user.py`:`withdraw_requisites` | после create WD |
| `withdraw_paid` | `admin.py`:`wd_paid` **и** `manager.py`:`mgr_wd_paid` | оба пути |
| `withdraw_rejected` | `wd_rej` / `mgr_wd_rej` | |
| `referral_reward` | тот же `grant_task_completion_rewards` | по одному event на уровень, если комиссия реально начислена |
| `broadcast_sent` | `admin.py`:`broadcast_send` / `manager.py`:`mgr_broadcast_send` | `mode=all\|personal`, `audience_size` |
| `broadcast_click` | нет кнопки в рассылке | не инструментировать, пока нет `campaign_id` в inline |
| `repeat_reminder_sent` | `services/executor_repeat_reminder.py`:`process_due_executor_reminders` | после успешного send + `mark_sent` |
| `staff_open` | `admin.py`:`cmd_admin` / `manager.py`:`cmd_manager` | |
| `biz_lead` | нет сущности | сайт / ветка /start |

### Ловушка менеджерского задания

`review_ok` при `created_by_user_id IS NOT NULL` делает `completed`, пишет менеджеру «оплатите», **баланс не трогает**.  
`balance_update` + реферал 20/5 случаются только в `mgr_outpay`.  
Если мерить «pass → деньги» по `completed`, завысим выплаченный take-home. Формула — в FUNNELS F2.

---

## Схема `analytics_events` (Phase 2, не мигрировать ночью)

| Колонка | Тип | Зачем |
|---|---|---|
| id | PK | |
| ts | DateTime UTC | не локаль сервера в тексте |
| name | String(64), index | словарь выше |
| user_id | BigInteger, index | кто совершил (исполнитель; для staff_* — staff) |
| role | String(16) | user\|manager\|admin |
| source | String(32) | menu\|deeplink\|broadcast\|reminder\|null |
| platform | String(50), nullable | |
| task_id | int, nullable | |
| attempt_id | int, nullable | |
| props_json | Text | остальное: is_new, kind, stage, amount, reason_code… |

Индексы: `(name, ts)`, `(user_id, ts)`. Идемпотентность денег: не дедупить по имени — повтор `balance_update` с другим `delta` законен. Дедуп только технических ретраев (один `attempt_id`+`name`+`kind` на proof).

Контракт хелпера (псевдокод, не в репо):

```
async def emit(session, name, user_id, **props):
    # Phase 1: logger.info("ji_event name=%s user_id=%s %s", name, user_id, json.dumps(safe_props))
    # Phase 2: INSERT analytics_events
```

`safe_props` выкидывает ключи `requisites`, `payout_requisites`, `username`, `text`, `phone`.

---

## Что админ-хаб уже считает (чтобы не дублировать)

`StatsRepository.summary` + `admin_dashboard_extras` + moderation hub:

| Уже есть на экране | Это не |
|---|---|
| users_total, users_new_week | `start` по дням, is_new vs вернувшиеся |
| tasks_completed (lifetime completed) | сданные / отклонённые за 24ч |
| pending WD count+sum | time-to-pay |
| reviews_awaiting, profiles_awaiting, secacc pending | возраст очереди > SLA |
| referral_payout_ops_total | **COUNT операций, не сумма ₽** — нельзя брать как ref cost |
| CSV attempts | только `status=completed` + реквизиты. Нет view/take/fail |
| CSV withdrawals | по created_at, все статусы периода |

Daily inbox (OPS-01) = ритуал в `docs/ops/DAILY_INBOX.md`. Не доверять хабу `admission` (нет `login_screenshot`); Q5 mgr unpaid в хабе нет; очереди `id DESC`. Event-таблица нужна для F1 (view) и F3 (D1/D7 по шагам), не для утренней кассы.

# Event taxonomy

Словарь целевых событий. **В коде patch-15 их нет** — есть CSV выгрузки Attempt/Withdrawal и админ-хаб.  
Имена стабильные, snake_case. Писать в одну таблицу `analytics_events` (рекомендация, не делать ночью).

Общие properties: `user_id`, `ts`, `role` (user|manager|admin), `city_selected`, `platform`, `source` (menu|deeplink|broadcast|reminder).

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

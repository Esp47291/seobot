# Воронки и формулы

Цифр конверсий в репо нет. Все % ниже — **формулы**, не факты. Считать после событий или SQL по patch-15.

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

## F5. B2B (будущее)

`biz_lead → qualify → first_brief → first_task_live → repeat_order`  
Сейчас воронки нет — нет сайта и сущности «заказчик».

## Операторские (ежедневно)

- Очередь: count review_submitted + waiting_approval старше SLA (SLA ещё не задан — назначить).
- Выводы pending: count + sum.
- Broadcast: sent vs click — click не измерить без кнопок.

## MIRO-READY

| Воронка | Шаги | Ключевая конверсия | Источник факта |
|---|---|---|---|
| F1 Activation | start→view→take→submit | submit / start(new) | events; пока SQL attempts/users |
| F2 Money | submit→pass→wd_paid | pass rate; time-to-pay | attempts, withdrawals |
| F3 Retention | cohort D1/D7; post-fail | D7; return after fail | нужно events |
| F4 Referral | join→qualified→reward | qualified / join | referrals + attempts |
| F5 B2B | lead→live task | live / lead | нет |

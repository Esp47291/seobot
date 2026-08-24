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

## Чего не показывать как «правду»

- Подписки на канал по `news_accepted` — это клик, не membership.
- «Активные пользователи» без определения (нужен: 1+ proof_submit за 7д — предложить).

## MIRO-READY

| Частота | Метрика | Формула / поле | Красная линия (назначить) |
|---|---|---|---|
| День | Queue aged | submitted_at > SLA | SLA нет — взять 24ч как гипотезу |
| День | WD pending ₽ | sum pending | касса |
| День | Pass % | completed/(c+r) | расследовать < ASSUMPTION после факта |
| Неделя | D7 return | events | нет данных |
| Неделя | Ref cost | ref ops / task_reward | если > запаса в цене заказчика |

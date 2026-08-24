# Ключевые таблицы — копипаст в Miro

## Unit economics

| Статья | Обозначение | Значение / формула | Источник факта |
|---|---|---|---|
| Выплата исполнителю | P_ex | task.price | TaskItem.price |
| Мин. Яндекс | floor_ya | 130 | BotSetting default |
| Мин. Google | floor_g | 35 | default |
| Мин. 2ГИС | floor_2 | 12 | default |
| Реферал L1 | r1 | 0.20 * P_ex | task_payout.py |
| Реферал L2 | r2 | 0.05 * P_ex | task_payout.py |
| Худший ref | r_max | 0.25 * P_ex | оба уровня |
| Мин. вывод | W_min | 20 | default |
| Цена клиенту | P_c | нет в БД | договор |
| Модерация + перевод | C_ops | неизвестно | замерить |
| Мин. P_c с запасом ref | P_c_min | P_ex*1.25 + C_ops + запас | до оффера ₽ |

## Funnel

| Воронка | Шаги | Ключевая конверсия | Источник факта |
|---|---|---|---|
| F1 Activation | start→rules→view→take→submit | submit / start(new) | events; пока users+attempts |
| F2 Money | submit→pass→wd_paid | pass%; time-to-pay | attempts, withdrawals |
| F3 Retention | D1/D7; return after fail | D7 | нужно events |
| F4 Referral | join→qualified→reward | qualified/join; ref cost% | referrals + ops |
| F5 B2B | lead→live task | live/lead | нет сущности |

## 30-day plan

| Неделя | Продукт | Продажи | Контент | Метрики |
|---|---|---|---|---|
| 1 | роли /start, ТЗ на карточке, SLA-текст | 15 outbound | 3 поста правил | new, take, submit, pass%, WD pending |
| 2 | статус вывода; лог 3 событий | FU + 10 + созвон | черновик лендинга | t-moderation p50 |
| 3 | FSM persist если жжёт; сегмент broadcast | закрыть пилот | кейс процесса | CM пилота |
| 4 | 8 событий taxonomy | повтор/разбор | FAQ | D7 proxy |

## Risks

| Риск | Почему реален | Митигация | P |
|---|---|---|---|
| ToS площадок | отзывы за ₽ | реальный визит, стоп по претензии | P0 |
| Репутация | copy «платим за отзывы» | COPY_SYSTEM, сайт-процесс | P0 |
| Фрод | скорость, second-acc, ref-веер | очередь новичков, hold 1-го WD | P0 |
| Ручные выплаты | касса | daily inbox, лимит pending | P0 |
| MemoryStorage | рестарт | Redis/DB | P0 |
| Реферал 25% | маржа | P_c с запасом | P1 |
| Секрет прокси в git | rules.py | вынести, ротировать | P1 |
| master ≠ patch-15 | две линии | docs по patch-15 | P1 |

## Site + Sales scripts summary

| Что | Одна строка | CTA / цель |
|---|---|---|
| Герой сайта | Присутствие на картах. Прозрачный процесс. | Оставить заявку |
| Исполнители на сайте | Правила и вывод, без лёгких денег | Открыть бота |
| Скрипт 1 холод | Карточка видна → бриф 4 вопроса | «бриф» |
| Скрипт 5 дорого | Цена за принятую единицу | посчитать |
| Скрипт 6 доверие | Платим после модерации | показать процесс |
| Скрипт 8 срочный объём | Не берём | отказ-качество |
| Скрипт 9 close | 14 дней, N принятых, P | фиксация |
| Тест нед.1 | 15 касаний одного города | ≥1 бриф |

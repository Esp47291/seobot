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
| F1 Activation | start→rules→view→take→submit (окно 7д) | submit_7d / start(new) | SQL take/submit; view/start — events |
| F2 Money | submit→pass→credited→wd_paid | pass%; paid-out%; t-pay | attempts.balance_credited + WD |
| F3 Retention | supply vs demand; unbounded D7 | took_within_7d | SQL proxy; N-day только онбординг |
| F4 Referral | join→qualified→reward | qualified/join; SUM ref / SUM reward | не COUNT из админки |
| F5 B2B | lead→qualify→live task | take/lead; live/take | нет сущности; no_take не в знаменатель live |

## 30-day plan

| Неделя | Продукт | Продажи | Контент | Метрики |
|---|---|---|---|---|
| 1 | роли /start, ТЗ на карточке, SLA-текст | 15 outbound | 3 поста правил | new, take, submit, pass%, WD pending |
| 2 | статус вывода; лог 3 событий | FU + 10 + созвон | Tilda по LANDING_BRIEF (1 CTA) | t-moderation p50 |
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
| Герой `/` | Присутствие на картах. Прозрачный процесс. | Только «Оставить заявку» |
| CTA2 в герое | нет (H3: бот уводит B2B) | бот — `/executors` + футер |
| Trust-чипы | Ручная модерация · гео рядом · оплата за принятое | без фейковых N |
| Форма | Имя, город, Telegram (+ чипы площадок) | `biz_lead` |
| Закрытие заявки | менеджер → TaskItem, кабинета нет | не self-serve |
| Исполнители | Правила и вывод, без лёгких денег | Открыть бота |
| Скрипт 1 холод | Карточка, без URL, 1 вопрос | «бриф» |
| Скрипт 13 inbound | `#lead`: не дублировать форму | Q1 точка + Q3 ожидание |
| Скрипт 14 накрутка | ToS: не продаём отзыв как товар | процесс или отказ |
| Скрипт 15 шаблон | Prebuilt не слать клиенту | отказ текста |
| Скрипт 16 no-take | После серого Q3 | без счёта |
| Скрипт 8 срочный объём | Не берём квоту | отказ-качество |
| Скрипт 9 close | 14 дней, N принятых, P | фиксация |
| Qualifier | берём = визит+проверка+темп | иначе 16 |
| Тест нед.1 | 15 касаний одного города | ≥1 бриф, 0 ссылок в 1-м DM |

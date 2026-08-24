# Job Inside — карта возможностей бота

Аудит: 2026-08-24 00:23 UTC, дописки H2–H6.  
Два снимка кода: `origin/master` (эта рабочая копия) и `origin/patch-15` (продукт-of-record: роли, баланс, рефералка, scheduler, аналитика).  
Сайта нет ни на одной ветке.

## Источник правды

| Ветка | Что это | Файлов | Использовать как |
|---|---|---|---|
| `master` / эта копия | Базовый aiogram-бот: обучение → задание → скрин → реквизиты на каждое задание → админ «оплачено» | 25 | Устаревший каркас. Не описывать как прод. |
| `patch-15` | Job Inside: задания TaskItem, попытки Attempt, менеджер, баланс, вывод, рефералка 20/5, broadcast, scheduler, CSV | 39 | **Продукт-of-record** для UX, аналитики, продаж |
| Сайт | отсутствует в репо | 0 | Gap. Бриф в `docs/website/` |

## Зоны (patch-15 = факт, master = отставание)

| Зона | Master | patch-15 | Риск | Комментарий |
|---|---|---|---|---|
| Выплаты / баланс / вывод | Нет баланса. Реквизиты на каждое задание. Админ жмёт «Выплачено» на Task | Есть `balance`, `WithdrawalRequest`, кабинет, мин. вывод (default 20, `BotSetting.min_withdraw_amount`). Выплаты ручные | **P0 опер.** Ручной контур не масштабируется; нет SLA «деньги уйдут до…» | Код: `handlers/user.py` withdraw_*, `services/task_payout.py` |
| Рефералка | Нет | Deep-link `/start <user_id>` только при **первом** создании юзера. L1 = 20% от цены задания, L2 = 5% | **P1 юнит.** 25% поверх выплаты исполнителю при полной цепочке — закладывать в цену заказчику. Нет события `referral_join` в аналитике | `Referral`, `grant_task_completion_rewards` |
| Модерация admin/manager | Только admin: pending → approved → paid / rejected | Двухступенчато: аккаунт/логин → отзыв. Статусы Attempt: `waiting_approval` → `login_screenshot` → `approved` → `review_submitted` → `completed` / `rejected` / `declined` / `canceled`. Есть очередь second-account | **P1 UX.** Исполнитель не видит очередь/SLA. Причины отказа есть в модели, но не всегда в человеческом тексте | `handlers/admin.py`, `handlers/manager.py` |
| Broadcast / scheduler | Нет (в админке master кнопка «написать одному») | Админ: массовая + личная. Менеджер: личная. Scheduler: напоминание админу о проверке отзыва; напоминание исполнителю «можно снова» | **P1.** MemoryStorage + рестарт = потеря FSM рассылки. Нет `broadcast_click` | `services/review_scheduler.py`, `executor_repeat_reminder.py` |
| FSM / storage | `MemoryStorage()` | То же `MemoryStorage()` | **P0 тех.** Рестарт/деплой рвёт: скрин, вывод, мастер создания задания | `main.py` обеих веток |
| Подписка на канал | Нет | Gate перед заданиями: кнопка на `t.me/Jobinsidenews`, флаг `news_accepted=True` **без** `getChatMember` | **P2 доверие.** Самоподтверждение. Комментарий в модели честный: «не реальная проверка» | `handlers/user.py` ~345 |
| Аналитика / CSV / метрики | `AdminAction` лог approve/reject/paid | Хаб: lifetime totals, очереди без возраста, CSV **только completed** + WD, `/status`, статистика заданий. `referral_payout_ops_total` = COUNT не ₽ | **P1.** Нет event-stream. F1 (view/start) не восстановить SQL. Флаги rules/news без timestamp | `handlers/admin_analytics.py`, `StatsRepository` |
| Онбординг / тексты / клавиатуры | 4 шага TrainingMessage + «Взять задание» | Welcome из `BotSetting`, правила (middleware), reply-меню 5 кнопок, карточка задания без инструкции до «Начать» | **P0 UX.** `/start` не сегментирует исполнитель/заказчик. Правила смешивают оффер, рефералку и промо прокси | см. `BOT_UX_VISION.md` |
| Роли | admin / user | user / admin (`ADMIN_IDS`) / manager (`MANAGER_IDS`) + block | Ок | Middlewares: admin, manager, blocked, rules, staff |
| Площадки | yandex, 2gis + кулдауны 24ч / 2ч | Платформа — свободная строка; мин. цены default: Яндекс 130 / Google 35 / 2ГИС 12 | ASSUMPTION: это дефолты кода, не факт продаж | `BotSetting` |
| Docker | Нет в master | `Dockerfile` + `docker-compose.yml`, volume `./data`, extra_hosts Telegram | Ок для VPS | Нет healthcheck, нет Redis/Postgres в compose |
| Сайт | Нет | Нет | **P1 рост.** Нечем закрывать B2B | `docs/website/` |

## Пайплайн задания (patch-15) — как есть

```
/start → welcome + меню
  → (rules accept, если не приняты)
  → «Приступить» → (news self-confirm) → город заведения → платформа
  → карточка (платформа / город / сфера / цена)
  → Начать | Следующее | Не интересно
  → скрин аккаунта/логина → модерация → approved
  → скрин отзыва (реквизиты из профиля) → review_submitted
  → completed (+ баланс + реф. 20/5) | rejected
  → вывод заявкой → ручная выплата admin/manager
```

Master-пайплайн короче и другой: обучение → рандом ссылка+текст → скрин → реквизиты в задании → approve → paid. Не мержить в одну схему.

## Чего нет (оба снимка)

- Сайт / лендинг / кабинет заказчика вне Telegram
- Event-аналитика шагов (start, task_take, proof_submit…)
- Персистентный FSM (Redis/DB)
- Реальная проверка подписки
- Видимый исполнителю SLA модерации и «где мои деньги»
- Автовыплаты
- Разделение бренда: «качественная локальная работа» vs ощущение накрутки (копирайт правил сейчас про «платим ВАМ за отзывы»)

## Tech audit — короткие issue-style (код не трогаем ночью)

1. **P0** `MemoryStorage` → Redis/DB storage. Симптом: пользователь в `waiting_review_screenshot` после рестарта получает «не то состояние».
2. **P1** Хардкод промо прокси в `middlewares/rules.py` (URL+secret в исходнике). Вынести в settings; секрет не светить в правилах и git.
3. **P1** Нет единого event-лога. CSV — выгрузка сущностей, не воронка.
4. **P2** `news_accepted` переименовать или сделать честную проверку; в копирайте не обещать «подписка проверена».
5. **P2** Две кодовые линии (master vs patch-15) без docs в репо. Ночной штаб документирует **patch-15**.

## MIRO-READY

| Зона | Статус patch-15 | Главный риск | Следующий шаг |
|---|---|---|---|
| Выплаты/вывод | Есть, ручные | Очередь без SLA | Показать статус заявки + срок в кабинете |
| Рефералка | L1 20% / L2 5% | Съедает маржу | Заложить 25% в оффер заказчику |
| Модерация | Две ступени + second-acc | Тишина после сдачи | Статус + ETA |
| Broadcast/scheduler | Есть | FSM в памяти | Redis; не слать >1–2 unprompted/сутки |
| Подписка на канал | Самоклик | Ложная уверенность | Честный copy или getChatMember |
| Аналитика | CSV + хаб | Нет шагов юзера | EVENT_TAXONOMY в код |
| Онбординг | Welcome + rules dump | Нет сегментации | /start: «Хочу задания» / «Я бизнес» |
| Сайт | Нет | Нет B2B входа | LANDING_BRIEF |

## Инкремент аудита 2026-08-24 H6 (~04:51 UTC)

- `origin/patch-15` HEAD всё ещё `a768bf3`. Зоны выплат / рефералка / FSM / channel gate / CSV / сайт без изменения кода.
- B2B-входа в боте нет: нельзя слать холод через broadcast. Лид = Telegram руками → `TaskItem`. Город спроса для outbound — `task_items.venue_city` на проде; в репо списка нет.
- Рефералка и канал — supply. Код бота не меняли.

## Инкремент аудита 2026-08-24 H5 (~03:49 UTC)

- `origin/patch-15` HEAD всё ещё `a768bf3`. Зоны выплат / рефералка / FSM / сайт без изменения кода.
- Деньги: `TaskItem.price` = P_ex (floor default 130/35/12). Сущности счёта/P_c нет. Реферал 20%+5% в `grant_task_completion_rewards` после админ-`review_ok` или `mgr_outpay`.
- Касса: WD ручной; `completed` ≠ credited на менеджерских слотах. Это не take-rate GMV.
- Сайта нет. Код бота не меняли.

## Инкремент аудита 2026-08-24 H4 (~02:51 UTC)

- `origin/patch-15` HEAD всё ещё `a768bf3`. Зоны выплат / модерация / FSM / channel gate / CSV без изменения кода.
- B2B: сущности заявки нет. Менеджер: `mgr:tasks_add` → платформа (Яндекс/2ГИС/Google/другое) → цена ≥ floor → `TaskItem`. Prebuilt тексты остаются внутренним FSM admin/manager — в продажи клиенту не тащить (скрипт 15).
- Сайта нет; inbound `#lead` пока бумажный (WEB-02). Код бота не меняли.

## Как обновлять этот файл

Каждый hourly run: 5–10 строк «что изменилось в коде / что осталось». Не переписывать таблицу с нуля, если зоны те же.

## Инкремент аудита 2026-08-24 H3 (~01:49 UTC)

- `origin/patch-15` HEAD `a768bf3`: cloud environment, на продукт бота не влияет. Предыдущий продуктный коммит в зоне сайта: «последние отзывы в профиле» (исполнитель) + prebuilt тексты/фото у admin/manager.
- Prebuilt **не выносить на лендинг** как «готовые отзывы» — ToS/репутация. Сайт продаёт процесс и проверку, не SKU «отзыв».
- Сайта нет. B2B после заявки = человек создаёт `TaskItem`. Исполнитель = бот. Кабинета заказчика нет — не обещать в IA.
- Зоны P0 без изменения кода: MemoryStorage, ручные WD, channel self-click, `/start` без роли.
- Код бота не меняли.

## Инкремент аудита 2026-08-24 H2

- `patch-15` сдвинулся: `chore: add Cursor cloud environment` — на продукт бота не влияет.
- Аналитика прочитана целиком (`admin_analytics.py` 507 строк + `StatsRepository`): daily-воронки нет, есть касса WD pending и хаб модерации (admission / reviews / secacc / WD).
- Критичный факт для денег: менеджерский `completed` ≠ `balance_credited`. Реферал 20/5 в `grant_task_completion_rewards` — после `review_ok` (админ) или `mgr_outpay`.
- `/menu` = welcome без реферала и без нового user-create path на deep-link.
- Код бота не меняли. Карта вставок событий: `docs/analytics/EVENT_TAXONOMY.md`.

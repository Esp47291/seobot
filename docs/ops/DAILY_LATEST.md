# Job Inside Daily

Дата: 2026-08-24 ~00:53 UTC. Run: H2 Analytics events. Ветка: `docs/night-ops-20260824-00`.

### Недавно сделано (по коммитам/докам)

Код (origin/patch-15): cloud environment commit, продукт бота без новой фичи.  
Docs H1: UX + каркас Business OS.  
Docs H2: карта «хендлер → emit», окна воронок, SQL-прокси, ловушка completed≠credited.

### Риски

- Продукт-of-record = **patch-15**, docs-ветка растёт от **master**.
- `MemoryStorage` — потеря FSM.
- Ручные выводы без SLA; менеджерский `completed` без `balance_credited` — касса и доверие.
- Админ-цифра рефералки = COUNT операций, легко принять за ₽.
- Copy правил / прокси-секрет в git (не копировать в docs).
- Сайта нет.

### Топ-5 задач на сейчас (P0/P1/P2)

1. **P0** /start: две роли + человеческие правила без секрета в тексте  
2. **P0** Карточка задания: инструкция и доказательство до «Начать»  
3. **P0** После сдачи: статус + честный срок; на менеджерском слоте не писать «оплачен» до credited  
4. **P0** Persist FSM (Redis/DB) — issue, не ночной рефакторинг  
5. **P1** Днём: 3 structured-лога `start` / `task_take` / `proof_submit` по карте в EVENT_TAXONOMY (AN-01). Спека готова.

Снято с топ-5 как «следующий час штаба»: писать taxonomy с нуля. Осталось внедрение в код — дневной маленький PR.

### Одна рекомендация владельцу (1 предложение)

Снимите с прод-SQLite четыре SQL из FUNNELS (take→submit 7д, pass%, очередь >24ч, SUM ref/payout) — без этого нельзя ни обещать SLA, ни ставить цену пилота.

### Что сделано ЭТИМ run (инкремент)

- Прочитаны `admin_analytics.py`, `StatsRepository`, точки user/admin/manager/payout.  
- EVENT_TAXONOMY: фазы 0–2, таблица вставок, PII, ловушка mgr_outpay.  
- FUNNELS: окна 7/14д, supply≠demand, SQL-прокси.  
- DASHBOARD: какие виджеты уже есть и какие врут.  
- Код бота не менялся.

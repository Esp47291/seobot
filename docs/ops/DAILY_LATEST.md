# Job Inside Daily

Дата: 2026-08-24 ~06:52 UTC. Run: H8 Risks&ops. Ветка: `docs/night-ops-20260824-00`.

### Недавно сделано (по коммитам/докам)

Код (origin/patch-15 `a768bf3`): без новой фичи.  
Docs H1–H7: UX, аналитика, лендинг, скрипты, CM1, 15 касаний, copy C-01…C-16.  
Docs H8: daily inbox 5 полос (хаб ≠ очередь), severity S0–S5, playbook инцидентов I1–I4.

### Риски

- Продукт-of-record = **patch-15**, docs-ветка от **master**.
- `MemoryStorage`; ручные WD; `completed` ≠ `credited` у менеджера.
- Хаб `admission` без `login_screenshot`; очереди `id DESC`; Q5 unpaid нет в хабе.
- Prebuilt в `admin:allow` = диктовка (Maps UGC / апр. 2026).
- Секрет прокси в git (`rules.py`) — не копировать в доки; ротация днём.
- Сайта нет; `#lead` некуда принимать (WEB-02).
- PR ночи не открыт (gh write нет).

### Топ-5 задач на сейчас (P0/P1/P2)

1. **P0** OPS-01 Inbox сегодня: SQL Q1–Q5 + не allow с prebuilt (`DAILY_INBOX.md`)  
2. **P0** UX-01 /start: две роли (текст H7 готов)  
3. **P0** UX-02 Карточка: инструкция до «Начать»  
4. **P0** UX-03 После сдачи: id + рабочие часы; ETA из S2, не «5 минут»  
5. **P0** TECH-01 Persist FSM — до фикса: deploy freeze при живой очереди  

Снято с топ-5: SALES-01 остаётся **field** (15 касаний), не блокирует утро ops. COPY-01 spec-ready. UNIT-01 / WEB-01 ждут поле/вёрстку.

### Одна рекомендация владельцу (1 предложение)

Завтра утром не создавайте слоты, пока не прогоните inbox: aged отзывы, WD pending ₽, mgr unpaid — и не подтверждайте допуск на заданиях с готовым текстом отзыва.

### Что сделано ЭТИМ run (инкремент)

- Research: очереди≠цифры, SLA по severity, Maps UGC incentive+диктовка.  
- `DAILY_INBOX.md`: 5 полос, ритуал 8 шагов, SQL, кассовый шлюз.  
- RISKS: playbook I1–I4, хаб-дыры; TABLES 9b.  
- Код бота не менялся.

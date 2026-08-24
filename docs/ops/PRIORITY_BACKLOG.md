# Priority backlog

Очередь двигается каждый run. Не повторять один и тот же топ-5 без прогресса.

## Сейчас (после 2026-08-24 H2)

| ID | Задача | P | Статус | Зачем |
|---|---|---|---|---|
| UX-01 | /start: исполнитель vs бизнес | P0 | todo | 10 секунд понимания |
| UX-02 | Инструкция/чеклист на карточке до take | P0 | todo | меньше слепых сдач |
| UX-03 | Текст после скрина: статус + честный ETA; не «оплачен» до credited | P0 | todo | удержание + честные деньги |
| TECH-01 | FSM не в MemoryStorage | P0 | todo | деплой не убивает сдачу |
| OPS-01 | Daily inbox: очередь модерации + WD pending + aged>24ч | P0 | todo | касса и SLA; SQL уже в FUNNELS |
| COPY-01 | Правила без прокси-секрета и «накруточного» тона | P0 | todo | репутация + секрет в git |
| AN-01 | 3 лога start/task_take/proof_submit | P1 | spec-ready | карта в EVENT_TAXONOMY; код — дневной PR |
| WEB-01 | Лендинг по LANDING_BRIEF | P1 | next-hour | B2B вход |
| UX-05 | Статус заявки на вывод в кабинете | P1 | queued | доверие к деньгам |
| SALES-01 | 15 касаний ICP «локальная услуга» | P1 | queued | проверка оффера |
| UNIT-01 | Заполнить P_c и C_ops фактом | P1 | queued | не продавать в минус |
| AN-02 | Таблица analytics_events + остальные 9 событий | P1 | queued | после недели Phase 1 |
| AN-03 | Daily-срезы в admin stats (не lifetime) | P1 | queued | DASHBOARD_SPEC SQL |
| UX-06 | Пустое состояние «напомнить по городу» | P2 | later | |
| REF-01 | Счётчик qualified рефералов | P2 | later | |
| CH-01 | Честный channel gate | P2 | later | |

## Сделано этим штабом (доки, не код)

- Карта возможностей master vs patch-15
- UX vision + journeys + gaps + copy
- Каркас analytics / website / business / sales / miro
- H2: instrumentation map, окна воронок, SQL-прокси, ловушка credited

## Ротация часов

H1 Product/UX  
H2 Analytics events ← **этот run**  
H3 Website landing ← **следующий**  
H4 Sales scripts  
H5 Unit economics  
H6 Acquisition  
H7 Copy system  
H8 Risks&ops  

Углублять, не переписывать скелет.

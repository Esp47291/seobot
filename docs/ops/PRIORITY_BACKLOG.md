# Priority backlog

Очередь двигается каждый run. Не повторять один и тот же топ-5 без прогресса.

## Сейчас (после 2026-08-24 H4)

| ID | Задача | P | Статус | Зачем |
|---|---|---|---|---|
| UX-01 | /start: исполнитель vs бизнес | P0 | todo | 10 секунд понимания |
| UX-02 | Инструкция/чеклист на карточке до take | P0 | todo | меньше слепых сдач |
| UX-03 | Текст после скрина: статус + честный ETA; не «оплачен» до credited | P0 | todo | удержание + честные деньги |
| TECH-01 | FSM не в MemoryStorage | P0 | todo | деплой не убивает сдачу |
| OPS-01 | Daily inbox: очередь модерации + WD pending + aged>24ч | P0 | todo | касса и SLA; SQL уже в FUNNELS |
| COPY-01 | Правила без прокси-секрета и «накруточного» тона | P0 | todo | репутация + секрет в git |
| SALES-01 | 15 касаний ICP «локальная услуга» по скрипту 1 | P1 | next-hour field | проверка оффера; спека скриптов готова |
| WEB-01 | Собрать `/` по LANDING_BRIEF (Tilda ок) | P1 | spec-ready | герой+форма+IA готовы; вёрстка — день |
| AN-01 | 3 лога start/task_take/proof_submit | P1 | spec-ready | карта в EVENT_TAXONOMY; код — дневной PR |
| UX-05 | Статус заявки на вывод в кабинете | P1 | queued | доверие к деньгам |
| UNIT-01 | Заполнить P_c и C_ops фактом | P1 | queued | не продавать в минус; не называть ₽ в скрипте 9 |
| AN-02 | Таблица analytics_events + остальные 9 событий | P1 | queued | после недели Phase 1 |
| AN-03 | Daily-срезы в admin stats (не lifetime) | P1 | queued | DASHBOARD_SPEC SQL |
| WEB-02 | Домен + UTM + приём `biz_lead` в таблицу/менеджеру | P1 | queued | иначе форма и скрипт 13 в никуда |
| UX-06 | Пустое состояние «напомнить по городу» | P2 | later | |
| REF-01 | Счётчик qualified рефералов | P2 | later | |
| CH-01 | Честный channel gate | P2 | later | |

## Сделано этим штабом (доки, не код)

- Карта возможностей master vs patch-15
- UX vision + journeys + gaps + copy
- Каркас analytics / website / business / sales / miro
- H2: instrumentation map, окна воронок, SQL-прокси, ловушка credited
- H3: лендинг 1 CTA, форма 3 поля, IA без кабинета
- H4: бриф ↔ `#lead`, qualifiers, inbound, stuffing, no canned text

## Ротация часов

H1 Product/UX  
H2 Analytics events  
H3 Website landing  
H4 Sales scripts ← **этот run**  
H5 Unit economics ← **следующий**  
H6 Acquisition  
H7 Copy system  
H8 Risks&ops  

Углублять, не переписывать скелет. H5: не выдумывать P_c в ₽; связать «не берём» с маржой (серый объём ≠ дешёвый пилот).

# Priority backlog

Очередь двигается каждый run. Не повторять один и тот же топ-5 без прогресса.

## Сейчас (после 2026-08-24 H1 круг 2)

| ID | Задача | P | Статус | Зачем |
|---|---|---|---|---|
| OPS-01 | Daily inbox: 5 полос + aged + WD ₽ + Q5 | P0 | **spec-ready** — ритуал руками; хаб днём | касса и SLA; SQL в DAILY_INBOX |
| UX-01 | /start: исполнитель vs бизнес | P0 | todo — тексты H7 готовы | 10 секунд понимания |
| UX-02 | Инструкция/чеклист на карточке до take | P0 | todo — + строка ETA с карточки | меньше слепых сдач; ожидание не засада |
| TECH-01 | FSM не в MemoryStorage | P0 | todo — до фикса deploy freeze | деплой не убивает сдачу |
| COPY-01 | Правила без прокси-секрета; реф без пассава; стоп prebuilt исполнителю | P0 | **spec-ready** | репутация + ToS; секрет не в docs |
| UX-03 | Текст после скрина: id + стадия + рабочие часы | P0 | **spec-ready** — BOT_UX_VISION; дневной PR C-04 | удержание в submit→pass; хаб не обещать |
| SALES-01 | 15 касаний ICP «локальная услуга» по скрипту 1 | P1 | **field** — протокол в ACQUISITION | проверка оффера; no_take не проигрыш |
| UNIT-01 | Заполнить P_c и C_ops фактом с первого take-договора | P1 | spec-ready | ждёт take + договор; ₽ в скрипте 9 запрещены |
| WEB-01 | Собрать `/` по LANDING_BRIEF (Tilda ок) | P1 | spec-ready | герой+форма+IA готовы; вёрстка — день |
| AN-01 | 3 лога start/task_take/proof_submit | P1 | spec-ready | карта в EVENT_TAXONOMY; код — дневной PR |
| UX-05 | Статус заявки на вывод в кабинете | P1 | queued | доверие к деньгам; не смешивать с UX-03 |
| AN-02 | Таблица analytics_events + остальные 9 событий | P1 | queued | после недели Phase 1 |
| AN-03 | Daily-срезы в admin stats (не lifetime) | P1 | queued | DASHBOARD_SPEC + хаб Q1/Q5 |
| WEB-02 | Домен + UTM + приём `biz_lead` в таблицу/менеджеру | P1 | queued | иначе форма и скрипт 13 в никуда |
| UX-06 | Пустое состояние «напомнить по городу» | P2 | later — текст H7 есть | |
| REF-01 | Счётчик qualified рефералов | P2 | later | |
| CH-01 | Честный channel gate | P2 | later — честный copy C-11 | |

## Сделано этим штабом (доки, не код)

- Карта возможностей master vs patch-15
- UX vision + journeys + gaps + copy
- Каркас analytics / website / business / sales / miro
- H2: instrumentation map, окна воронок, SQL-прокси, ловушка credited
- H3: лендинг 1 CTA, форма 3 поля, IA без кабинета
- H4: бриф ↔ `#lead`, qualifiers, inbound, stuffing, no canned text клиенту
- H5: CM1 vs take-rate; no_take ≠ маржа; полы ≠ SKU; WD нефондирован без P_c
- H6: протокол 15, supply-first город, трекер исходов, партнёр ≠ ranking SKU
- H7: инвентарь C-01…C-16; RULES без секрета; стоп диктовки исполнителю; тон канала = скрипт 1
- H8: inbox 5 полос; хаб admission врёт; Q5 нет в хабе; severity; инциденты I1–I4
- H1 круг 2: UX-03 spec — 6 полей ожидания; запрет N-го и минут; S2/S3 не путать в ЛС

## Ротация часов

H1 Product/UX ← **этот run** (круг 2)  
H2 Analytics events  
H3 Website landing  
H4 Sales scripts  
H5 Unit economics  
H6 Acquisition  
H7 Copy system  
H8 Risks&ops  

Следующий: **H2 Analytics**. Не переписывать taxonomy с нуля. Углубить: окно ожидания submit→pass / `t_mod`, не выдумывать %. Не копировать секрет из rules.py.

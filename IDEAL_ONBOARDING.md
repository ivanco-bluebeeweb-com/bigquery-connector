# Google BigQuery Connector — идеальный первый запуск

Источник: `ONBOARDING_FIRST_LAUNCH_STANDARD.md`. Целевой пользователь: data
engineer/analyst, администрирующий собственный GCP-проект с BigQuery.

## 1. Credential type
GCP Service Account JSON key (тот же паттерн, что GCP Connector) — содержит
project_id, client_email, private_key. BYOK, без посредничества Imperal.

## 2. Идеальный флоу
1. **Первое открытие** — `Empty` со ссылкой "IAM & Admin > Service Accounts >
   Keys > Add Key > JSON" и объяснением, что нужен файл целиком (весь JSON),
   а не отдельные поля — частая ошибка — пользователи вставляют только
   private_key без остальных полей.
2. **Форма** — единственное поле service_account_json (Password/TextArea,
   placeholder "Вставьте содержимое JSON-файла целиком"), после парсинга
   project_id читается автоматически из JSON.
3. **После успеха** — сразу `audit_datasets` — сколько datasets без TTL на
   таблицах (утечка storage costs), самые дорогие запросы за 24ч по
   `INFORMATION_SCHEMA.JOBS`, наличие партиционирования на больших таблицах —
   actionable с первой секунды, а не пустой дашборд.
4. **Datasets-first UX** — центр экрана сразу показывает список datasets с
   их location и default table expiration, т.к. самый частый вопрос
   ("где лежат мои данные и сколько это стоит?").
5. **Ошибка "invalid key format"** — если JSON не парсится или не содержит
   `private_key`/`client_email` — конкретное сообщение "Похоже, это не полный
   Service Account JSON — нужен весь файл ключа, скачанный из IAM & Admin",
   а не общее "не удалось подключиться".
6. **Ошибка "insufficient permissions"** — 403 PERMISSION_DENIED от BigQuery
   API — сообщение "У сервисного аккаунта нет роли BigQuery Data Viewer/Job
   User — назначьте роль в IAM и повторите подключение", ссылка на
   IAM-страницу проекта.
7. **Query-first workflow** — рядом с датасетами кнопка "Выполнить запрос"
   ведёт к простому SQL-редактору (Input многострочный) + результат в
   DataTable, т.к. BigQuery в первую очередь используется для ad-hoc SQL.

## 3. Особые состояния
- Job ещё выполняется (async query) — Badge "Running" + кнопка "Обновить
  статус", не блокирующий спиннер на весь экран.
- Query превысила dry-run bytes billed estimate — предупреждение с оценкой
  стоимости ДО выполнения (BigQuery оплачивается по объёму просканированных
  данных) — критично для доверия пользователя.

# Google BigQuery Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`.
Основано на `IDEAL_ONBOARDING.md` этого приложения.

## 0. Разница с идеалом
Идеал предлагает dry-run bytes estimate до выполнения запроса и live-статус
job — сегодняшние примитивы не поддерживают inline preview стоимости.
Компромисс: `execute_sql` сам делает dry_run=true первым шагом и возвращает
оценку в ответе перед фактическим запуском; live-статус job заменён
кнопкой "Обновить статус" рядом со списком jobs.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Stack`(align="start") + project label + `ui.Divider` + navigation `ui.ListItem`(Datasets/Tables/Jobs & Queries/Scheduled Queries) + `ui.Button`("App settings") | Без карточек по стандарту, один "App settings" в самом низу. |
| Connect form (sidebar, до подключения) | `ui.Form`(full_width, action="connect_bigquery") с `_field()`-обёрнутым `ui.Password`(label="Service Account JSON", placeholder="Вставьте содержимое JSON-файла целиком") | Контейнер растянут на всю ширину сайдбара (`align="stretch"`), лейбл + контекстный плейсхолдер. Нет дублирующих инструкций — walkthrough только в App settings. |
| Datasets (center, `center_overlay=True`) | `ui.DataTable`(dataset_id, location, default_table_expiration, table_count) + row action `ui.Button`("Открыть таблицы") | `DataTable` — табличный список объектов, стандартный паттерн категории. |
| Tables (center) | `ui.DataTable`(table_id, num_rows, num_bytes, partitioning Badge) + row actions (`ui.Button`("Просмотр схемы"/"Удалить")) | Badge — визуальный статус партиционирования (частая причина высоких costs). |
| Jobs & Queries (center) | `ui.DataTable`(job_id, query preview, state Badge, bytes_processed, created) + `ui.Button`("Обновить") + форма для нового запроса (`ui.Form` с `ui.Input`(label="SQL-запрос", placeholder="SELECT * FROM `project.dataset.table` LIMIT 100")) | Query-first workflow, как в идеале. |
| Scheduled Queries (center) | `ui.DataTable`(display_name, schedule, next_run_time, state Badge) + row action `ui.Button`("Запустить сейчас") | Тот же паттерн, что list_saved_searches у Splunk. |
| App settings (center, отдельная панель) | `ui.Stack` с заголовком "Connections" + список подключений + `ui.Button`("Disconnect", variant="danger") на каждый | Disconnect только здесь, не в сайдбаре — сайдбар без дублирующих инструкций. |

## 2. Первый экран без подключения
`ui.Empty`(message="Подключите ваш GCP-проект с BigQuery, чтобы управлять
датасетами, таблицами и запросами.", icon="bigquery") прямо над формой
подключения — без блока текста-инструкции (эта информация только в
IDEAL_ONBOARDING.md / App settings, не дублируется в сайдбаре).

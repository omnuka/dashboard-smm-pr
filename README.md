# Serenity Infopole Dashboard

Демо-версия дашборда мониторинга конкурентного инфополя для Serenity.

Сейчас внутри лежат выдуманные демо-данные в `data/weekly_findings.json`.
Позже этот файл заменим на реальные еженедельные выгрузки: кейсы, посты, СМИ, SEO и реакции.

## Файлы

- `index.html` - страница дашборда
- `styles.css` - дизайн
- `app.js` - логика фильтров и таблиц
- `data/competitors.json` - база конкурентов
- `data/sources.json` - источники мониторинга
- `data/weekly_findings.json` - текущие находки, сейчас демо
- `data/weekly_findings.demo.json` - копия демо-данных
- `data/seo_snapshot.template.csv` - шаблон SEO-выгрузки

## Публикация

Загрузить файлы в отдельный GitHub-репозиторий и включить GitHub Pages из ветки `main`, папка `/root`.

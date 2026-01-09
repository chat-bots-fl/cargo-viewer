# Качество кода (Code Quality)

Документация по использованию линтеров и форматтеров в проекте cargo-viewer.

## Содержание

- [Обзор инструментов](#обзор-инструментов)
- [Установка](#установка)
- [Использование](#использование)
- [Настройка IDE](#настройка-ide)
- [Pre-commit hooks](#pre-commit-hooks)
- [CI/CD интеграция](#cicd-интеграция)
- [Troubleshooting](#troubleshooting)

---

## Обзор инструментов

Проект использует следующие инструменты для обеспечения качества кода:

| Инструмент | Назначение | Конфигурация |
|-----------|-----------|--------------|
| **Black** | Форматирование кода | [`.black`](../.black) |
| **isort** | Сортировка импортов | [`.isort`](../.isort) |
| **flake8** | Линтинг кода | [`.flake8`](../.flake8) |
| **mypy** | Статическая типизация | [`mypy.ini`](../mypy.ini) |
| **pre-commit** | Автоматические проверки | [`.pre-commit-config.yaml`](../.pre-commit-config.yaml) |

### Black

**Black** - это "неоспоримый" форматтер кода для Python. Он автоматически форматирует код в соответствии с PEP 8.

- **Line length:** 100 символов
- **Target version:** Python 3.11
- **Исключаемые директории:** migrations, venv, node_modules и др.

### isort

**isort** - утилита для сортировки импортов в Python файлах.

- **Profile:** black (совместимость с Black)
- **Line length:** 100 символов
- **Sections:** FUTURE, STDLIB, DJANGO, THIRDPARTY, FIRSTPARTY, LOCALFOLDER

### flake8

**flake8** - инструмент для проверки кода на соответствие PEP 8 и выявления ошибок.

- **Max line length:** 100 символов
- **Игнорируемые ошибки:** E203, W503, E501, C901
- **Max complexity:** 10

### mypy

**mypy** - статический типизатор для Python.

- **Python version:** 3.11
- **Strict mode:** включен
- **Django plugin:** включен

---

## Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Или используя Makefile:

```bash
make install
```

### 2. Установка pre-commit hooks

```bash
make pre-commit-install
```

Или напрямую:

```bash
pre-commit install
```

---

## Использование

### Форматирование кода

Форматирование всех файлов проекта:

```bash
make format
```

Или по отдельности:

```bash
# Форматирование с Black
black --config .black .

# Сортировка импортов
isort --settings-path .isort .
```

### Линтинг кода

Запуск всех линтеров:

```bash
make lint
```

Или по отдельности:

```bash
# Flake8
flake8 --config .flake8 .

# mypy
mypy --config-file mypy.ini .
```

### Полная проверка

Форматирование + линтинг:

```bash
make check
```

### Запуск тестов

```bash
make test
```

### Все проверки

Форматирование + линтинг + тесты:

```bash
make all
```

### Очистка кэша

```bash
make clean
```

---

## Настройка IDE

### VS Code

Установите следующие расширения:

1. **Black Formatter** - `ms-python.black-formatter`
2. **isort** - `ms-python.isort`
3. **Flake8** - `ms-python.flake8`
4. **Mypy** - `matangover.mypy`
5. **EditorConfig** - `EditorConfig.EditorConfig`

Добавьте в `.vscode/settings.json`:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "ms-python.black-formatter",
  "editor.codeActionsOnSave": {
    "source.organizeImports": "explicit"
  },
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.blackArgs": ["--config", ".black"],
  "python.linting.flake8Args": ["--config", ".flake8"],
  "python.linting.mypyArgs": ["--config-file", "mypy.ini"],
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

### PyCharm

1. **Настройка Black:**
   - Settings → Tools → External Tools
   - Добавить новый инструмент:
     - Name: Black
     - Program: `$ProjectFileDir$/venv/Scripts/black.exe` (или путь к black)
     - Arguments: `--config .black $FilePath$`
     - Working directory: `$ProjectFileDir$`

2. **Настройка isort:**
   - Settings → Tools → External Tools
   - Добавить новый инструмент:
     - Name: isort
     - Program: `$ProjectFileDir$/venv/Scripts/isort.exe` (или путь к isort)
     - Arguments: `--settings-path .isort $FilePath$`
     - Working directory: `$ProjectFileDir$`

3. **Настройка Flake8:**
   - Settings → Tools → External Tools
   - Добавить новый инструмент:
     - Name: Flake8
     - Program: `$ProjectFileDir$/venv/Scripts/flake8.exe` (или путь к flake8)
     - Arguments: `--config .flake8 $FilePath$`
     - Working directory: `$ProjectFileDir$`

4. **Настройка mypy:**
   - Settings → Tools → External Tools
   - Добавить новый инструмент:
     - Name: mypy
     - Program: `$ProjectFileDir$/venv/Scripts/mypy.exe` (или путь к mypy)
     - Arguments: `--config-file mypy.ini $FilePath$`
     - Working directory: `$ProjectFileDir$`

5. **Настройка EditorConfig:**
   - Settings → Editor → Code Style → EditorConfig
   - Поставить галочку "Enable EditorConfig support"

### Vim/Neovim

Добавьте в `.vimrc` или `init.vim`:

```vim
" Black
autocmd BufWritePre *.py execute ':Black'

" isort
autocmd BufWritePre *.py execute ':Isort'

" Flake8
autocmd BufWritePost *.py execute ':Flake8'

" mypy
autocmd BufWritePost *.py execute ':Mypy'
```

---

## Pre-commit hooks

Pre-commit hooks автоматически запускаются перед каждым коммитом.

### Установка

```bash
make pre-commit-install
```

### Ручной запуск на всех файлах

```bash
make pre-commit-run
```

Или напрямую:

```bash
pre-commit run --all-files
```

### Пропуск hooks (не рекомендуется)

```bash
git commit --no-verify -m "Your message"
```

**Внимание:** Используйте `--no-verify` только в исключительных случаях!

---

## CI/CD интеграция

### GitHub Actions

Пример конфигурации для `.github/workflows/code-quality.yml`:

```yaml
name: Code Quality

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  quality:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Format check
      run: |
        black --check --config .black .
        isort --check-only --settings-path .isort .
    
    - name: Lint
      run: |
        flake8 --config .flake8 .
        mypy --config-file mypy.ini .
    
    - name: Run tests
      run: |
        pytest --cov=apps --cov=config --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Troubleshooting

### Проблема: Black изменяет форматирование

**Решение:**
- Убедитесь, что все разработчики используют одну и ту же версию Black
- Проверьте конфигурацию в [`.black`](../.black)

### Проблема: isort конфликтует с Black

**Решение:**
- isort настроен с профилем `black` для совместимости
- Убедитесь, что line length совпадает (100 символов)

### Проблема: mypy находит ошибки в сторонних библиотеках

**Решение:**
- Добавьте `ignore_missing_imports = True` в [`mypy.ini`](../mypy.ini)
- Установите stubs для нужных библиотек (например, `django-stubs`)

### Проблема: flake8 слишком строгий

**Решение:**
- Добавьте код ошибки в `ignore` в [`.flake8`](../.flake8)
- Используйте `# noqa: CODE` для игнорирования конкретной строки

### Проблема: Pre-commit hooks не запускаются

**Решение:**
```bash
# Переустановите hooks
pre-commit uninstall
pre-commit install

# Проверьте статус
pre-commit status
```

### Проблема: Ошибки в миграциях

**Решение:**
- Миграции исключены из линтинга по умолчанию
- Если нужно проверить миграции, временно уберите их из exclude

### Проблема: Слишком много ошибок mypy

**Решение:**
- Временно отключите strict mode в [`mypy.ini`](../mypy.ini)
- Постепенно добавляйте type hints в код
- Используйте `# type: ignore` для временного игнорирования

### Проблема: Flake8 жалуется на line length

**Решение:**
- Увеличьте `max-line-length` в [`.flake8`](../.flake8)
- Разбейте длинные строки на несколько
- Используйте скобки для неявного переноса строк

---

## Дополнительные ресурсы

- [Black documentation](https://black.readthedocs.io/)
- [isort documentation](https://pycqa.github.io/isort/)
- [flake8 documentation](https://flake8.pycqa.org/)
- [mypy documentation](https://mypy.readthedocs.io/)
- [pre-commit documentation](https://pre-commit.com/)
- [EditorConfig documentation](https://editorconfig.org/)
- [PEP 8](https://pep8.org/)

---

## Контрибьюция

При внесении изменений в код проекта:

1. Запустите `make format` для форматирования
2. Запустите `make lint` для проверки ошибок
3. Запустите `make test` для проверки тестов
4. Убедитесь, что pre-commit hooks проходят успешно

---

## Поддержка

Если у вас возникли вопросы или проблемы с настройкой линтеров:

1. Проверьте этот документ
2. Посмотрите документацию конкретного инструмента
3. Обратитесь к команде разработки через issue tracker

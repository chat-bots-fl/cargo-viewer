# Установка ngrok в WSL

## Почему устанавливать ngrok в WSL?

1. **Проще запускать** - одна команда `./start.sh` без дополнительных окон
2. **Нет проблем с коммуникацией** - все процессы в WSL
3. **Надёжнее** - не зависит от Windows
4. **Быстрее** - нет задержек между Windows и WSL

---

## Способ 1: Установка через snap (Рекомендуется)

### Проверьте, установлен ли snap
```bash
snap --version
```

Если не установлен, установите:
```bash
sudo apt update
sudo apt install snapd
```

### Установите ngrok
```bash
sudo snap install ngrok
```

### Проверьте установку
```bash
ngrok version
```

### Добавьте ngrok в PATH (если нужно)
```bash
# Добавьте в ~/.bashrc или ~/.zshrc
export PATH="$PATH:/snap/bin"
```

Перезапустите терминал или выполните:
```bash
source ~/.bashrc
```

---

## Способ 2: Установка через apt (Альтернатива)

### Добавьте репозиторий ngrok
```bash
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
```

### Обновите список пакетов
```bash
sudo apt update
```

### Установите ngrok
```bash
sudo apt install ngrok
```

### Проверьте установку
```bash
ngrok version
```

---

## Способ 3: Скачивание бинарного файла (Универсальный)

### Скачайте ngrok
```bash
cd ~
wget https://bin.equinox.io/c/4VmDzA7bV9a/ngrok-stable-linux-amd64.zip
```

### Распакуйте архив
```bash
unzip ngrok-stable-linux-amd64.zip
```

### Переместите в /usr/local/bin
```bash
sudo mv ngrok /usr/local/bin/ngrok
```

### Проверьте установку
```bash
ngrok version
```

---

## Настройка автозаполнения токена (Опционально)

### Войдите в ngrok
```bash
ngrok config add-authtoken YOUR_TOKEN
```

Замените `YOUR_TOKEN` на ваш токен из https://dashboard.ngrok.com/get-started/your-authtoken

---

## Проверка работы

### Запустите ngrok
```bash
ngrok http 8000
```

### Проверьте, что ngrok работает
Откройте в браузере: http://127.0.0.1:4040

Должен показать интерфейс ngrok с URL туннеля.

---

## Использование с проектом

### После установки ngrok в WSL

```bash
# Подготовка окружения (первый раз)
./setup.sh

# Запуск сервисов (каждый раз)
./start.sh
```

Теперь скрипт [`start.sh`](start.sh:1) автоматически найдёт ngrok в WSL и запустит его!

---

## Удаление ngrok

### Если установлен через snap
```bash
sudo snap remove ngrok
```

### Если установлен через apt
```bash
sudo apt remove ngrok
```

### Если установлен вручную
```bash
sudo rm /usr/local/bin/ngrok
```

---

## Решение проблем

### Ошибка: "snap not found"
```bash
sudo apt update
sudo apt install snapd
```

### Ошибка: "permission denied"
```bash
sudo snap install ngrok
```

### Ошибка: "command not found"
```bash
# Проверьте, где установлен ngrok
which ngrok

# Если не найден, добавьте в PATH
export PATH="$PATH:/snap/bin"
```

### Ошибка: "ngrok: command not found" после установки
```bash
# Перезапустите терминал или выполните
source ~/.bashrc

# Или используйте полный путь
/snap/bin/ngrok version
```

---

## Рекомендация

**Используйте Способ 1 (snap)** - это самый простой и надёжный способ установки ngrok в WSL.

После установки ngrok в WSL, запуск проекта станет намного проще:
```bash
./start.sh
```

Всё будет работать в WSL без необходимости запускать ngrok в отдельном окне Windows!

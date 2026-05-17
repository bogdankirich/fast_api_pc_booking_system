# Тесты Telegram-бота

Асинхронные тесты для Telegram-бота на базе aiogram 3 с использованием pytest и pytest-asyncio.

## Структура

```
tests/tg_bot/
├── conftest.py              # Фикстуры для тестирования
├── test_common.py           # Тесты базовых команд (/start)
├── test_auth.py             # Тесты авторизации и логина
├── test_profile.py          # Тесты профиля пользователя
└── test_api_client.py       # Тесты APIClient с автообновлением токенов
```

## Фикстуры (conftest.py)

### Основные фикстуры

- `bot_user` - имитация объекта User из aiogram
- `chat` - имитация объекта Chat
- `message` - мок объекта Message с AsyncMock для методов answer/edit_text
- `callback_query` - мок объекта CallbackQuery
- `fsm_context` - FSMContext с MemoryStorage для тестирования состояний
- `authenticated_fsm_context` - FSMContext с предустановленными токенами
- `mock_api_client` - замоканный APIClient для изоляции от бэкенда
- `mock_httpx_client` - замоканный httpx.AsyncClient для HTTP-запросов

## Покрытие тестами

### test_common.py
- ✅ Проверка приветственного сообщения `/start`
- ✅ Проверка корректности клавиатуры

### test_auth.py
- ✅ Начало процесса логина (`/login`)
- ✅ Сохранение email и переход к вводу пароля
- ✅ Обработка пустого email
- ✅ Успешный логин с сохранением токенов
- ✅ Привязка telegram_id через PATCH запрос
- ✅ Обработка неверных учетных данных (401)
- ✅ Обработка ошибок сервера (500)
- ✅ Обработка ошибок подключения
- ✅ Обработка пустого пароля
- ✅ Обработка ошибки привязки telegram_id

### test_profile.py
- ✅ Проверка неавторизованного доступа
- ✅ Отображение профиля обычного пользователя
- ✅ Отображение профиля администратора
- ✅ Обработка null значения баланса
- ✅ Обработка ошибок API (500)
- ✅ Обработка исключений
- ✅ Выход из аккаунта (logout) с очисткой состояния
- ✅ Callback пополнения баланса

### test_api_client.py
- ✅ GET запрос с валидным токеном
- ✅ POST запрос с JSON данными
- ✅ Ошибка при отсутствии токена
- ✅ Автоматическое обновление токена при 401
- ✅ Очистка состояния при неудачном обновлении токена
- ✅ DELETE метод
- ✅ PUT метод

## Запуск тестов

### Все тесты бота
```bash
pytest tests/tg_bot/ -v
```

### Конкретный модуль
```bash
pytest tests/tg_bot/test_auth.py -v
```

### Конкретный тест
```bash
pytest tests/tg_bot/test_auth.py::test_process_password_successful_login -v
```

### С покрытием кода
```bash
pytest tests/tg_bot/ --cov=tg_bot --cov-report=html
```

## Особенности реализации

### Изоляция от FastAPI тестов
Тесты бота изолированы от тестов FastAPI через проверку в `tests/conftest.py`:
```python
if "tg_bot" in request.node.nodeid:
    yield
    return
```

### Мокирование API запросов
Все HTTP-запросы к бэкенду замоканы через `unittest.mock.patch`:
```python
with patch("httpx.AsyncClient", return_value=mock_httpx_client):
    await process_password(message, fsm_context)
```

### Мокирование APIClient
Кастомный APIClient замокан для предотвращения реальных запросов:
```python
with patch("tg_bot.handlers.profile.api_client", mock_api_client):
    await cmd_profile(message, authenticated_fsm_context)
```

### Асинхронные тесты
Все тесты помечены декоратором `@pytest.mark.asyncio` для корректной работы с async/await.

## Соответствие стандартам

- ✅ PEP8 форматирование
- ✅ Типизация всех параметров и возвращаемых значений
- ✅ Использование AsyncMock для асинхронных методов
- ✅ Изоляция тестов (без реальных HTTP-запросов)
- ✅ Понятные имена тестов в формате `test_<action>_<expected_result>`
- ✅ Проверка как успешных, так и ошибочных сценариев

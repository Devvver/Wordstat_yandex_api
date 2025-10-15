import streamlit as st
import requests
import pandas as pd
import time
import io
import sqlite3
import os
import re

# -------------------
# Конфиг
# -------------------
API_URL = "https://api.wordstat.yandex.net/v1/topRequests"
USER_INFO_URL = "https://api.wordstat.yandex.net/v1/userInfo"
TOKEN = "тут ваш апи код"  # ВНИМАНИЕ: это публичный токен, замените его
NUM_PHRASES = 2000
MAX_ERRORS = 3  # Максимальное количество последовательных ошибок API

st.set_page_config(page_title="Yandex Wordstat Parser", layout="wide")
st.title("🔍 Парсер Yandex Wordstat API с SQLite ")


# -------------------
# Функции работы с API
# -------------------
# -------------------
# Функции работы с API
# -------------------
# -------------------
# Функции работы с API
# -------------------
def fetch_user_info(token):
    """
    Получает информацию о квоте пользователя, выполняя ТОЛЬКО POST-запрос,
    который был определен как рабочий.
    """
    # URL для этого метода уже должен быть определен в конфиге: USER_INFO_URL
    # (USER_INFO_URL = "https://api.wordstat.yandex.net/v1/userInfo")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
    }

    if not token:
        st.error("Токен API пуст.")
        return None

    try:
        # Выполняем сразу POST-запрос
        resp = requests.post(USER_INFO_URL, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("userInfo", {}).get("dailyLimitRemaining")
        else:
            # Выводим код ошибки, если POST не сработал
            st.error(f"Не удалось получить информацию о квоте. Код: {resp.status_code}.")
            return None

    except Exception as e:
        st.error(f"Ошибка при запросе /v1/userInfo: {e}")
        return None


def fetch_wordstat(phrase, region, token, no_region=False):
    # URL для этого метода уже должен быть определен в конфиге: API_URL
    # (API_URL = "https://api.wordstat.yandex.net/v1/topRequests")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8"
    }
    body = {"phrase": phrase, "numPhrases": NUM_PHRASES}  # NUM_PHRASES должен быть в конфиге
    if not no_region:
        body["regions"] = [int(region)]
    try:
        resp = requests.post(API_URL, headers=headers, json=body, timeout=30)
        if resp.status_code != 200:
            st.warning(f"Ошибка API для запроса '{phrase}': Код {resp.status_code}. Пропускаем.")
            return []
        data = resp.json()
        return data.get("topRequests", [])
    except Exception as e:
        st.error(f"Ошибка при запросе '{phrase}': {e}")
        return []





def fetch_wordstat(phrase, region, token, no_region=False):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8"
    }
    body = {"phrase": phrase, "numPhrases": NUM_PHRASES}
    if not no_region:
        body["regions"] = [int(region)]
    try:
        resp = requests.post(API_URL, headers=headers, json=body, timeout=30)
        # 429 Too Many Requests, 503 Service Unavailable и другие ошибки
        if resp.status_code != 200:
            st.warning(f"Ошибка API для запроса '{phrase}': Код {resp.status_code}. Пропускаем.")
            return []
        data = resp.json()
        return data.get("topRequests", [])
    except Exception as e:
        st.error(f"Ошибка при запросе '{phrase}': {e}")
        return []


# -------------------
# Функции работы с SQLite
# -------------------
def sanitize_filename(phrase):
    """Очищает фразу для использования в качестве имени файла."""
    phrase = re.sub(r'[\\/:*?"<>|]', '', phrase)
    return phrase.strip().replace(' ', '_')[:50] + ".db"


def setup_db(db_name):
    """Подключается к БД и создает две таблицы: results и queue."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            phrase TEXT PRIMARY KEY,
            count INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            phrase TEXT PRIMARY KEY,
            status TEXT DEFAULT 'PENDING' 
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_queue ON queue (status)")
    conn.commit()
    return conn


def insert_result_and_queue(conn, phrase, count, is_processed=False):
    """Вставляет фразу в results и в queue."""
    conn.execute("INSERT OR IGNORE INTO results (phrase, count) VALUES (?, ?)", (phrase, count))
    status = 'PROCESSED' if is_processed else 'PENDING'
    conn.execute("INSERT OR IGNORE INTO queue (phrase, status) VALUES (?, ?)", (phrase, status))


def update_queue_status(conn, phrase, status='PROCESSED'):
    """Обновляет статус фразы в таблице queue."""
    conn.execute("UPDATE queue SET status = ? WHERE phrase = ?", (status, phrase))


def get_all_results_df(conn):
    """Загружает все результаты из БД в DataFrame."""
    return pd.read_sql_query("SELECT phrase AS Фраза, count AS Показы FROM results ORDER BY Показы DESC", conn)


def get_db_phrase_count(conn):
    """Возвращает текущее количество уникальных фраз из таблицы results."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(phrase) FROM results")
    return cursor.fetchone()[0]


# -------------------
# Функция вывода таблицы и кнопок (без изменений)
# -------------------
def render_results(df: pd.DataFrame, db_name: str):
    st.subheader("📊 Результаты")
    st.dataframe(df, use_container_width=True)

    col1, col2, col3 = st.columns(3)

    csv_data = df.to_csv(index=False).encode("utf-8")
    with col1:
        st.download_button(
            "📥 Скачать CSV",
            csv_data,
            file_name=f"{db_name.replace('.db', '')}.csv",
            mime="text/csv",
            key="csv_btn"
        )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wordstat")
    with col2:
        st.download_button(
            "📊 Скачать Excel",
            output.getvalue(),
            file_name=f"{db_name.replace('.db', '')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_btn"
        )
    with col3:
        if os.path.exists(db_name):
            with open(db_name, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                "💾 Скачать SQLite DB",
                db_bytes,
                file_name=db_name,
                mime="application/octet-stream",
                key="sqlite_btn"
            )
        else:
            st.info("Файл БД не найден для скачивания.")


# -------------------
# UI и Основная логика
# -------------------

# --- 🆕 Вывод оставшейся квоты в основной части UI
remaining_quota = fetch_user_info(TOKEN)

# --- Параметры парсинга
col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    phrase = st.text_input("Введите исходный запрос", "фраза").strip()
    no_region = st.checkbox("Парсинг без региона", value=False)
with col2:
    region = st.number_input("ID региона", value=225, step=1, disabled=no_region)
with col3:
    # 2. Создаем плейсхолдер для динамического обновления
    quota_placeholder = st.empty()
    if remaining_quota is None:
        quota_placeholder.info("Квота неизвестна")
    else:
        # 3. Выводим начальное значение
        quota_placeholder.metric(label="Остаток дневной квоты", value=f"{remaining_quota} запросов")


max_requests = st.number_input("Максимум рекурсивных запросов (N).", value=5, step=1, min_value=1)
st.caption(f"Лимит квоты сбросится в полночь по МСК. Парсинг остановится после {MAX_ERRORS} последовательных ошибок.")

# --- Логика кнопки очистки
if "current_db" in st.session_state and os.path.exists(st.session_state["current_db"]):
    if st.button(f"🗑️ Удалить БД: {st.session_state['current_db']}"):
        os.remove(st.session_state["current_db"])
        del st.session_state["current_db"]
        if "df" in st.session_state:
            del st.session_state["df"]
        st.success("База данных удалена. Перезапустите парсинг.")
        st.rerun()

start_btn = st.button("🚀 Запустить парсинг")

# --- Основная логика выполнения
if start_btn:
    if not phrase:
        st.error("Пожалуйста, введите исходный запрос.")
        st.stop()

    # 1. Формирование имени БД и подключение
    db_name = sanitize_filename(phrase)
    st.session_state["current_db"] = db_name
    conn = setup_db(db_name)

    # 2. Загрузка очереди для возобновления парсинга
    with st.spinner("Загрузка очереди из БД..."):
        query_queue = pd.read_sql_query("SELECT phrase FROM queue WHERE status = 'PENDING'", conn)['phrase'].tolist()
        queue_set = set(query_queue)

    progress = st.progress(0)
    status = st.empty()
    start_time = time.time()
    total_phrases = get_db_phrase_count(conn)
    consecutive_errors = 0

    # --- Первый запрос (если очередь пуста)
    # --- Первый запрос (если очередь пуста)
    if not query_queue:

        current_phrase = phrase

        first = fetch_wordstat(current_phrase, region, TOKEN, no_region=no_region)

        # Проверка: Если первый запрос сразу ошибочен (429/503), не начинаем
        if not first:
            st.error("❌ Первый запрос завершился ошибкой. Парсинг не может быть начат.")
            conn.close()
            st.stop()

        # 1. Получаем частотность исходной фразы (она должна быть первой в массиве)
        # Убеждаемся, что элемент существует и содержит нужную фразу
        initial_phrase_count = first[0].get('count', 0) if first and first[0].get('phrase') == current_phrase else 0

        # 2. Вставляем ИСХОДНУЮ фразу с ее частотностью и сразу ставим статус 'PROCESSED'.
        insert_result_and_queue(conn, current_phrase, initial_phrase_count, is_processed=True)

        # 3. Обрабатываем ВСЕ 2000 фраз. INSERT OR IGNORE позаботится о дедупликации.
        for item in first:
            p = item["phrase"]
            c = item["count"]

            # Вставляем/обновляем в results, и добавляем PENDING в queue (кроме уже PROCESSED)
            insert_result_and_queue(conn, p, c, is_processed=False)

            # Добавляем в оперативную очередь только PENDING
            if p not in queue_set:
                query_queue.append(p)
                queue_set.add(p)

        conn.commit()
        total_phrases = get_db_phrase_count(conn)
    else:
        st.info(f"Возобновление парсинга. Очередь: {len(query_queue)} фраз.")

    # --- Рекурсивные запросы
    done_requests = 0

    # Цикл работает, пока:
    # 1. Мы не превысили установленный пользователем лимит API-запросов (max_requests).
    # 2. В очереди есть фразы, ожидающие обработки.
    while done_requests < max_requests and query_queue:
        # Берем фразу для обработки
        current_phrase = query_queue.pop(0)
        queue_set.discard(current_phrase)

        # Пропускаем, если фраза уже была обработана (важно для возобновления)
        status_check = conn.execute("SELECT status FROM queue WHERE phrase = ?", (current_phrase,)).fetchone()
        if status_check and status_check[0] == 'PROCESSED':
            continue

        # 1. Выполняем запрос к API.
        # В ответ приходит список 'wordstat' до 2000 фраз.
        wordstat = fetch_wordstat(current_phrase, region, TOKEN, no_region=no_region)
        done_requests += 1  # Увеличиваем счетчик API-запросов

        # 2. Логика контроля ошибок (429/503)
        if not wordstat:
            consecutive_errors += 1

            if consecutive_errors >= MAX_ERRORS:
                st.error(f"❌ Достигнут лимит последовательных ошибок ({MAX_ERRORS}). Парсинг остановлен.")
                break

                # При ошибке возвращаем фразу в конец очереди, чтобы попробовать снова
            st.warning(
                f"⚠️ Ошибка API. Фраза '{current_phrase}' осталась в PENDING. Счет: {consecutive_errors}/{MAX_ERRORS}. Ожидание...")
            query_queue.append(current_phrase)
            queue_set.add(current_phrase)
            time.sleep(5)
            continue

        else:
            consecutive_errors = 0

            # 3. Обработка результатов и пополнение очереди
            # Перебираем ВСЕ полученные от API фразы (макс. 2000)
            for item in wordstat:
                p = item["phrase"]
                c = item["count"]

                # Сохраняем результат и добавляем в очередь как PENDING
                insert_result_and_queue(conn, p, c, is_processed=False)

                # Добавляем в оперативную очередь, только если фраза еще не там
                if p not in queue_set:
                    query_queue.append(p)
                    queue_set.add(p)

            # 4. СОХРАНЕНИЕ ПОЗИЦИИ: Помечаем текущую фразу как обработанную
            update_queue_status(conn, current_phrase, 'PROCESSED')
            conn.commit()
            if remaining_quota is not None and remaining_quota > 0:
                remaining_quota -= 1
                quota_placeholder.metric(label="Остаток дневной квоты", value=f"{remaining_quota} запросов")

            # 5. Обновление прогресса и ETA
        total_phrases = get_db_phrase_count(conn)
        elapsed = time.time() - start_time
        avg_time = elapsed / done_requests
        eta = avg_time * (max_requests - done_requests) if done_requests < max_requests else 0

        progress.progress(done_requests / max_requests)
        status.text(
            f"Запрос {done_requests}/{max_requests} | Фраз: {total_phrases} | Осталось ~ {eta:.1f} сек ")

        # 6. Пауза между запросами (для контроля QPS)
        time.sleep(0.15)

        # 3. Загрузка финального результата и завершение
    df = get_all_results_df(conn)
    conn.close()

    # сохраняем результат в сессию
    st.session_state["df"] = df
    st.session_state["db_name"] = db_name

    # Финальное сообщение
    if done_requests == max_requests:
        st.success(f"✅ Установленный лимит запросов ({max_requests}) достигнут. Собрано {len(df)} фраз.")
    elif consecutive_errors >= MAX_ERRORS:
        st.warning(f"⚠️ Парсинг остановлен из-за лимита API. Собрано {len(df)} фраз. Возобновите позже.")
    elif not query_queue:
        st.success(f"✅ Парсинг завершен! Вся очередь обработана. Собрано {len(df)} фраз.")
    else:
        st.success(f"✅ Готово! Собрано {len(df)} уникальных фраз.")

# -------------------
# Отрисовка таблицы (всегда одна, из сессии)
# -------------------
if "df" in st.session_state and not st.session_state["df"].empty:
    render_results(st.session_state["df"], st.session_state["db_name"])
elif "current_db" in st.session_state and os.path.exists(st.session_state["current_db"]):
    try:
        conn = setup_db(st.session_state["current_db"])
        df = get_all_results_df(conn)
        conn.close()
        if not df.empty:
            st.session_state["df"] = df
            st.session_state["db_name"] = st.session_state["current_db"]
            render_results(st.session_state["df"], st.session_state["db_name"])
        else:
            st.info(f"База данных {st.session_state['current_db']} существует, но пуста. Запустите парсинг.")
    except Exception as e:
        st.error(f"Не удалось загрузить данные из SQLite ({st.session_state['current_db']}): {e}")
import streamlit as st
import requests
import pandas as pd
import time
import io

# -------------------
# Конфиг
# -------------------
API_URL = "https://api.wordstat.yandex.net/v1/topRequests"
TOKEN = "сюда ваш токен"
NUM_PHRASES = 2000

st.set_page_config(page_title="Yandex Wordstat Parser", layout="wide")
st.title("🔍 Парсер Yandex Wordstat API")

# -------------------
# Функция API-запроса
# -------------------
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
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("topRequests", [])
    except Exception as e:
        st.error(f"Ошибка: {e}")
        return []

# -------------------
# Функция вывода таблицы и кнопок (всегда одна)
# -------------------
def render_results(df: pd.DataFrame):
    st.subheader("📊 Результаты")
    st.dataframe(df, use_container_width=True)

    col1, col2 = st.columns(2)
    # CSV
    csv_data = df.to_csv(index=False).encode("utf-8")
    with col1:
        st.download_button(
            "📥 Скачать CSV",
            csv_data,
            file_name="wordstat.csv",
            mime="text/csv",
            key="csv_btn"
        )
    # Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Wordstat")
    with col2:
        st.download_button(
            "📊 Скачать Excel",
            output.getvalue(),
            file_name="wordstat.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="excel_btn"
        )

# -------------------
# UI
# -------------------
col1, col2 = st.columns([2, 1])
with col1:
    phrase = st.text_input("Введите исходный запрос", "фраза").strip()
    no_region = st.checkbox("Парсинг без региона", value=False)
with col2:
    region = st.number_input("ID региона", value=225, step=1, disabled=no_region)

max_requests = st.number_input("Максимум рекурсивных запросов (N). Учитывайте ограничение 1000 запросов в сутки", value=5, step=1, min_value=1)
start_btn = st.button("🚀 Запустить парсинг")

# -------------------
# Основная логика
# -------------------
if start_btn:
    results = {}
    query_queue = []

    progress = st.progress(0)
    status = st.empty()

    start_time = time.time()

    # --- Первый запрос
    first = fetch_wordstat(phrase, region, TOKEN, no_region=no_region)
    for item in first:
        p = item["phrase"]
        c = item["count"]
        results[p] = c
        query_queue.append(p)

    # --- Рекурсивные запросы
    done_requests = 0
    while done_requests < max_requests and query_queue:
        current = query_queue.pop(0)
        wordstat = fetch_wordstat(current, region, TOKEN, no_region=no_region)
        done_requests += 1

        for item in wordstat:
            p = item["phrase"]
            c = item["count"]
            if p not in results:
                results[p] = c
                query_queue.append(p)

        elapsed = time.time() - start_time
        avg_time = elapsed / done_requests
        eta = avg_time * (max_requests - done_requests)

        progress.progress(done_requests / max_requests)
        status.text(f"Запрос {done_requests}/{max_requests} | Осталось ~ {eta:.1f} сек")

        time.sleep(1)

    # сохраняем результат в сессию
    df = pd.DataFrame([{"Фраза": k, "Показы": v} for k, v in results.items()])
    df = df.sort_values("Показы", ascending=False).reset_index(drop=True)
    st.session_state["df"] = df
    st.session_state["last_phrase"] = phrase
    st.success(f"✅ Готово! Собрано {len(results)} уникальных фраз.")

# -------------------
# Отрисовка таблицы (всегда одна, из сессии)
# -------------------
if "df" in st.session_state and not st.session_state["df"].empty:
    render_results(st.session_state["df"])

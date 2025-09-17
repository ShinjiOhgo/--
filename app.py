# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from mahjong_manager import MahjongScoreManager
import os

# --- アプリの基本設定 ---
st.set_page_config(
    page_title="麻雀成績管理アプリ",
    page_icon="🀄",
    layout="wide"
)

# --- Excelファイルのパスを指定 ---
EXCEL_FILE_PATH = 'mahjong_management.xlsx'

# --- セッション管理 ---
if 'manager' not in st.session_state:
    st.session_state.manager = MahjongScoreManager(EXCEL_FILE_PATH)

manager = st.session_state.manager

# --- サイドバー ---
st.sidebar.title("🀄 操作メニュー")

if st.sidebar.button("データ再読み込み"):
    st.session_state.manager = MahjongScoreManager(EXCEL_FILE_PATH)
    st.rerun()

app_mode = st.sidebar.radio(
    "モードを選択してください",
    ("成績ランキング", "個人成績", "成績入力")
)

st.sidebar.header("絞り込み条件")

# 日付フィルター
if manager.raw_data is not None and not manager.raw_data.empty:
    min_date = manager.raw_data['日付'].min().date()
    max_date = manager.raw_data['日付'].max().date()
else:
    min_date = datetime.today().date() - timedelta(days=365)
    max_date = datetime.today().date()

start_date = st.sidebar.date_input('開始日', min_date, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input('終了日', max_date, min_value=min_date, max_value=max_date)

# チップフィルター (新規追加)
chip_rule = st.sidebar.radio(
    "チップの有無で絞り込み",
    ("全て", "チップありのみ", "チップなしのみ"),
    index=0  # デフォルトは「全て」
)

# --- メイン画面 ---
if app_mode == "成績ランキング":
    st.title("🏆 成績ランキング")
    stats_df = manager.calculate_stats(start_date, end_date, chip_filter=chip_rule)
    if not stats_df.empty:
        ranking = stats_df.sort_values(by='トータルスコア', ascending=False).reset_index(drop=True)
        st.dataframe(ranking[['名前', 'トータルスコア', 'チップスコア', '平均着順', '対戦回数']], use_container_width=True)
    else:
        st.warning("選択された条件のデータがありません。")

elif app_mode == "個人成績":
    st.title("📊 個人成績")
    player_list = manager.get_player_list()
    if player_list:
        selected_player = st.sidebar.selectbox("対戦者を選択", player_list)
        stats_df = manager.calculate_stats(start_date, end_date, chip_filter=chip_rule)
        player_data = stats_df[stats_df['名前'] == selected_player]
        if not player_data.empty:
            st.header(f"{selected_player} さんの成績")
            st.dataframe(player_data[['名前', 'トータルスコア', 'チップスコア', '平均着順', '対戦回数']], use_container_width=True)
        else:
            st.warning(f"選択された条件に {selected_player} さんのデータはありません。")
    else:
        st.warning("表示できる対戦者がいません。")

elif app_mode == "成績入力":
    st.title("📝 成績入力")
    with st.form(key='add_record_form'):
        input_date = st.date_input("対戦日")
        st.subheader("対戦結果をスコア(点)で入力")
        players = [{} for _ in range(4)]
        for i in range(4):
            with st.container():
                cols = st.columns([2, 2, 1])
                players[i]['名前'] = cols[0].text_input(f"プレイヤー{i+1} 名前", key=f"name{i}")
                players[i]['SCORE'] = cols[1].number_input(f"プレイヤー{i+1} スコア", step=100, key=f"score{i}")
                players[i]['チップ'] = cols[2].number_input(f"プレイヤー{i+1} チップ", step=1, key=f"tip{i}")
        submit_button = st.form_submit_button(label='この内容で記録する')

    if submit_button:
        if not all(p['名前'] for p in players):
            st.error("エラー: 4人全員の名前を入力してください。")
        elif sum(p['SCORE'] for p in players) != 0:
            st.error(f"エラー: 4人のスコア合計が0になりません (現在: {sum(p['SCORE'] for p in players)})。")
        else:
            date_str = input_date.strftime('%y%m%d')
            success, message = manager.add_record(date_str, players)
            if success:
                st.success(message)
            else:
                st.error(message)
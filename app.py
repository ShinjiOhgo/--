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
EXCEL_FILE_PATH = 'mahjong_management.xlsx' # ご自身のファイル名に合わせてください

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
start_date = None
end_date = None

if manager.raw_data is not None and not manager.raw_data.empty:
    available_dates = sorted(manager.raw_data['日付'].dt.date.unique())
    
    start_date = st.sidebar.selectbox(
        "開始日",
        available_dates,
        index=0
    )
    
    end_date = st.sidebar.selectbox(
        "終了日",
        available_dates,
        index=len(available_dates) - 1
    )

    if start_date > end_date:
        st.sidebar.error("エラー: 終了日は開始日以降の日付を選択してください。")
        st.stop()

# チップフィルター
chip_rule = st.sidebar.radio(
    "チップの有無で絞り込み",
    ("全て", "チップありのみ", "チップなしのみ"),
    index=0
)

# --- メイン画面 ---
if app_mode == "成績ランキング":
    st.title("🏆 成績ランキング")
    date_title = f"{start_date} ~ {end_date}" if start_date and end_date and start_date != end_date else (start_date or "全期間")
    st.header(f"対象期間: {date_title}")

    stats_df = manager.calculate_stats(start_date, end_date, chip_filter=chip_rule)
    if not stats_df.empty:
        ranking = stats_df.sort_values(by='トータルスコア', ascending=False).reset_index(drop=True)
        st.dataframe(ranking[['名前', 'トータルスコア', 'チップスコア', '平均着順', '対戦回数']], use_container_width=True, height = 800)
    else:
        st.warning("選択された条件のデータがありません。")

elif app_mode == "個人成績":
    st.title("📊 個人成績")
    date_title = f"{start_date} ~ {end_date}" if start_date and end_date and start_date != end_date else (start_date or "全期間")
    st.header(f"対象期間: {date_title}")

    player_list = manager.get_player_list()
    if player_list:
        selected_player = st.sidebar.selectbox("対戦者を選択", player_list)
        stats_df = manager.calculate_stats(start_date, end_date, chip_filter=chip_rule)
        player_data = stats_df[stats_df['名前'] == selected_player]
        if not player_data.empty:
            st.header(f"{selected_player} さんの成績")
            st.dataframe(player_data[['名前', 'トータルスコア', 'チップスコア', '平均着順', '対戦回数']], use_container_width=True, height=1000)
        else:
            st.warning(f"選択された条件に {selected_player} さんのデータはありません。")
    else:
        st.warning("表示できる対戦者がいません。")

# --- 成績入力部分 ---
elif app_mode == "成績入力":
    st.title("📝 成績入力")
    with st.form(key='add_record_form'):
        input_date = st.date_input("対戦日")
        st.subheader("対戦結果を素点(持ち点)で入力")
        
        players_input = []
        for i in range(4):
            with st.container():
                cols = st.columns([2, 2, 1])
                player_info = {
                    '名前': cols[0].text_input(f"プレイヤー{i+1} 名前", key=f"name{i}"),
                    '素点': cols[1].number_input(f"プレイヤー{i+1} 素点", value=25000, step=100, key=f"soten{i}"),
                    'チップ': cols[2].number_input(f"プレイヤー{i+1} チップ", step=1, key=f"tip{i}")
                }
                players_input.append(player_info)

        submit_button = st.form_submit_button(label='この内容で記録する')

# app.py の if submit_button: ブロック以降をこちらに差し替え

    if submit_button:
        if not all(p['名前'] for p in players_input):
            st.error("エラー: 4人全員の名前を入力してください。")
        elif sum(p['素点'] for p in players_input) != 100000:
            st.error(f"エラー: 4人の素点合計が100000になりません (現在: {sum(p['素点'] for p in players_input)})。")
        else:
            # --- ▼▼▼ ここから修正 ▼▼▼ ---

            # 1. 素点（持ち点）でプレイヤーを降順にソート
            sorted_players = sorted(players_input, key=lambda p: p['素点'], reverse=True)

            # 2. 同点がないと仮定した場合の各順位のスコアを計算
            #    - 2位、3位、4位のスコアを、ソート後の各順位のプレイヤーの素点から計算
            score_2nd = round((sorted_players[1]['素点'] - 30000) / 1000) + 10
            score_3rd = round((sorted_players[2]['素点'] - 30000) / 1000) - 10
            score_4th = round((sorted_players[3]['素点'] - 30000) / 1000) - 30
            
            #    - 1位のスコアは、全体の合計が0になるように調整
            score_1st = -(score_2nd + score_3rd + score_4th)
            
            #    - 各順位の理論上のスコアをリストに格納
            theoretical_scores = [score_1st, score_2nd, score_3rd, score_4th]

            # 3. 最終的な記録リストを作成（同点処理）
            final_records = []
            i = 0
            while i < len(sorted_players):
                # 同じ素点のプレイヤーが何人いるかを見つける
                j = i
                while j < len(sorted_players) and sorted_players[j]['素点'] == sorted_players[i]['素点']:
                    j += 1
                
                # 同点グループの範囲はインデックス i から j-1
                num_tied = j - i
                
                # 同点グループがまたがる順位の理論スコアを合計
                total_score_for_tied_group = sum(theoretical_scores[i:j])
                
                # 平均スコアを計算
                average_score = total_score_for_tied_group / num_tied if num_tied > 0 else 0
                
                # 同点グループの各プレイヤーに平均化されたスコアを割り当てる
                for k in range(i, j):
                    player = sorted_players[k]
                    final_records.append({
                        '名前': player['名前'],
                        'SCORE': average_score,
                        'チップ': player['チップ']
                    })
                
                # 次のプレイヤー（グループ）へインデックスを移動
                i = j


            # --- ▲▲▲ ここまで修正 ▲▲▲ ---

            date_str = input_date.strftime('%y%m%d')
            success, message = manager.add_record(date_str, final_records)
            
            if success:
                st.success(message)
            else:
                st.error(message)
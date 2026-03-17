import streamlit as st 
import pandas as pd 
import requests 
import numpy as np
from bs4 import BeautifulSoup 
from nba_api.stats.endpoints import leaguedashteamstats, scoreboardv2, leaguedashplayerstats 
from nba_api.stats.static import teams 
from datetime import datetime, timedelta 
import json
import os
import time
import pickle # 新增：用來將 NBA 龐大數據存成實體檔案

# ------------------------ 
# 0 核心配置與中英對照庫 
# ------------------------ 
TEAM_CN = { 
    "Atlanta Hawks": "老鷹", "Boston Celtics": "塞爾提克", "Brooklyn Nets": "籃網", 
    "Charlotte Hornets": "黃蜂", "Chicago Bulls": "公牛", "Cleveland Cavaliers": "騎士", 
    "Dallas Mavericks": "獨行俠", "Denver Nuggets": "金塊", "Detroit Pistons": "活塞", 
    "Golden State Warriors": "勇士", "Houston Rockets": "火箭", "Indiana Pacers": "溜馬", 
    "LA Clippers": "快艇", "Los Angeles Lakers": "湖人", "Memphis Grizzlies": "灰熊", 
    "Miami Heat": "熱火", "Milwaukee Bucks": "公鹿", "Minnesota Timberwolves": "灰狼", 
    "New Orleans Pelicans": "鵜鶘", "New York Knicks": "尼克", "Oklahoma City Thunder": "雷霆", 
    "Orlando Magic": "魔術", "Philadelphia 76ers": "76人", "Phoenix Suns": "太陽", 
    "Portland Trail Blazers": "拓荒者", "Sacramento Kings": "國王", "San Antonio Spurs": "馬刺", 
    "Toronto Raptors": "暴龍", "Utah Jazz": "爵士", "Washington Wizards": "巫師" 
} 

TEAM_ZONE = {
    "Atlanta Hawks": "East", "Boston Celtics": "East", "Brooklyn Nets": "East",
    "Charlotte Hornets": "East", "Chicago Bulls": "East", "Cleveland Cavaliers": "East",
    "Detroit Pistons": "East", "Indiana Pacers": "East", "Miami Heat": "East",
    "Milwaukee Bucks": "East", "New York Knicks": "East", "Orlando Magic": "East",
    "Philadelphia 76ers": "East", "Toronto Raptors": "East", "Washington Wizards": "East",
    "Dallas Mavericks": "West", "Denver Nuggets": "West", "Golden State Warriors": "West",
    "Houston Rockets": "West", "LA Clippers": "West", "Los Angeles Lakers": "West",
    "Memphis Grizzlies": "West", "Minnesota Timberwolves": "West", "New Orleans Pelicans": "West",
    "Oklahoma City Thunder": "West", "Phoenix Suns": "West", "Portland Trail Blazers": "West",
    "Sacramento Kings": "West", "San Antonio Spurs": "West", "Utah Jazz": "West"
}

ODDS_API_TEAMS = {k: k for k in TEAM_CN.keys()} 
ODDS_API_TEAMS["LA Clippers"] = "Los Angeles Clippers"

STAR_PLAYERS = { 
    "Lakers": ["LeBron James", "Anthony Davis", "D'Angelo Russell", "Austin Reaves"],  
    "Nuggets": ["Nikola Jokic", "Jamal Murray", "Aaron Gordon", "Michael Porter Jr."], 
    "Celtics": ["Jayson Tatum", "Jaylen Brown", "Kristaps Porzingis", "Derrick White", "Jrue Holiday"],  
    "Mavericks": ["Luka Doncic", "Kyrie Irving", "Dereck Lively"], 
    "Thunder": ["Shai Gilgeous-Alexander", "Chet Holmgren", "Jalen Williams"],  
    "Timberwolves": ["Anthony Edwards", "Rudy Gobert", "Karl-Anthony Towns"], 
    "Bucks": ["Giannis Antetokounmpo", "Damian Lillard", "Khris Middleton"],  
    "Warriors": ["Stephen Curry", "Draymond Green", "Jonathan Kuminga", "Andrew Wiggins"], 
    "Suns": ["Kevin Durant", "Devin Booker", "Bradley Beal"], 
    "76ers": ["Joel Embiid", "Tyrese Maxey", "Paul George"], 
    "Clippers": ["Kawhi Leonard", "James Harden"], 
    "Heat": ["Jimmy Butler", "Bam Adebayo"], 
    "Kings": ["De'Aaron Fox", "Domantas Sabonis"] 
} 

PLAYER_CN = { 
    "LeBron James": "詹姆斯", "Anthony Davis": "戴維斯", "D'Angelo Russell": "羅素", "Austin Reaves": "里夫斯", 
    "Nikola Jokic": "約基奇", "Jamal Murray": "莫瑞", "Aaron Gordon": "高登", "Michael Porter Jr.": "小波特", 
    "Jayson Tatum": "塔圖姆", "Jaylen Brown": "布朗", "Kristaps Porzingis": "波辛吉斯", "Derrick White": "懷特", "Jrue Holiday": "哈勒戴", 
    "Luka Doncic": "唐西奇", "厄文": "厄文", "Dereck Lively": "萊夫利", 
    "Shai Gilgeous-Alexander": "亞歷山大", "Chet Holmgren": "霍姆格倫", "Jalen Williams": "威廉斯", 
    "Anthony Edwards": "愛德華茲", "Rudy Gobert": "戈貝爾", "Karl-Anthony Towns": "唐斯", 
    "Giannis Antetokounmpo": "字母哥", "Damian Lillard": "里拉德", "Khris Middleton": "米德爾頓", 
    "Stephen Curry": "柯瑞", "Draymond Green": "格林", "Jonathan Kuminga": "庫明加", "Andrew Wiggins": "威金斯", 
    "Kevin Durant": "杜蘭特", "Devin Booker": "布克", "Bradley Beal": "比爾", 
    "Joel Embiid": "恩比德", "Tyrese Maxey": "馬克西", "Paul George": "喬治", 
    "Kawhi Leonard": "雷納德", "James Harden": "哈登", 
    "Jimmy Butler": "巴特勒", "Bam Adebayo": "阿德巴約", 
    "De'Aaron Fox": "福克斯", "Domantas Sabonis": "沙波尼斯" 
} 

# ------------------------ 
# 1 傷兵、數據與盤口引擎 
# ------------------------ 
@st.cache_data(ttl=3600) 
def fetch_injury_raw(): 
    try: 
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get("https://www.cbssports.com/nba/injuries/", headers=headers, timeout=15) 
        return BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True).lower() 
    except: return "" 

def get_injury_impact(team_name, raw_text): 
    if not raw_text: return 0, [], False, []
    mascot = team_name.split()[-1] 
    penalty, reports, has_gtd, out_players = 0, [], False, [] 
    search_key = "76ers" if mascot == "76ers" else mascot 
    t_cn = TEAM_CN.get(team_name, team_name) 
    
    if search_key in STAR_PLAYERS: 
        for player in STAR_PLAYERS[search_key]: 
            full_name = player.lower() 
            if full_name in raw_text: 
                idx = raw_text.find(full_name) 
                chunk = raw_text[idx:idx+250] 
                if any(word in chunk for word in ["out", "expected to be out", "surgery"]): 
                    penalty += 5.0  
                    reports.append(f"🚨 [{t_cn}] {player} - 確定缺陣") 
                    out_players.append(player) 
                elif any(word in chunk for word in ["questionable", "gtd", "decision"]): 
                    penalty += 2.5 
                    reports.append(f"⚠️ [{t_cn}] {player} - 出戰成疑(GTD)") 
                    has_gtd = True 
                    out_players.append(player) 
    return min(penalty, 8.5), reports, has_gtd, out_players 

# 🛡️ 實體檔案快取防護罩：NBA 數據存入本地硬碟，脫掉多餘偽裝
def fetch_nba_master_with_physical_cache(game_date_str): 
    cache_file = f"nba_cache_{game_date_str}.pkl"
    
    # 如果今天已經抓過，直接讀取本地檔案，完全不連線！
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass # 如果檔案損毀，就繼續往下重新抓取

    game_date_obj = datetime.strptime(game_date_str, '%Y-%m-%d')
    date_api_format = game_date_obj.strftime('%m/%d/%Y') 
    yest_str = (game_date_obj - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        team_dict = {t["id"]: t["full_name"] for t in teams.get_teams()} 
        
        # 拿掉所有的 custom_headers 跟 timeout，用 V31.2 最原始能跑的素顏寫法
        sb = scoreboardv2.ScoreboardV2(game_date=game_date_str) 
        games = sb.get_data_frames()[0].drop_duplicates(subset=['GAME_ID']) 
        line_score = sb.get_data_frames()[1] 
        
        sb_yest = scoreboardv2.ScoreboardV2(game_date=yest_str)
        yest_games = sb_yest.get_data_frames()[0]
        
        b2b_data = {}
        for _, y_row in yest_games.iterrows():
            b2b_data[y_row["HOME_TEAM_ID"]] = "Home"
            b2b_data[y_row["VISITOR_TEAM_ID"]] = "Away"
        
        s_h = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Home", date_to_nullable=date_api_format).get_data_frames()[0] 
        
        s_a = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", location_nullable="Road", date_to_nullable=date_api_format).get_data_frames()[0] 
        
        p_stats = leaguedashplayerstats.LeagueDashPlayerStats(measure_type_detailed_defense="Advanced", date_to_nullable=date_api_format).get_data_frames()[0] 
        
        try:
            s_last5 = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Advanced", last_n_games=5, date_to_nullable=date_api_format).get_data_frames()[0]
        except:
            s_last5 = pd.DataFrame()

        result_tuple = (team_dict, games, line_score, s_h, s_a, p_stats, b2b_data, s_last5)
        
        # 抓取成功後，存入本地實體檔案！
        with open(cache_file, "wb") as f:
            pickle.dump(result_tuple, f)
            
        return result_tuple
        
    except Exception as e:
        st.sidebar.error(f"🚨 NBA 伺服器阻擋或逾時，請稍後再試。錯誤細節：{e}")
        return {}, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, pd.DataFrame()

# 🛡️ Odds 盤口檔案快取與額度擷取
def fetch_live_odds(api_key, target_date_str):
    if not api_key: return {}
    
    file_name = f"odds_{target_date_str}.json"
    
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
            
    try:
        url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?apiKey={api_key}&regions=us&markets=spreads,totals&bookmakers=pinnacle"
        r = requests.get(url, timeout=15)
        data = r.json()
        
        # 🔑 抓取 API 剩餘額度並存檔
        with open("api_quota.json", "w", encoding="utf-8") as f:
            json.dump({
                "remaining": r.headers.get('x-requests-remaining', '未知'), 
                "used": r.headers.get('x-requests-used', '未知'), 
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, f)

        # 恢復好讀的盤口解析迴圈
        odds_dict = {}
        for game in data:
            home = game.get('home_team')
            bookies = game.get('bookmakers', [])
            if not bookies: continue
            markets = bookies[0].get('markets', [])
            spread_val, total_val = None, None
            
            for m in markets:
                if m['key'] == 'spreads':
                    for outcome in m['outcomes']:
                        if outcome['name'] == home: spread_val = outcome['point']
                elif m['key'] == 'totals':
                    total_val = m['outcomes'][0]['point']
                    
            odds_dict[home] = {"spread": spread_val, "total": total_val}
            
        if odds_dict:
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump(odds_dict, f, ensure_ascii=False, indent=4)
                
        return odds_dict
    except Exception as e:
        return {}

def calculate_weighted_pie(p_stats_df, team_id, out_players):
    if p_stats_df.empty: return 0
    active_players = p_stats_df[(p_stats_df["TEAM_ID"] == team_id) & (~p_stats_df["PLAYER_NAME"].isin(out_players))]
    core_players = active_players[active_players["MIN"] > 15] 
    if core_players.empty: return 0
    top5 = core_players.nlargest(5, 'PIE')
    weighted_pie = (top5['PIE'] * top5['MIN']).sum() / top5['MIN'].sum()
    return weighted_pie

def run_monte_carlo(h_s, a_s, game_pace, n_sims=10000):
    sim_pace = np.random.normal(loc=game_pace, scale=4.0, size=n_sims)
    h_ppp_mean = h_s / game_pace
    a_ppp_mean = a_s / game_pace
    sim_h_ppp = np.random.normal(loc=h_ppp_mean, scale=0.12, size=n_sims)
    sim_a_ppp = np.random.normal(loc=a_ppp_mean, scale=0.12, size=n_sims)
    
    sim_h_score = sim_pace * sim_h_ppp
    sim_a_score = sim_pace * sim_a_ppp
    
    return sim_h_score - sim_a_score, sim_h_score + sim_a_score

def calculate_ev(win_prob, decimal_odds=1.909):
    return (win_prob * (decimal_odds - 1)) - (1 - win_prob)

# ------------------------ 
# 2 主介面與實戰分析 
# ------------------------ 
st.set_page_config(page_title="NBA AI 攻防大師 V33", layout="wide", page_icon="🏀") 
st.sidebar.header("🗓️ 歷史回測與實戰控制") 
target_date = st.sidebar.date_input("選擇賽事日期", datetime.now() - timedelta(hours=8)) 
formatted_date = target_date.strftime('%Y-%m-%d') 

st.sidebar.divider()
st.sidebar.markdown("### 🤖 The Odds API 授權與額度")
api_key = st.sidebar.text_input("輸入 API 金鑰 (選填)", type="password")

if st.sidebar.button("🔄 強制更新盤口 (清除今日盤口快取)"):
    cache_file = f"odds_{formatted_date}.json"
    if os.path.exists(cache_file):
        os.remove(cache_file)
        st.sidebar.success(f"✅ 已清除盤口快取！")
        time.sleep(1)
        st.rerun()

# 顯示 API 額度追蹤
if os.path.exists("api_quota.json"):
    with open("api_quota.json", "r", encoding="utf-8") as f:
        quota_data = json.load(f)
        st.sidebar.metric("API 剩餘請求次數", f"{quota_data.get('remaining', '未知')} 次")
        st.sidebar.caption(f"已使用: {quota_data.get('used', '未知')} 次")

st.title(f"🏀 NBA AI V33 實體裝甲版: 蒙地卡羅與 EV 決策引擎 ({formatted_date})") 

with st.spinner("啟動系統：優先讀取本地實體檔案，安全隱蔽運行中..."): 
    # 呼叫實體檔案快取版本的抓取函數
    t_dict, games_df, line_df, s_h, s_a, p_stats, b2b_data, s_last5 = fetch_nba_master_with_physical_cache(formatted_date) 
    raw_inj = fetch_injury_raw() 
    live_odds = fetch_live_odds(api_key, formatted_date) if api_key and target_date == (datetime.now() - timedelta(hours=8)).date() else {}

if games_df.empty: 
    st.info("📅 此日期暫無賽程數據，或是檔案建立中遇到阻擋。") 
else: 
    match_data = [] 
    all_ev_opportunities = [] 
    is_historical = target_date < (datetime.now() - timedelta(hours=8)).date() 

    for _, row in games_df.iterrows(): 
        h_id, a_id = row["HOME_TEAM_ID"], row["VISITOR_TEAM_ID"] 
        h_n_en, a_n_en = t_dict.get(h_id), t_dict.get(a_id) 
        h_n, a_n = TEAM_CN.get(h_n_en, h_n_en), TEAM_CN.get(a_n_en, a_n_en) 
        
        try: 
            h_pts_raw = line_df.loc[line_df['TEAM_ID'] == h_id, 'PTS'].values 
            a_pts_raw = line_df.loc[line_df['TEAM_ID'] == a_id, 'PTS'].values 
            h_act = int(float(h_pts_raw[0])) if len(h_pts_raw) > 0 and pd.notna(h_pts_raw[0]) else 0 
            a_act = int(float(a_pts_raw[0])) if len(a_pts_raw) > 0 and pd.notna(a_pts_raw[0]) else 0 
        except: 
            h_act, a_act = 0, 0 
            
        is_finished = (h_act > 0 and a_act > 0 and (h_act + a_act) > 150) 

        h_pen, h_rep, h_gtd, h_out_players = get_injury_impact(h_n_en, raw_inj) 
        a_pen, a_rep, a_gtd, a_out_players = get_injury_impact(a_n_en, raw_inj) 
        
        if is_historical: 
            h_pen, a_pen = h_pen * 0.5, a_pen * 0.5 

        h_is_b2b = h_id in b2b_data
        a_is_b2b = a_id in b2b_data
        
        if h_is_b2b:
            h_pen += 3.5  
            h_rep.append(f"🔋 [{h_n}] 主場背靠背")
        if a_is_b2b:
            a_pen += 4.5
            a_rep.append(f"✈️ [{a_n}] 客場背靠背")

        try: 
            h_d = s_h[s_h["TEAM_ID"] == h_id].iloc[0] 
            a_d = s_a[s_a["TEAM_ID"] == a_id].iloc[0] 
            
            if not s_last5.empty:
                h_l5 = s_last5[s_last5["TEAM_ID"] == h_id]
                a_l5 = s_last5[s_last5["TEAM_ID"] == a_id]
                h_off = (h_d["OFF_RATING"] * 0.7) + (h_l5.iloc[0]["OFF_RATING"] * 0.3) if not h_l5.empty else h_d["OFF_RATING"]
                h_def = (h_d["DEF_RATING"] * 0.7) + (h_l5.iloc[0]["DEF_RATING"] * 0.3) if not h_l5.empty else h_d["DEF_RATING"]
                a_off = (a_d["OFF_RATING"] * 0.7) + (a_l5.iloc[0]["OFF_RATING"] * 0.3) if not a_l5.empty else a_d["OFF_RATING"]
                a_def = (a_d["DEF_RATING"] * 0.7) + (a_l5.iloc[0]["DEF_RATING"] * 0.3) if not a_l5.empty else a_d["DEF_RATING"]
            else:
                h_off, h_def = h_d["OFF_RATING"], h_d["DEF_RATING"]
                a_off, a_def = a_d["OFF_RATING"], a_d["DEF_RATING"]
            
            pace_h = h_d["PACE"]
            pace_a = a_d["PACE"]
            game_pace = (2 * pace_h * pace_a) / (pace_h + pace_a)
            
            h_base_rating = (h_off * 0.65) + (a_def * 0.35) 
            a_base_rating = (a_off * 0.65) + (h_def * 0.35) 
            
            h_pie = calculate_weighted_pie(p_stats, h_id, h_out_players)
            a_pie = calculate_weighted_pie(p_stats, a_id, a_out_players)
            
            h_edge = (h_pie - 12) * 0.4 if h_pie > 12 else 0 
            a_edge = (a_pie - 12) * 0.4 if a_pie > 12 else 0 
            
            h_s = round((h_base_rating * (game_pace/100)) + 2.5 - h_pen + h_edge, 1) 
            a_s = round((a_base_rating * (game_pace/100)) - a_pen + a_edge, 1) 
            
            sim_diff, sim_total = run_monte_carlo(h_s, a_s, game_pace)
            
            prob_win_h = np.mean(sim_diff > 0)
            prob_win_a = 1 - prob_win_h

            api_team_name = ODDS_API_TEAMS.get(h_n_en)
            market_spread = live_odds.get(api_team_name, {}).get("spread")
            market_total = live_odds.get(api_team_name, {}).get("total")

            decision = f"⚠️ 五五波"
            if prob_win_h > 0.55: decision = f"主勝 ({prob_win_h:.1%})"
            elif prob_win_h < 0.45: decision = f"客勝 ({prob_win_a:.1%})"

            if market_spread is not None:
                prob_cover_h = np.mean(sim_diff > -market_spread)
                prob_cover_a = 1 - prob_cover_h
                ev_h = calculate_ev(prob_cover_h)
                ev_a = calculate_ev(prob_cover_a)
                
                if ev_h > 0:
                    all_ev_opportunities.append({
                        "對戰組合": f"{a_n} @ {h_n}", "開盤": f"主 {market_spread}", 
                        "推薦": f"{h_n}", "不讓分勝率": f"{prob_win_h:.1%}", "過盤率": f"{prob_cover_h:.1%}", "EV": ev_h
                    })
                if ev_a > 0:
                    all_ev_opportunities.append({
                        "對戰組合": f"{a_n} @ {h_n}", "開盤": f"客 {-market_spread}", 
                        "推薦": f"{a_n}", "不讓分勝率": f"{prob_win_a:.1%}", "過盤率": f"{prob_cover_a:.1%}", "EV": ev_a
                    })

            hit = "待定" 
            if is_finished: 
                if market_spread is not None:
                    if "主" in decision and (h_act - a_act > -market_spread): hit = "✅"
                    elif "客" in decision and (h_act - a_act < -market_spread): hit = "✅"
                    else: hit = "❌"
                else:
                    hit = "✅" if (prob_win_h > 0.5 and h_act > a_act) or (prob_win_h < 0.5 and h_act < a_act) else "❌" 

            match_data.append({ 
                "對戰組合": f"{a_n} @ {h_n}", 
                "AI淨勝分(客:主)": f"{a_s} : {h_s}", 
                "主隊勝率(PK)": f"{prob_win_h:.1%}",
                "市場讓分(主)": market_spread if market_spread is not None else "-",
                "最佳 EV 決策": decision,
                "實際比分": f"{a_act} : {h_act}" if is_finished else "-", 
                "勝負命中": hit, 
                "h_s": h_s, "a_s": a_s, "game_pace": game_pace, "reports": h_rep + a_rep,
                "is_finished": is_finished
            }) 
        except Exception as e: 
            continue 

    if all_ev_opportunities:
        st.header("🔥 今日 TOP 5 價值投注 (結合 V31 高精準模型)")
        ev_df = pd.DataFrame(all_ev_opportunities).sort_values(by="EV", ascending=False).head(5)
        ev_df["EV"] = ev_df["EV"].apply(lambda x: f"+{x:.1%}")
        st.dataframe(ev_df, use_container_width=True)

    if match_data: 
        done = [m for m in match_data if m["is_finished"]] 
        done_valid = [m for m in done if m["勝負命中"] in ["✅", "❌"]]
        
        if done_valid: 
            rate = sum(1 for m in done_valid if m["勝負命中"] == "✅") / len(done_valid) 
            st.sidebar.metric("🎯 本日策略命中率", f"{rate:.1%}") 

        st.divider() 
        st.header("📊 蒙地卡羅 EV 決策總表 (10,000 次模擬)") 
        display_df = pd.DataFrame(match_data)[["對戰組合", "AI淨勝分(客:主)", "主隊勝率(PK)", "市場讓分(主)", "最佳 EV 決策", "實際比分", "勝負命中"]]
        st.dataframe(display_df, use_container_width=True) 

        st.divider() 
        st.header("🔍 蒙地卡羅深度解析儀") 
        s_g = st.selectbox("請選擇分析場次：", match_data, format_func=lambda x: x["對戰組合"]) 
        col_a, col_b = st.columns(2) 
        
        with col_a: 
            st.subheader("📝 陣容報告") 
            if s_g["reports"]: 
                for r in s_g["reports"]:
                    if "🚨" in r:
                        st.error(r)
                    else:
                        st.warning(r)
            else:
                st.success("✅ 目前無重大傷病。") 
            
        with col_b: 
            st.subheader("🎲 動態 EV 模擬") 
            u_spread = st.number_input("主隊讓分", value=-4.5, step=0.5) 
            u_total = st.number_input("總分盤口", value=225.5, step=0.5) 
            
            sd, stotal = run_monte_carlo(s_g['h_s'], s_g['a_s'], s_g['game_pace'])
            pc_h, pc_a = np.mean(sd > -u_spread), np.mean(sd < -u_spread)
            po, pu = np.mean(stotal > u_total), np.mean(stotal < u_total)
            
            st.write(f"主過盤率: `{pc_h:.1%}` | EV: `{calculate_ev(pc_h):.1%}`")
            st.write(f"客過盤率: `{pc_a:.1%}` | EV: `{calculate_ev(pc_a):.1%}`")
            st.divider()
            st.write(f"大分率: `{po:.1%}` | 小分率: `{pu:.1%}`")

st.caption("NBA AI V33 - 實體裝甲版：物理檔案快取、API 額度追蹤、恢復 V31 核心高準度預測模型 (修復語法衝突)")

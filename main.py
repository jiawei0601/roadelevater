# app.py (調整後的版本)

import streamlit as st
import pandas as pd
import gspread
from scipy.interpolate import interp1d

# --- 1. Google Sheets 連接與讀取 (與之前相同，但讀取所有欄位) ---
@st.cache_data(ttl=600)
def load_data_from_gsheet():
    # 略... 保持 gspread 連接部分的程式碼不變
    # 假設這段程式碼成功返回包含 'Road Name', 'Distance (m)', 'Elevation (m)' 的 DataFrame
    
    try:
        # ⚠️ 請替換為您的 Google Sheet 檔案名稱
        SHEET_TITLE = "您的道路高程資料表"
        WORKSHEET_NAME = "Sheet1" 
        gc = gspread.service_account(filename="service_account.json")
        sh = gc.open(SHEET_TITLE)
        worksheet = sh.worksheet(WORKSHEET_NAME)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 確保關鍵資料是數值類型
        df['Distance (m)'] = pd.to_numeric(df['Distance (m)'], errors='coerce')
        df['Elevation (m)'] = pd.to_numeric(df['Elevation (m)'], errors='coerce')
        df.dropna(subset=['Road Name', 'Distance (m)', 'Elevation (m)], inplace=True)
        
        return df
        
    except Exception as e:
        st.error(f"無法讀取 Google Sheet 資料：{e}")
        return pd.DataFrame()

# --- 2. 內插求值函式 (保持不變) ---
def interpolate_elevation(df_single_road, target_distance):
    # 此處 df_single_road 必須只包含一條路的資料
    f = interp1d(df_single_road['Distance (m)'], df_single_road['Elevation (m)'], 
                 kind='linear', fill_value="extrapolate")
    return f(target_distance)

# --- 3. Streamlit 介面 (主要修改區) ---
def main():
    st.set_page_config(page_title="多道路高程內插工具", layout="wide")
    st.title("🛣️ 多道路高程內插查找工具")
    
    data_df = load_data_from_gsheet()
    
    if data_df.empty:
        st.warning("資料載入失敗或資料為空，請檢查 Google Sheet 設定。")
        return
        
    # --- A. 選擇道路介面 ---
    st.sidebar.header("🛠️ 道路選擇")
    
    # 獲取所有不重複的路名
    road_names = data_df['Road Name'].unique().tolist()
    
    if not road_names:
        st.error("Google Sheet 中沒有找到 'Road Name' 資料。")
        return
        
    # 讓使用者選擇一條道路
    selected_road = st.sidebar.selectbox(
        "請選擇要進行高程內插的道路:",
        options=road_names
    )
    
    # --- B. 篩選資料 ---
    # 僅篩選出使用者選擇的道路資料
    filtered_df = data_df[data_df['Road Name'] == selected_road].sort_values('Distance (m)')
    
    if filtered_df.empty:
        st.error(f"找不到 {selected_road} 的高程資料。")
        return

    # --- C. 介面顯示與計算 ---
    st.subheader(f"✅ 當前選定道路: **{selected_road}**")
    
    st.dataframe(filtered_df[['Distance (m)', 'Elevation (m)']].head())
    
    max_dist = filtered_df['Distance (m)'].max()
    min_dist = filtered_df['Distance (m)'].min()
    
    st.markdown(f"*道路距離範圍: 從 **{min_dist:.2f} m** 到 **{max_dist:.2f} m***")
    
    st.markdown("---")

    # 讓使用者輸入目標距離
    target_distance = st.number_input(
        "請輸入您要查找的目標距離 (m):",
        min_value=min_dist,
        max_value=max_dist,
        value=(min_dist + max_dist) / 2, 
        step=0.1
    )
    
    # 進行計算
    if st.button(f"計算 {selected_road} 上的內插高程"):
        with st.spinner('正在計算中...'):
            try:
                result_elevation = interpolate_elevation(filtered_df, target_distance)
                
                st.success("✅ 計算完成！")
                st.metric(
                    label=f"在 **{target_distance:.2f} m** 處的內插高程",
                    value=f"{result_elevation:.2f} m"
                )
                
            except Exception as e:
                st.error(f"計算錯誤：{e}")

if __name__ == "__main__":
    main()

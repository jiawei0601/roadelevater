import streamlit as st
import pandas as pd
import gspread
from scipy.interpolate import interp1d
import plotly.express as px # 用於繪製互動式圖表

# --- 1. Google Sheets 連接與讀取 ---
# 使用 st.cache_data 確保數據只在需要時重新載入，加快應用程式速度
@st.cache_data(ttl=600)
def load_data_from_gsheet():
    """
    連接 Google Sheet 並讀取高程資料。
    
    ⚠️ 注意: 此版本使用 st.secrets 從 Streamlit Cloud 環境讀取授權資訊。
    """
    try:
        # 替換為您的 Google Sheet 檔案名稱和工作表名稱
        SHEET_TITLE = "道路高程資料表"
        WORKSHEET_NAME = "Sheet1" 
        
        # 🌟 關鍵修改點：從 st.secrets 讀取 Service Account 憑證
        # 憑證名稱 'gdrive_service_account' 必須與您在 Streamlit Secrets 中設定的名稱一致
        if "gdrive_service_account" not in st.secrets:
             st.error("錯誤：Streamlit Secrets 中未找到 'gdrive_service_account' 設定。請檢查 Streamlit Cloud Secrets 配置。")
             return pd.DataFrame()
        
        # 使用字典憑證進行認證
        gc = gspread.service_account_from_dict(st.secrets["gdrive_service_account"])
        sh = gc.open(SHEET_TITLE)
        worksheet = sh.worksheet(WORKSHEET_NAME)
        
        # 讀取所有資料並轉換為 DataFrame
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 確保關鍵資料是正確的類型
        # 'Road Name' (字串), 'Distance (m)' (數值), 'Elevation (m)' (數值)
        df['Distance (m)'] = pd.to_numeric(df['Distance (m)'], errors='coerce')
        df['Elevation (m)'] = pd.to_numeric(df['Elevation (m)'], errors='coerce')
        
        # 確保三個關鍵欄位都有值
        df.dropna(subset=['Road Name', 'Distance (m)', 'Elevation (m)'], inplace=True)
        
        if df.empty:
             st.error("Google Sheet 載入成功，但處理後資料為空。請檢查欄位名稱和資料格式。")
             return pd.DataFrame()

        return df
        
    except Exception as e:
        # 捕捉 Gspread 可能的認證或連接錯誤
        st.error(f"Google Sheet 連接或讀取失敗。請檢查授權（共享給服務帳號的郵箱）和 Sheet 名稱。詳細錯誤：{e}")
        return pd.DataFrame()

# --- 2. 內插求值函式 ---
def interpolate_elevation(df_single_road, target_distance):
    """
    對給定的距離進行線性內插，求出高程。
    """
    # 建立內插函式：使用 'linear' 線性內插
    f = interp1d(df_single_road['Distance (m)'], df_single_road['Elevation (m)'], 
                 kind='linear', fill_value="extrapolate")
    
    # 進行內插
    interpolated_value = f(target_distance).item() # .item() 確保返回單一數值
    
    return interpolated_value

# --- 3. Streamlit 介面與主邏輯 ---
def main():
    st.set_page_config(page_title="道路高程內插工具", layout="wide")
    st.title("🛣️ Google Sheet 道路高程內插查找工具")
    
    # 載入資料
    data_df = load_data_from_gsheet()
    
    if data_df.empty:
        # 如果資料載入失敗或為空，則終止程式運行
        return
        
    # --- 側邊欄：道路選擇 ---
    st.sidebar.header("🛠️ 道路選擇與資料概覽")
    
    road_names = data_df['Road Name'].unique().tolist()
    
    selected_road = st.sidebar.selectbox(
        "請選擇要進行高程內插的道路:",
        options=road_names,
        index=0
    )
    
    # 篩選資料：僅保留選定道路的數據，並按距離排序
    filtered_df = data_df[data_df['Road Name'] == selected_road].sort_values('Distance (m)')
    
    if filtered_df.empty:
        st.error(f"找不到 {selected_road} 的高程資料。")
        return
        
    max_dist = filtered_df['Distance (m)'].max()
    min_dist = filtered_df['Distance (m)'].min()

    # 顯示選定道路的資料概覽
    st.sidebar.markdown(f"**資料點數:** {len(filtered_df)}")
    st.sidebar.markdown(f"**距離範圍:** {min_dist:.2f} m ~ {max_dist:.2f} m")
    st.sidebar.dataframe(filtered_df[['Distance (m)', 'Elevation (m)']].head(5))

    st.subheader(f"✅ 當前選定道路: **{selected_road}**")
    
    # --- 主區域：使用者輸入與計算 ---
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### 🔍 查找目標距離")
        
        # 讓使用者輸入目標距離
        target_distance = st.number_input(
            "請輸入您要查找的目標距離 (m):",
            min_value=min_dist,
            max_value=max_dist,
            value=min_dist + (max_dist - min_dist) / 4, # 預設值為 1/4 處
            step=0.1,
            format="%.2f"
        )
        
        interpolated_elevation = None
        
        # 進行計算
        if st.button(f"計算內插高程", use_container_width=True):
            with st.spinner('正在計算中...'):
                try:
                    interpolated_elevation = interpolate_elevation(filtered_df, target_distance)
                    
                    st.success("✅ 計算完成！")
                    st.metric(
                        label=f"在 **{target_distance:.2f} m** 處的內插高程",
                        value=f"{interpolated_elevation:.2f} m"
                    )
                    
                except Exception as e:
                    st.error(f"計算錯誤：請確保該距離在資料範圍內且數據有效。詳細錯誤：{e}")
        
    with col2:
        st.markdown("### 📊 道路高程剖面圖")

        # 創建一個 Plotly 圖表
        fig = px.line(
            filtered_df,
            x='Distance (m)',
            y='Elevation (m)',
            title=f"道路高程剖面圖: {selected_road}",
            markers=True
        )

        # 如果已經計算出內插值，則將內插點添加到圖表上
        if interpolated_elevation is not None:
            # 建立一個包含內插點的 DataFrame
            interp_point = pd.DataFrame({
                'Distance (m)': [target_distance],
                'Elevation (m)': [interpolated_elevation],
                'Point Type': ['內插點']
            })
            
            # 將內插點作為散點圖層疊加
            fig.add_scatter(
                x=interp_point['Distance (m)'],
                y=interp_point['Elevation (m)'],
                mode='markers',
                name='內插點',
                marker=dict(size=12, color='red', symbol='star'),
                hovertext=f"距離: {target_distance:.2f} m<br>高程: {interpolated_elevation:.2f} m"
            )

        # 顯示圖表
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()

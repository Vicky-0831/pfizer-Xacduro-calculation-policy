import streamlit as st
import pandas as pd
import altair as alt
import re

# 页面配置
st.set_page_config(page_title="X药2026模拟器", layout="wide")

# --- 终极 CSS 样式 (保持不变) ---
st.markdown("""
    <style>
    /* 1. 输入框容器样式 */
    div[data-baseweb="input"] {
        background-color: #EBF5FB !important;
        border: 1px solid #EBF5FB !important;
        border-radius: 5px !important;
    }
    /* 2. 内部透明 */
    div[data-baseweb="input"] > div,
    div[data-baseweb="input"] input {
        background-color: transparent !important;
        color: #000000 !important;
        font-weight: 500;
    }
    /* 3. 锁定状态 */
    div[data-baseweb="input"]:has(input:disabled) {
        background-color: #f0f2f6 !important;
        border: 1px solid rgba(49, 51, 63, 0.2) !important;
        opacity: 0.6;
    }
    div[data-baseweb="input"] input:disabled {
        color: #666666 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 智能数据加载函数 (修复读取报错) ---
@st.cache_data
def load_policy_data():
    default_file = 'policy_data.xlsx'
    
    def search_and_load(source):
        try:
            xl = pd.ExcelFile(source)
            # 遍历所有 Sheet，寻找包含"省份"的那一个
            for sheet_name in xl.sheet_names:
                # 先读前10行探探路
                df_preview = pd.read_excel(source, sheet_name=sheet_name, header=None, nrows=10)
                
                header_idx = -1
                # 寻找哪一行是表头
                for idx, row in df_preview.iterrows():
                    row_values = [str(x).strip() for x in row.values]
                    if '省份' in row_values and '保险名称' in row_values:
                        header_idx = idx
                        break
                
                if header_idx != -1:
                    # 找到了！正式读取
                    df = pd.read_excel(source, sheet_name=sheet_name, header=header_idx)
                    # 清洗列名
                    df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
                    
                    # 标准化列名，防止 Excel 里写的是"起付线"而不是"起付线/年"
                    rename_map = {}
                    for c in df.columns:
                        if '起付线' in c: rename_map[c] = '起付线'
                        if '报销' in c and '比例' in c: rename_map[c] = '报销比例'
                        if 'X药' in c and '报销' in c: rename_map[c] = 'X药覆盖'
                    
                    df = df.rename(columns=rename_map)
                    
                    # 确保关键列存在
                    required = ['省份', '城市', '保险名称']
                    if all(r in df.columns for r in required):
                        # 简单的缺失值填充
                        df['省份'] = df['省份'].fillna('其他')
                        df['城市'] = df['城市'].fillna('通用')
                        return df
            return pd.DataFrame() # 没找到合适的表
        except Exception:
            return pd.DataFrame()

    try:
        df = search_and_load(default_file)
        # 如果本地没找到，允许用户上传（调试用）
        if df.empty:
            return pd.DataFrame()
        return df
    except:
        return pd.DataFrame()

def parse_deductible(val):
    """解析起付线，返回浮点数"""
    if pd.isna(val): return 20000.0
    text = str(val)
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        num = float(match.group(1))
        if '万' in text or 'w' in text.lower(): return num * 10000
        if num < 100: return num * 10000 # 猜测单位是万
        return num
    return 20000.0

def parse_rate(val):
    """解析报销比例，返回百分数数值 (如 60.0)"""
    if pd.isna(val): return 60.0
    text = str(val)
    match_pct = re.search(r'(\d+(\.\d+)?)%', text)
    if match_pct: return float(match_pct.group(1))
    match_dec = re.search(r'0\.(\d+)', text)
    if match_dec: return float("0." + match_dec.group(1)) * 100
    return 60.0

# 加载数据
df_policy = load_policy_data()

st.title("X药2026多重支付商保模拟计算器")
st.markdown("---")

col1, col2 = st.columns([1, 1.5])

with col1:
    # --- A. 用药参数 ---
    st.subheader("A. 用药参数")
    st.info("基础信息设置")
    
    price_per_box = st.number_input("药品单价 (元/盒)", value=3179, disabled=True, help="单价已锁定标准价格")
    daily_usage = st.number_input("一日使用盒数", value=4) 
    days_usage = st.number_input("用药天数", value=7, step=1)
    
    total_cost = price_per_box * daily_usage * days_usage
    st.write(f"**当前周期总费用:** ¥{total_cost:,.0f}")
    
    st.markdown("---")
    
    # --- B. 保障参数 ---
    st.subheader("B. 保障参数")
    st.info("多重支付设置")
    
    st.write("**第1重保障：惠民保**")
    is_huiminbao = st.checkbox("参加当地惠民保", value=True)
    
    # 默认值
    default_deductible = 20000.0
    default_rate = 60.0
    selected_prod_id = "default" # 用于控制输入框刷新的 Key
    
    # --- [自动化选择区域] ---
    if is_huiminbao and not df_policy.empty:
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            provinces = ['(请选择)'] + sorted(list(df_policy['省份'].unique()))
            sel_prov = st.selectbox("省份", provinces, label_visibility="collapsed")
        with c_sel2:
            if sel_prov != '(请选择)':
                cities = sorted(list(df_policy[df_policy['省份']==sel_prov]['城市'].unique()))
                sel_city = st.selectbox("城市", cities, label_visibility="collapsed")
            else:
                sel_city = None
                st.selectbox("城市", ["-"], disabled=True, label_visibility="collapsed")
        
        if sel_prov != '(请选择)' and sel_city:
            # 筛选产品
            prod_rows = df_policy[(df_policy['省份']==sel_prov) & (df_policy['城市']==sel_city)]
            prod_names = prod_rows['保险名称'].unique()
            sel_prod = st.selectbox("具体产品", prod_names)
            
            # 获取数值
            if sel_prod:
                row = prod_rows[prod_rows['保险名称'] == sel_prod].iloc[0]
                default_deductible = parse_deductible(row.get('起付线'))
                default_rate = parse_rate(row.get('报销比例'))
                
                # 关键：生成一个基于产品名的 Key
                # 只要 sel_prod 变了，selected_prod_id 就变，输入框就会重置为新的默认值
                selected_prod_id = f"{sel_prov}_{sel_city}_{sel_prod}"
                
                # 显示政策小字
                is_cover = row.get('X药覆盖', '需确认')
                raw_info = f"起付线: {row.get('起付线', '-')} | 比例: {row.get('报销比例', '-')}"
                st.caption(f"📋 {sel_prod}: X药覆盖 [{is_cover}]")
                st.caption(f"ℹ️ 参考条款: {raw_info}")

    # --- 输入框 (支持自动更新 + 手动修改) ---
    c1, c2 = st.columns(2)
    with c1:
        # key 变化时，value 生效；key 不变时，用户修改生效
        hmb_deductible = st.number_input(
            "惠民保起付线", 
            value=default_deductible, 
            step=1000.0,
            key=f"deductible_{selected_prod_id}" 
        )
    with c2:
        hmb_rate_input = st.number_input(
            "报销比例 (%)", 
            value=default_rate, 
            step=5.0,
            key=f"rate_{selected_prod_id}"
        )
        hmb_rate = hmb_rate_input / 100.0
        
    st.markdown("---")
    st.write("**第2重保障：双坦同行项目**")
    is_shuangtan = st.checkbox("参加双坦同行项目", value=True)
    shuangtan_rate = 0.5 
    st.caption("说明：双坦项目直接报销总费用的 50%")

with col2:
    st.subheader("结果输出 (模拟测算)")
    
    # --- 计算逻辑 ---
    if total_cost > hmb_deductible:
        reimburse_hmb_val = (total_cost - hmb_deductible) * hmb_rate
    else:
        reimburse_hmb_val = 0.0
        
    if not is_huiminbao:
        reimburse_hmb_val = 0.0

    reimburse_st_val = total_cost * shuangtan_rate if is_shuangtan else 0.0
    
    # --- 准备图表数据 ---
    cost_scenario_1 = total_cost
    
    cost_scenario_2 = total_cost - reimburse_hmb_val
    if cost_scenario_2 < 0: cost_scenario_2 = 0
    
    total_reimb_both = reimburse_hmb_val + reimburse_st_val
    cost_scenario_3 = total_cost - total_reimb_both
    if cost_scenario_3 < 0: cost_scenario_3 = 0
    
    # --- 顶部大数字 ---
    current_reimburse = 0
    if is_huiminbao: current_reimburse += reimburse_hmb_val
    if is_shuangtan: current_reimburse += reimburse_st_val
    
    if current_reimburse > total_cost: current_reimburse = total_cost
    current_final_cost = total_cost - current_reimburse
    
    daily_avg_cost = current_final_cost / days_usage if days_usage > 0 else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("本周期总费用", f"¥{total_cost:,.0f}")
    m2.metric("当前报销合计", f"¥{current_reimburse:,.0f}", delta=f"省下 {current_reimburse/total_cost:.1%}" if total_cost>0 else None)
    m3.metric("患者最终自付", f"¥{current_final_cost:,.0f}", delta_color="inverse")
    
    # --- 结论行 ---
    st.markdown(f"""
    <div style='background-color: #dcebf7; padding: 10px; border-radius: 5px; margin-top: 10px; text-align: center; color: #0e1117;'>
        <span style='font-size: 16px; font-weight: bold;'>
            💡 多重保障后，患者用药治疗 <span style='color:#27ae60'>{int(days_usage)}</span> 天，日治疗费用：<span style='color:#27ae60'>¥{daily_avg_cost:,.0f}</span> 元
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # --- 图表：费用分担对比 ---
    st.write("### 📊 费用分担对比 (双重保障)")
    
    label_1 = '全额自费'
    label_2 = '参加地方惠民保'
    label_3 = '惠民保+双坦同行'
    
    chart_data = pd.DataFrame({
        '情景': [label_1, label_2, label_3],
        '患者自付费用': [cost_scenario_1, cost_scenario_2, cost_scenario_3],
        '标签': [f'¥{cost_scenario_1:,.0f}', f'¥{cost_scenario_2:,.0f}', f'¥{cost_scenario_3:,.0f}']
    })
    
    max_val = chart_data['患者自付费用'].max() * 1.2
    
    # 手机端优化：禁用 tooltip 和 interactive
    base = alt.Chart(chart_data).encode(
        x=alt.X('患者自付费用', title='患者自付费用（元）', scale=alt.Scale(domain=[0, max_val])),
        y=alt.Y('情景', sort=None, title=None), 
    )
    bars = base.mark_bar(size=40).encode(
        color=alt.Color('情景', scale=alt.Scale(
            domain=[label_1, label_2, label_3],
            range=['#e74c3c', '#3498db', '#27ae60'] 
        ), legend=None)
    )
    
    text = base.mark_text(
        align='left',
        baseline='middle',
        dx=5,
        color='black'
    ).encode(
        text='标签'
    )
    final_chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(final_chart, use_container_width=True)
    
    st.info(f"📉 **节省统计：** 相比全额自费，该方案预计共为您节省 **¥{(cost_scenario_1 - cost_scenario_3):,.0f}** 元。")

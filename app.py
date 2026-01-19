import streamlit as st
import pandas as pd
import altair as alt
import re
import os

# --- 1. 页面配置 ---
st.set_page_config(page_title="X药2026双重支付商保模拟计算器", layout="wide")

# --- 2. 终极 CSS 样式 ---
st.markdown("""
    <style>
    /* 全局字体优化 */
    .big-font { font-size: 24px !important; font-weight: bold; color: #000000; }
    .highlight-green { color: #27ae60; font-weight: bold; }
    
    /* 输入框样式 */
    div[data-baseweb="input"] {
        background-color: #EBF5FB !important;
        border: 1px solid #EBF5FB !important;
        border-radius: 5px !important;
    }
    div[data-baseweb="input"] > div,
    div[data-baseweb="input"] input {
        background-color: transparent !important;
        color: #000000 !important;
        font-weight: 500;
    }
    div[data-baseweb="input"]:has(input:disabled) {
        background-color: #f0f2f6 !important;
        opacity: 0.6;
    }
    .small-header { font-size: 14px; color: #999; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 数据加载函数 (读取 Excel) ---
@st.cache_data
def load_policy_data():
    # 1. 动态获取 app.py 所在的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. 拼接出 Excel 的完整路径
    excel_file = os.path.join(current_dir, 'policy.xlsx')
    
    try:
        # 打印一下路径，方便调试（你看终端就能看到）
        print(f"正在读取文件: {excel_file}")
        
        xl = pd.ExcelFile(excel_file)
        for sheet in xl.sheet_names:
            df_preview = pd.read_excel(excel_file, sheet_name=sheet, header=None, nrows=10)
            header_idx = -1
            for idx, row in df_preview.iterrows():
                row_str = row.astype(str).values
                if '省份' in row_str and '保险名称' in row_str:
                    header_idx = idx
                    break
            
            if header_idx != -1:
                df = pd.read_excel(excel_file, sheet_name=sheet, header=header_idx)
                df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
                if '省份' in df.columns: df['省份'] = df['省份'].fillna('其他')
                if '城市' in df.columns: df['城市'] = df['城市'].fillna('通用')
                return df
                
        st.error("❌ Excel 读取成功，但未找到包含'省份'的表头。")
        return pd.DataFrame()
        
    except FileNotFoundError:
        st.error(f"❌ 依然找不到文件: {excel_file}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ 读取错误: {e}")
        return pd.DataFrame()

def parse_deductible(val):
    if pd.isna(val): return 20000.0
    text = str(val)
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        num = float(match.group(1))
        if '万' in text or 'w' in text.lower(): return num * 10000
        if num < 100: return num * 10000
        return num
    return 20000.0

def parse_rate(val):
    if pd.isna(val): return 60.0
    text = str(val)
    match_pct = re.search(r'(\d+(\.\d+)?)%', text)
    if match_pct: return float(match_pct.group(1))
    match_dec = re.search(r'0\.(\d+)', text)
    if match_dec: return float("0." + match_dec.group(1)) * 100
    return 60.0

# 加载数据
df_policy = load_policy_data()

# --- 4. 主界面 ---

st.title("X药2026双重支付商保模拟计算器")
st.markdown("""
<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; font-size: 12px; color: #856404; margin-bottom: 20px;'>
    <strong>⚠️ Disclaimer:</strong> 计算器仅限内部使用，该项目仅考虑患者使用X药且不涵盖其他项目费用，计算金额仅供参考，实际情况以医院为准。
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1.5])

with col1:
    # A. 基础信息
    st.markdown("<div class='small-header'>基础信息设置</div>", unsafe_allow_html=True)
    with st.container():
        c_p1, c_p2 = st.columns([1, 2])
        with c_p1:
             price_per_box = st.number_input("药品单价", value=3179, disabled=True, label_visibility="collapsed")
        with c_p2:
             st.caption("元/盒 (已锁定标准价格)")

        c_a1, c_a2 = st.columns(2)
        with c_a1:
            daily_usage = st.number_input("一日使用盒数", value=4) 
        with c_a2:
            days_usage = st.number_input("用药天数", value=7, step=1)
            
        total_cost = price_per_box * daily_usage * days_usage
        st.markdown(f"<div style='margin-top:10px; font-size:16px;'>当前周期预计总费用: <span class='big-font'>¥{total_cost:,.0f}</span></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # B. 双重保障设置
    st.subheader("双重保障设置")
    
    # 方案切换
    calc_mode = st.radio(
        "请选择报销结算顺序：",
        ("方案一：先惠民保 -> 再双坦", "方案二：先双坦 -> 再惠民保"),
        index=0
    )
    is_hmb_first = "方案一" in calc_mode
    
    st.markdown("---")
    
    # 1. 惠民保
    st.write("**第1重保障：惠民保** (信息更新时间：2026AP1)")
    is_huiminbao = st.checkbox("参加当地惠民保", value=True)
    
    default_deductible = 20000.0
    default_rate = 60.0
    selected_prod_id = "default"
    
    if is_huiminbao and not df_policy.empty:
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            provinces = ['(请选择)'] + sorted([str(x) for x in df_policy['省份'].unique() if pd.notna(x)])
            sel_prov = st.selectbox("省份", provinces, label_visibility="collapsed")
        with c_sel2:
            if sel_prov != '(请选择)':
                cities = sorted([str(x) for x in df_policy[df_policy['省份']==sel_prov]['城市'].unique() if pd.notna(x)])
                sel_city = st.selectbox("城市", cities, label_visibility="collapsed")
            else:
                sel_city = None
                st.selectbox("城市", ["-"], disabled=True, label_visibility="collapsed")
        
        if sel_prov != '(请选择)' and sel_city:
            prod_rows = df_policy[(df_policy['省份']==sel_prov) & (df_policy['城市']==sel_city)]
            prod_names = prod_rows['保险名称'].unique()
            sel_prod = st.selectbox("具体产品", prod_names)
            
            if sel_prod:
                row = prod_rows[prod_rows['保险名称'] == sel_prod].iloc[0]
                
                # 智能提取数值
                # 兼容可能的列名变化
                def get_col(candidates):
                    for c in candidates:
                        if c in row: return row[c]
                    return None
                    
                val_deduct = get_col(['起付线/年', '起付线'])
                val_rate = get_col(['报销比例'])
                
                default_deductible = parse_deductible(val_deduct)
                default_rate = parse_rate(val_rate)
                selected_prod_id = f"{sel_prov}_{sel_city}_{sel_prod}"
                
                # 条款提取
                def safe_get(key_part):
                    for col in df_policy.columns:
                        if key_part in col: return str(row[col])
                    return '-'

                ref_txt = f"""
                <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 10px; color: #000; font-size: 13px;">
                    <strong>📋 参考条款 ({sel_prod})</strong><br>
                    • <strong>投保期:</strong> {safe_get('投保期间（起）')} 至 {safe_get('投保期间（止）')}<br>
                    • <strong>保障期:</strong> {safe_get('保障期间（起）')} 至 {safe_get('保障期间（止）')}<br>
                    • <strong>保费:</strong> {safe_get('保费')} | <strong>结算:</strong> {safe_get('报销结算方式')}<br>
                    • <strong>核心条款:</strong> 起付线 {safe_get('起付线')} | 比例 {safe_get('报销比例')} | 封顶 {safe_get('封顶线')}
                </div>
                """
                st.markdown(ref_txt, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        hmb_deductible = st.number_input("惠民保起付线", value=default_deductible, step=1000.0, key=f"d_{selected_prod_id}")
    with c2:
        hmb_rate_input = st.number_input("报销比例 (%)", value=default_rate, step=5.0, key=f"r_{selected_prod_id}")
        hmb_rate = hmb_rate_input / 100.0
        st.markdown("<div style='font-size:12px; color:#666;'>具体情况可根据自己实际修改</div>", unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 2. 双坦
    st.write("**第2重保障：双坦同行项目**")
    is_shuangtan = st.checkbox("参加双坦同行项目", value=True)
    shuangtan_rate = 0.5 
    st.caption("说明：双坦项目报销自付总费用的 50%")

with col2:
    st.subheader("结果输出 (模拟测算)")
    
    # --- 核心计算 ---
    st_val = 0.0
    hmb_val = 0.0
    
    if is_hmb_first:
        # 方案一：先惠民保 -> 后双坦
        if is_huiminbao:
            if total_cost > hmb_deductible:
                hmb_val = (total_cost - hmb_deductible) * hmb_rate
        
        balance = total_cost - hmb_val
        if is_shuangtan:
            st_val = balance * shuangtan_rate
            
    else:
        # 方案二：先双坦 -> 后惠民保
        if is_shuangtan:
            st_val = total_cost * shuangtan_rate
            
        balance = total_cost - st_val
        if is_huiminbao:
            if balance > hmb_deductible:
                hmb_val = (balance - hmb_deductible) * hmb_rate
                
    final_reimb = st_val + hmb_val
    if final_reimb > total_cost: final_reimb = total_cost
    final_pay = total_cost - final_reimb
    
    # --- 展示 ---
    daily_avg = final_pay / days_usage if days_usage > 0 else 0
    total_saved = total_cost - final_pay
    
    m1, m2, m3 = st.columns(3)
    m1.metric("当前周期预计总费用", f"¥{total_cost:,.0f}")
    
    # 绿色文字，无箭头符号干扰
    m2.markdown(f"""
    <div style="font-size: 14px; color: #555;">当前报销合计</div>
    <div style="font-size: 24px; font-weight: bold; color: #000;">¥{total_saved:,.0f}</div>
    <div style="color: #27ae60; font-weight: bold;">↓ 省下 {total_saved/total_cost:.1%}</div>
    """, unsafe_allow_html=True)
    
    m3.metric("患者最终自付", f"¥{final_pay:,.0f}", delta_color="inverse")
    
    # 结论
    st.markdown(f"""
    <div style='background-color: #dcebf7; padding: 15px; border-radius: 8px; margin-top: 10px; text-align: center; color: #0e1117;'>
        <span style='font-size: 18px;'>
            💡 多重保障后，患者用药治疗 <b>{int(days_usage)}</b> 天<br>
            日治疗费用：<span style='color:#27ae60; font-size: 26px; font-weight: bold;'>¥{daily_avg:,.0f}</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # --- 图表 ---
    st.write("### 📊 自付费用对比")
    
    # 场景1：全自费
    c1 = total_cost
    # 场景2：参考 (仅惠民保)
    if is_huiminbao and total_cost > hmb_deductible:
        c2 = total_cost - (total_cost - hmb_deductible) * hmb_rate
    else:
        c2 = total_cost
    # 场景3：当前
    c3 = final_pay
    
    chart_df = pd.DataFrame({
        '情景': ['全额自费', '参加地方惠民保', '惠民保+双坦同行'],
        '费用': [c1, c2, c3],
        '标签': [f'¥{c1:,.0f}', f'¥{c2:,.0f}', f'¥{c3:,.0f}']
    })
    
     max_val = chart_df['费用'].max() * 1.1
    
    base = alt.Chart(chart_df).encode(
        y=alt.Y('情景', sort=['全额自费', '参加地方惠民保', '惠民保+双坦同行'], title=None),
        x=alt.X('费用', title='自付费用', scale=alt.Scale(domain=[0, max_val]))
    )
    bars = base.mark_bar(size=40).encode(
        color=alt.Color('情景', scale=alt.Scale(range=['#e74c3c', '#3498db', '#27ae60']), legend=None)
    )
    text = base.mark_text(dx=5, align='left', color='black').encode(text='标签')
    
    final_chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(final_chart, use_container_width=True)
    
    # 节省统计
    mode_name = calc_mode.split('：')[0] # "方案一"
    st.markdown(f"""
    <div style='padding: 10px; background-color: #f0fdf4; border-radius: 5px; border-left: 5px solid #27ae60;'>
        📉 <strong>节省统计：</strong> 相比全额自费，当前【{mode_name}】预计共为您节省 
        <span style='color: #27ae60; font-weight: bold; font-size: 1.2em;'>¥{total_saved:,.0f}</span>
    </div>
    """, unsafe_allow_html=True)



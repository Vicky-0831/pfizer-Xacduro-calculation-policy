import streamlit as st
import pandas as pd
import altair as alt
import re

# --- 1. 页面配置 ---
st.set_page_config(page_title="X药2026双重支付商保模拟计算器", layout="wide")

# --- 2. 终极 CSS 样式 ---
st.markdown("""
    <style>
    /* 全局字体优化 */
    .big-font { font-size: 24px !important; font-weight: bold; color: #000000; }
    .highlight-green { color: #27ae60; font-weight: bold; }
    
    /* 输入框样式 - 保持浅蓝底色 */
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
    /* 锁定框样式 */
    div[data-baseweb="input"]:has(input:disabled) {
        background-color: #f0f2f6 !important;
        border: 1px solid rgba(49, 51, 63, 0.2) !important;
        opacity: 0.6;
    }
    div[data-baseweb="input"] input:disabled {
        color: #666666 !important;
    }
    
    /* 弱化基础信息设置的标题 */
    .small-header {
        font-size: 14px;
        color: #999;
        margin-bottom: 5px;
        font-weight: normal;
    }
    
    /* 调整一下 number_input 的 label 字体大小 */
    .stNumberInput label {
        font-size: 14px;
        color: #555;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 数据加载函数 (读取 CSV) ---
@st.cache_data
def load_policy_data():
    # 使用上传的CSV文件名
    csv_file = 'CSMI BASIC DATA-鼎优乐2026AP1.xlsx_Sheet1_CSMI_BASIC_DATA-2026AP1.csv'
    
    try:
        # header=1 因为第一行是分类大标题
        df = pd.read_csv(csv_file, header=1)
        
        # 清洗列名
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        
        # 填充缺失值
        if '省份' in df.columns: df['省份'] = df['省份'].fillna('其他')
        if '城市' in df.columns: df['城市'] = df['城市'].fillna('通用')
        
        return df
    except Exception as e:
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

# --- 4. 主界面布局 ---

# 大标题与免责声明
st.title("X药2026双重支付商保模拟计算器")
st.markdown("""
<div style='background-color: #fff3cd; padding: 10px; border-radius: 5px; font-size: 12px; color: #856404; margin-bottom: 20px;'>
    <strong>⚠️ Disclaimer:</strong> 计算器仅限内部使用，该项目仅考虑患者使用X药且不涵盖其他项目费用，计算金额仅供参考，实际情况以医院为准。
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([1, 1.5])

with col1:
    # --- A. 基础信息设置 (弱化处理) ---
    st.markdown("<div class='small-header'>基础信息设置</div>", unsafe_allow_html=True)
    
    with st.container():
        # 缩小单价显示
        c_p1, c_p2 = st.columns([1, 2])
        with c_p1:
             price_per_box = st.number_input("药品单价", value=3179, disabled=True, label_visibility="collapsed")
        with c_p2:
             st.caption("元/盒 (已锁定标准价格)")

        # 合并在一行
        c_a1, c_a2 = st.columns(2)
        with c_a1:
            daily_usage = st.number_input("一日使用盒数", value=4) 
        with c_a2:
            days_usage = st.number_input("用药天数", value=7, step=1)
            
        total_cost = price_per_box * daily_usage * days_usage
        
        # 放大显示的黑色总费用
        st.markdown(f"<div style='margin-top:10px; font-size:16px;'>当前周期预计总费用: <span class='big-font'>¥{total_cost:,.0f}</span></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # --- B. 双重支付设置 ---
    st.subheader("双重支付设置")
    
    # 1. 惠民保
    st.write("**第1重保障：惠民保** (信息更新时间：**)")
    is_huiminbao = st.checkbox("参加当地惠民保", value=True)
    
    default_deductible = 20000.0
    default_rate = 60.0
    selected_prod_id = "default"
    
    # 自动化选择器
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
            prod_rows = df_policy[(df_policy['省份']==sel_prov) & (df_policy['城市']==sel_city)]
            prod_names = prod_rows['保险名称'].unique()
            sel_prod = st.selectbox("具体产品", prod_names)
            
            if sel_prod:
                row = prod_rows[prod_rows['保险名称'] == sel_prod].iloc[0]
                # 尝试使用CSV中的列名提取数据
                # 根据之前分析，起付线可能在 '起付线/年'，报销在 '报销比例'
                val_deduct = row.get('起付线/年') if '起付线/年' in row else row.get('起付线')
                val_rate = row.get('报销比例')
                
                default_deductible = parse_deductible(val_deduct)
                default_rate = parse_rate(val_rate)
                
                # 关键：生成ID强制刷新输入框
                selected_prod_id = f"{sel_prov}_{sel_city}_{sel_prod}"
                
                # --- 参考条款 (醒目黑色 + 详细信息) ---
                # 获取 CSV 中 J,K,M,N,O,R,AA,AB,AC 列的信息
                # J=投保期间（起）, K=投保期间（止）, M=保障期间（起）, N=保障期间（止）, 
                # O=保费（元/年）, R=报销结算方式, AA=起付线/年, AB=报销比例, AC=封顶线/年
                
                # 容错获取
                def get_val(col_part):
                    for c in df_policy.columns:
                        if col_part in c: return row.get(c, '-')
                    return '-'

                ref_info = {
                    "投保期": f"{get_val('投保期间（起）')} 至 {get_val('投保期间（止）')}",
                    "保障期": f"{get_val('保障期间（起）')} 至 {get_val('保障期间（止）')}",
                    "保费": get_val('保费'),
                    "结算方式": get_val('报销结算方式'),
                    "起付线": get_val('起付线'),
                    "报销比例": get_val('报销比例'),
                    "封顶线": get_val('封顶线')
                }
                
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #ddd; margin-bottom: 10px; color: #000; font-size: 13px;">
                    <strong>📋 参考条款 ({sel_prod})</strong><br>
                    • <strong>投保期:</strong> {ref_info['投保期']}<br>
                    • <strong>保障期:</strong> {ref_info['保障期']}<br>
                    • <strong>保费:</strong> {ref_info['保费']} | <strong>结算:</strong> {ref_info['结算方式']}<br>
                    • <strong>核心条款:</strong> 起付线 {ref_info['起付线']} | 比例 {ref_info['报销比例']} | 封顶 {ref_info['封顶线']}
                </div>
                """, unsafe_allow_html=True)

    # 惠民保输入框
    c1, c2 = st.columns(2)
    with c1:
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
        st.markdown("<div style='font-size:12px; color:#666;'>具体情况可根据自己实际修改</div>", unsafe_allow_html=True)
        
    st.markdown("---")
    
    # 2. 双坦
    st.write("**第2重保障：双坦同行项目**")
    is_shuangtan = st.checkbox("参加双坦同行项目", value=True)
    shuangtan_rate = 0.5 
    st.caption("说明：双坦项目报销自付总费用的 50%")

with col2:
    st.subheader("结果输出 (模拟测算)")
    
    # --- 计算逻辑：默认顺序 (先双坦，后惠民保) ---
    def calculate_cost(order_type):
        """
        order_type: 
        'st_first' = 先双坦(50%) -> 余额 -> 惠民保 (二段式)
        'hmb_first' = 先惠民保 -> 余额 -> 双坦
        """
        st_val = 0.0
        hmb_val = 0.0
        
        if order_type == 'st_first':
            # Step A: 双坦 (基于总价)
            if is_shuangtan:
                st_val = total_cost * shuangtan_rate
            
            # Step B: 惠民保 (基于余额)
            balance = total_cost - st_val
            if is_huiminbao:
                if balance > hmb_deductible:
                    hmb_val = (balance - hmb_deductible) * hmb_rate
        
        else: # hmb_first
            # Step A: 惠民保 (基于总价)
            if is_huiminbao:
                if total_cost > hmb_deductible:
                    hmb_val = (total_cost - hmb_deductible) * hmb_rate
            
            # Step B: 双坦 (基于余额)
            balance = total_cost - hmb_val
            if is_shuangtan:
                st_val = balance * shuangtan_rate
                
        final_reimb = st_val + hmb_val
        if final_reimb > total_cost: final_reimb = total_cost
        final_pay = total_cost - final_reimb
        return final_pay, st_val, hmb_val

    # 默认计算 (先双坦)
    pay_default, st_val_def, hmb_val_def = calculate_cost('st_first')
    
    # --- 准备图表数据 ---
    cost_s1 = total_cost # 全自费
    
    # 场景2：参加地方惠民保 (参考) -> 仅算惠民保，无双坦
    if is_huiminbao and total_cost > hmb_deductible:
        only_hmb_reimb = (total_cost - hmb_deductible) * hmb_rate
    else:
        only_hmb_reimb = 0.0
    cost_s2 = total_cost - only_hmb_reimb
    
    # 场景3：当前 (惠民保+双坦同行)
    cost_s3 = pay_default
    
    total_saved = cost_s1 - cost_s3
    
    # --- 结果展示 ---
    
    # 大数字面板
    daily_avg = cost_s3 / days_usage if days_usage > 0 else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("当前周期预计总费用", f"¥{total_cost:,.0f}")
    
    # 箭头向下 ↓ (Streamlit trick: negative delta shows red down arrow, we want green down arrow?
    # Streamlit standard: Green = Up (Good), Red = Down (Bad).
    # If we want "Down Arrow" but "Green", we can use a hack:
    # Use normal delta string "↓ 省下 xx%" but delta_color="normal" (green)
    delta_str = f"↓ 省下 {total_saved/total_cost:.1%}" if total_cost > 0 else "-"
    m2.metric("当前报销合计", f"¥{(total_cost - cost_s3):,.0f}", delta=delta_str) 
    
    m3.metric("患者最终自付", f"¥{cost_s3:,.0f}", delta_color="inverse")
    
    # 结论行
    st.markdown(f"""
    <div style='background-color: #dcebf7; padding: 15px; border-radius: 8px; margin-top: 10px; text-align: center; color: #0e1117;'>
        <span style='font-size: 18px;'>
            💡 多重保障后，患者用药治疗 <b>{int(days_usage)}</b> 天<br>
            日治疗费用：<span style='color:#27ae60; font-size: 26px; font-weight: bold;'>¥{daily_avg:,.0f}</span>
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # --- 图表：自付费用对比 (横向柱状图 + 折线趋势) ---
    st.write("### 📊 自付费用对比")
    
    label_1 = '全额自费'
    label_2 = '参加地方惠民保'
    label_3 = '惠民保+双坦同行'
    
    chart_df = pd.DataFrame({
        '情景': [label_1, label_2, label_3],
        '费用': [cost_s1, cost_s2, cost_s3],
        '标签': [f'¥{cost_s1:,.0f}', f'¥{cost_s2:,.0f}', f'¥{cost_s3:,.0f}'],
        'order': [1, 2, 3] #用于排序
    })
    
    max_val = chart_df['费用'].max() * 1.2
    
    # 1. 基础柱状图 (横向)
    base = alt.Chart(chart_df).encode(
        y=alt.Y('情景', sort=[label_1, label_2, label_3], title=None),
        x=alt.X('费用', title='自付费用 (¥)', scale=alt.Scale(domain=[0, max_val]))
    )
    
    bars = base.mark_bar(size=40).encode(
        color=alt.Color('情景', scale=alt.Scale(range=['#e74c3c', '#3498db', '#27ae60']), legend=None)
    )
    
    # 2. 文字标签
    text = base.mark_text(dx=10, align='left', color='black').encode(text='标签')
    
    # 3. 价格下降箭头趋势 (用 tick 或 rule 模拟)
    # Altair 横向画折线不太直观，我们可以用 rule 连接各点
    # 或者简单点，我们保持您的原版横向图，因为它最清晰
    
    final_chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(final_chart, use_container_width=True)
    
    # 节省统计 (绿色金额)
    st.markdown(f"""
    <div style='padding: 10px; background-color: #f0fdf4; border-radius: 5px; border-left: 5px solid #27ae60;'>
        📉 <strong>节省统计：</strong> 相比全额自费，该方案预计共为您节省 
        <span style='color: #27ae60; font-weight: bold; font-size: 1.2em;'>¥{total_saved:,.0f}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # --- 报销机制对比按钮 ---
    st.write("")
    st.write("")
    with st.expander("🔄 切换报销结算顺序 (查看金额差异)"):
        st.write("目前默认采用 **“先双坦，后惠民保”** 的结算逻辑。您可以点击下方查看另一种顺序的结果：")
        
        pay_alt, st_val_alt, hmb_val_alt = calculate_cost('hmb_first')
        diff = pay_default - pay_alt
        
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.info(f"**方案 A (当前): 先双坦 -> 后惠民保**\n\n患者自付: **¥{pay_default:,.0f}**")
        with col_res2:
            st.warning(f"**方案 B: 先惠民保 -> 后双坦**\n\n患者自付: **¥{pay_alt:,.0f}**")
            
        if abs(diff) > 1:
            if diff < 0:
                st.success(f"结论：当前方案 (A) 更划算，比方案 B 多省 ¥{abs(diff):,.0f}")
            else:
                st.error(f"结论：方案 B 更划算，比当前方案多省 ¥{abs(diff):,.0f}")
        else:
            st.write("结论：两种顺序下，患者最终自付费用一致。")


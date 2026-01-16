import streamlit as st
import pandas as pd
import altair as alt
import re

# 页面配置
st.set_page_config(page_title="X药2026模拟器", layout="wide")

# --- 终极 CSS 样式 (保持原版) ---
st.markdown("""
    <style>
    /* 1. 【核心】针对所有启用的输入框容器：设置统一浅蓝色背景 */
    div[data-baseweb="input"] {
        background-color: #EBF5FB !important; /* 浅蓝色底 */
        border: 1px solid #EBF5FB !important; /* 浅蓝色边框 */
        border-radius: 5px !important;
    }
    
    /* 2. 【关键】强制内部所有子元素背景透明 */
    div[data-baseweb="input"] > div,
    div[data-baseweb="input"] input {
        background-color: transparent !important;
        color: #000000 !important; /* 文字黑色 */
        font-weight: 500;
    }
    /* 3. 【锁定框】针对被禁用(Locked)的输入框，强制改回灰色 */
    div[data-baseweb="input"]:has(input:disabled) {
        background-color: #f0f2f6 !important; /* 灰色底 */
        border: 1px solid rgba(49, 51, 63, 0.2) !important;
        opacity: 0.6;
    }
    
    /* 4. 锁定框里的文字颜色变浅 */
    div[data-baseweb="input"] input:disabled {
        color: #666666 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 数据处理函数 ---
@st.cache_data
def load_policy_data():
    default_file = 'policy_data.xlsx'
    
    def read_and_clean(source):
        # 1. 先读前几行，找表头在哪
        # 很多表第一行是标题，第二行才是列名，我们搜索包含"省份"的那一行
        df_preview = pd.read_excel(source, sheet_name=0, header=None, nrows=10)
        header_row_idx = 0
        for idx, row in df_preview.iterrows():
            row_str = row.astype(str).values
            if '省份' in row_str or '城市' in row_str:
                header_row_idx = idx
                break
        
        # 2. 正式读取
        df = pd.read_excel(source, sheet_name=0, header=header_row_idx)
        
        # 3. 清洗列名 (去换行符)
        df.columns = [str(c).replace('\n', '').strip() for c in df.columns]
        
        # 4. 筛选列 (根据您提供的文件列名)
        # 尝试匹配可能的列名，增加鲁棒性
        col_map = {
            '省份': '省份',
            '城市': '城市',
            '保险名称': '保险名称',
            '起付线': '起付线/年', # 支持模糊匹配
            '起付线/年': '起付线/年',
            '报销比例': '报销比例',
            'X药是否可报销': 'X药是否可报销'
        }
        
        # 找到实际存在的列
        final_cols = []
        rename_dict = {}
        for key, target in col_map.items():
            if target in df.columns:
                final_cols.append(target)
            elif key in df.columns:
                final_cols.append(key)
                rename_dict[key] = target # 统一列名
        
        df = df[final_cols].rename(columns=rename_dict)
        
        # 填充
        if '省份' in df.columns: df['省份'] = df['省份'].fillna('其他')
        if '城市' in df.columns: df['城市'] = df['城市'].fillna('全省/通用')
        
        return df

    try:
        return read_and_clean(default_file)
    except FileNotFoundError:
        # 假如本地没有，静默处理，不报错，只是下拉框里没数据
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def parse_deductible(val):
    if pd.isna(val): return 20000.0
    text = str(val)
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        num = float(match.group(1))
        if '万' in text or 'w' in text.lower(): return num * 10000
        if num < 100: return num * 10000 # 猜测是万
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

st.title("X药2026多重支付商保模拟计算器")
st.markdown("---")

col1, col2 = st.columns([1, 1.5])

with col1:
    # --- A. 用药参数 ---
    st.subheader("A. 用药参数")
    st.info("基础信息设置")
    
    # 单价锁定 -> 灰色
    price_per_box = st.number_input("药品单价 (元/盒)", value=3179, disabled=True, help="单价已锁定标准价格")
    
    # 启用 -> 全蓝 (包括加减号)
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
    
    # --- [新增] 智能填充逻辑 ---
    auto_deductible = 20000.0
    auto_rate = 60.0
    
    if is_huiminbao and not df_policy.empty:
        # 只有当数据加载成功时才显示选择器
        try:
            # 紧凑布局选择器
            s1, s2 = st.columns(2)
            with s1:
                prov_list = ['请选择'] + list(df_policy['省份'].unique())
                sel_prov = st.selectbox("省份", prov_list, label_visibility="collapsed", placeholder="选择省份")
            with s2:
                if sel_prov != '请选择':
                    city_list = list(df_policy[df_policy['省份']==sel_prov]['城市'].unique())
                    sel_city = st.selectbox("城市", city_list, label_visibility="collapsed")
                else:
                    sel_city = None
                    st.selectbox("城市", ["先选省份"], disabled=True, label_visibility="collapsed")
            
            if sel_prov != '请选择' and sel_city:
                # 筛选产品
                prods = df_policy[(df_policy['省份']==sel_prov) & (df_policy['城市']==sel_city)]
                prod_name = st.selectbox("选择具体产品", prods['保险名称'].unique())
                
                # 获取数据
                row = prods[prods['保险名称'] == prod_name].iloc[0]
                auto_deductible = parse_deductible(row.get('起付线/年'))
                auto_rate = parse_rate(row.get('报销比例'))
                
                # 显示政策小提示 (原汁原味风格)
                is_cover = row.get('X药是否可报销', '-')
                st.caption(f"ℹ️ {prod_name}: X药覆盖[{is_cover}] | 起付线 {row.get('起付线/年')} | 比例 {row.get('报销比例')}")
                
        except Exception:
            pass # 出错就静默，回退到手动输入
            
    # --- [原版] 输入框 (值由上面计算，用户可改) ---
    c1, c2 = st.columns(2)
    with c1:
        # 启用 -> 全蓝
        hmb_deductible = st.number_input("惠民保起付线", value=auto_deductible, step=1000.0)
    with c2:
        # 启用 -> 全蓝
        hmb_rate_input = st.number_input("报销比例 (%)", value=auto_rate, step=5.0)
        hmb_rate = hmb_rate_input / 100.0
        
    st.markdown("---")
    st.write("**第2重保障：双坦同行项目**")
    is_shuangtan = st.checkbox("参加双坦同行项目", value=True)
    shuangtan_rate = 0.5 
    st.caption("说明：双坦项目直接报销总费用的 50%")

with col2:
    st.subheader("结果输出 (模拟测算)")
    
    # --- 计算逻辑 (完全保持原版) ---
    if total_cost > hmb_deductible:
        reimburse_hmb_val = (total_cost - hmb_deductible) * hmb_rate
    else:
        reimburse_hmb_val = 0.0
    
    # 如果没勾选，归零
    if not is_huiminbao:
        reimburse_hmb_val = 0.0

    reimburse_st_val = total_cost * shuangtan_rate if is_shuangtan else 0.0
    
    # --- 准备图表数据 ---
    cost_scenario_1 = total_cost
    
    # 场景2：假设仅参加惠民保 (用于对比)
    # 这里的逻辑稍微需要注意：如果用户没勾惠民保，场景2其实就等于场景1。
    # 为了图表好看，我们假设场景2是“如果参加了惠民保”的效果，或者严格按照用户勾选
    # 既然是“费用分担对比”，通常展示 1.全自费 2.仅惠民保 3.双重
    
    # 重新计算一个“理论上的仅惠民保”值，哪怕用户上面没勾，为了画图对比也要算一下吗？
    # 按照原版逻辑: cost_scenario_2 = total_cost - reimburse_hmb_val
    # 这意味着如果上面没勾，场景2就等于全自费。这符合逻辑。
    cost_scenario_2 = total_cost - reimburse_hmb_val
    if cost_scenario_2 < 0: cost_scenario_2 = 0
    
    total_reimb_both = reimburse_hmb_val + reimburse_st_val
    cost_scenario_3 = total_cost - total_reimb_both
    if cost_scenario_3 < 0: cost_scenario_3 = 0
    
    # --- 顶部大数字 ---
    current_reimburse = total_reimb_both
    
    if current_reimburse > total_cost: current_reimburse = total_cost
    current_final_cost = total_cost - current_reimburse
    
    # 计算日均费用
    daily_avg_cost = current_final_cost / days_usage if days_usage > 0 else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("本周期总费用", f"¥{total_cost:,.0f}")
    m2.metric("当前报销合计", f"¥{current_reimburse:,.0f}", delta=f"省下 {current_reimburse/total_cost:.1%}" if total_cost>0 else None)
    m3.metric("患者最终自付", f"¥{current_final_cost:,.0f}", delta_color="inverse")
    
    # --- 结论行 (颜色修正版) ---
    # 天数和金额都使用绿色 #27ae60
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
    
    # 修复手机端飘窗：去掉 tooltip，禁用 interactive
    base = alt.Chart(chart_data).encode(
        x=alt.X('患者自付费用', title='患者自付费用（元）', scale=alt.Scale(domain=[0, max_val])),
        y=alt.Y('情景', sort=None, title=None), 
        # tooltip=['情景', '患者自付费用']  <-- 已删除
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
    # configure_view(strokeWidth=0) 去掉边框，确保静态
    final_chart = (bars + text).properties(height=300).configure_view(strokeWidth=0)
    st.altair_chart(final_chart, use_container_width=True)
    
    st.info(f"📉 **节省统计：** 相比全额自费，该方案预计共为您节省 **¥{(cost_scenario_1 - cost_scenario_3):,.0f}** 元。")


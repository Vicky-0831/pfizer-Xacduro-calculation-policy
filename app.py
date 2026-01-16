import streamlit as st
import pandas as pd
import altair as alt
import re

# 页面配置
st.set_page_config(page_title="X药2026模拟器(Pro版)", layout="wide")

# --- 1. 数据加载与处理函数 ---
@st.cache_data
def load_policy_data():
    default_file = 'policy_data.xlsx'
    
    def read_excel_file(source):
        # 注意这里：sheet_name=0 表示读取第一个表，不管名字叫什么
        df = pd.read_excel(source, sheet_name=0, header=1)
        
        # ... 后面的清洗逻辑保持不变 ...
        df.columns = [c.replace('\n', '') if isinstance(c, str) else c for c in df.columns]
        cols = ['省份', '城市', '保险名称', '起付线/年', '报销比例', 'X药是否可报销', '备注']
        valid_cols = [c for c in cols if c in df.columns]
        df = df[valid_cols]
        df['省份'] = df['省份'].fillna('其他')
        df['城市'] = df['城市'].fillna('全省/通用')
        return df

    try:
        return read_excel_file(default_file)
    except FileNotFoundError:
        st.warning(f"⚠️ 未找到配置文件 `{default_file}`，请手动上传。")
        uploaded_file = st.file_uploader("上传 Excel", type=['xlsx'])
        if uploaded_file:
            return read_excel_file(uploaded_file)
        return pd.DataFrame()
    except Exception as e:
        # 这里会把具体的错误打印出来，方便调试
        st.error(f"表格读取错误: {e}")
        return pd.DataFrame()


def parse_deductible(val):
    """尝试从文本中提取起付线数字"""
    if pd.isna(val): return 20000.0 # 默认值
    text = str(val)
    # 提取第一个数字
    match = re.search(r'(\d+(\.\d+)?)', text)
    if match:
        num = float(match.group(1))
        # 如果包含'万'或'w'，乘以10000
        if '万' in text or 'w' in text.lower():
            return num * 10000
        # 如果数字小于100，可能提取错了或者单位是万元但没写，保守起见不做处理或假设为万？
        # 这里简单处理：如果提取出 1.5 但没写万，通常在起付线语境下也是万，但为了安全，只处理明确带万的
        # 或者如果数字 > 100，假设是元
        if num > 100: return num
        # 如果是 1.5 这种小数字，大概率是万
        if num < 50: return num * 10000
    return 20000.0

def parse_rate(val):
    """尝试从文本中提取报销比例"""
    if pd.isna(val): return 60.0 # 默认值
    text = str(val)
    # 找百分数 (e.g. 60%)
    match_pct = re.search(r'(\d+(\.\d+)?)%', text)
    if match_pct:
        return float(match_pct.group(1))
    # 找小数 (e.g. 0.6)
    match_dec = re.search(r'0\.(\d+)', text)
    if match_dec:
        return float("0." + match_dec.group(1)) * 100
    return 60.0

# 加载数据
df_policy = load_policy_data()

# --- 终极 CSS 样式 ---
st.markdown("""
    <style>
    /* 核心输入框样式 */
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
    </style>
""", unsafe_allow_html=True)

st.title("X药2026多重支付商保模拟计算器 (Pro)")
st.caption("基于最新 CSMI 惠民保数据")
st.markdown("---")

# --- 核心布局 ---
col1, col2 = st.columns([1, 1.5])

with col1:
    # --- A. 用药参数 ---
    st.subheader("A. 用药参数")
    with st.expander("基础设置", expanded=True):
        price_per_box = st.number_input("药品单价 (元/盒)", value=3179, disabled=True)
        daily_usage = st.number_input("一日使用盒数", value=4) 
        days_usage = st.number_input("用药天数", value=7, step=1)
        total_cost = price_per_box * daily_usage * days_usage
        st.write(f"**当前周期总费用:** ¥{total_cost:,.0f}")

    st.markdown("---")

    # --- B. 保障参数 (集成数据版) ---
    st.subheader("B. 保障参数")
    st.info("多重支付设置")

    # 1. 惠民保选择器
    st.write("**第1重保障：惠民保**")
    is_huiminbao = st.checkbox("参加当地惠民保", value=True)

    # 初始化默认值
    default_deductible = 20000.0
    default_rate = 60.0
    policy_note = "未选择特定产品"
    drug_coverage_status = "未知"

    if is_huiminbao and not df_policy.empty:
        # 级联选择器
        provinces = ['自定义'] + list(df_policy['省份'].unique())
        selected_prov = st.selectbox("选择省份", provinces)

        if selected_prov != '自定义':
            cities = list(df_policy[df_policy['省份'] == selected_prov]['城市'].unique())
            selected_city = st.selectbox("选择城市", cities)
            
            products = df_policy[
                (df_policy['省份'] == selected_prov) & 
                (df_policy['城市'] == selected_city)
            ]
            product_names = products['保险名称'].unique()
            selected_product_name = st.selectbox("选择产品", product_names)

            # 获取选中产品的详细信息
            product_row = products[products['保险名称'] == selected_product_name].iloc[0]
            
            # 提取原始文本
            raw_deductible = product_row.get('起付线/年', '未说明')
            raw_rate = product_row.get('报销比例', '未说明')
            drug_coverage = product_row.get('X药是否可报销', '需确认')
            
            # 智能解析数值
            default_deductible = parse_deductible(raw_deductible)
            default_rate = parse_rate(raw_rate)
            
            # 显示政策详情提示
            msg_color = "red" if str(drug_coverage).strip() == "否" else "green"
            st.markdown(f"""
            <div style="background-color: #f9f9f9; padding: 10px; border-radius: 5px; font-size: 0.9em; border-left: 3px solid #3498db; margin-bottom: 10px;">
                <strong>📋 政策详情 ({selected_product_name})</strong><br>
                • <strong>X药覆盖:</strong> <span style="color:{msg_color}">{drug_coverage}</span><br>
                • <strong>起付线条款:</strong> {raw_deductible}<br>
                • <strong>报销条款:</strong> {raw_rate}
            </div>
            """, unsafe_allow_html=True)
            
            if str(drug_coverage).strip() == "否":
                st.warning("⚠️ 注意：该产品资料显示可能不覆盖此药，请仔细核对。")

    # 输入框 (如果选择了产品，会自动填入解析后的值；用户仍可修改)
    c1, c2 = st.columns(2)
    with c1:
        hmb_deductible = st.number_input(
            "惠民保起付线", 
            value=default_deductible, 
            step=1000.0,
            help="根据所选产品自动填充，支持手动修改"
        )
    with c2:
        hmb_rate_input = st.number_input(
            "报销比例 (%)", 
            value=default_rate, 
            step=5.0,
            help="根据所选产品自动填充，支持手动修改"
        )
        hmb_rate = hmb_rate_input / 100.0

    st.markdown("---")
    st.write("**第2重保障：双坦同行项目**")
    is_shuangtan = st.checkbox("参加双坦同行项目", value=True)
    shuangtan_rate = 0.5 
    st.caption("说明：双坦项目直接报销总费用的 50%")

with col2:
    # --- 结果逻辑 (保持不变) ---
    # 核心计算
    if total_cost > hmb_deductible:
        reimburse_hmb_val = (total_cost - hmb_deductible) * hmb_rate
    else:
        reimburse_hmb_val = 0.0
    
    # 如果不参加，归零
    if not is_huiminbao:
        reimburse_hmb_val = 0.0

    reimburse_st_val = total_cost * shuangtan_rate if is_shuangtan else 0.0
    
    current_reimburse = reimburse_hmb_val + reimburse_st_val
    # 防止报销超额
    if current_reimburse > total_cost: 
        current_reimburse = total_cost
        
    current_final_cost = total_cost - current_reimburse
    daily_avg_cost = current_final_cost / days_usage if days_usage > 0 else 0

    # --- 结果展示 ---
    st.subheader("📊 模拟测算结果")
    
    # 顶部大指标 (手机端友好)
    m1, m2, m3 = st.columns(3)
    m1.metric("本周期总费用", f"¥{total_cost:,.0f}")
    m2.metric("当前报销合计", f"¥{current_reimburse:,.0f}", delta=f"省下 {current_reimburse/total_cost:.1%}" if total_cost>0 else None)
    m3.metric("患者最终自付", f"¥{current_final_cost:,.0f}", delta_color="inverse")

    # 结论卡片
    st.markdown(f"""
    <div style='background-color: #dcebf7; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: center; color: #0e1117; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
        <span style='font-size: 18px; font-weight: bold;'>
            💡 综合治疗成本：<span style='color:#27ae60'>¥{daily_avg_cost:,.0f}</span> /天
        </span>
        <br>
        <span style='font-size: 14px; color: #555;'>
            (基于 {int(days_usage)} 天疗程计算)
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # --- 图表 ---
    # 场景数据准备
    cost_s1 = total_cost # 全自费
    
    # 场景2：仅惠民保
    reimb_only_hmb = (total_cost - hmb_deductible) * hmb_rate if total_cost > hmb_deductible else 0
    if not is_huiminbao: reimb_only_hmb = 0 # 如果没选惠民保，这就是0，或者我们可以假设场景2是“假设参加了惠民保”
    cost_s2 = max(0, total_cost - reimb_only_hmb)

    # 场景3：当前配置 (惠民保+双坦)
    cost_s3 = current_final_cost

    label_1, label_2, label_3 = '全额自费', '仅惠民保', '惠民保+双坦'

    chart_data = pd.DataFrame({
        '情景': [label_1, label_2, label_3],
        '患者自付费用': [cost_s1, cost_s2, cost_s3],
        '标签': [f'¥{cost_s1:,.0f}', f'¥{cost_s2:,.0f}', f'¥{cost_s3:,.0f}']
    })

    # 修复：移除 tooltip 防止手机端悬浮窗问题，禁用交互
    base = alt.Chart(chart_data).encode(
        x=alt.X('患者自付费用', title='患者自付费用（元）'),
        y=alt.Y('情景', sort=None, title=None), 
    )
    
    bars = base.mark_bar(size=40).encode(
        color=alt.Color('情景', scale=alt.Scale(
            domain=[label_1, label_2, label_3],
            range=['#95a5a6', '#3498db', '#27ae60'] 
        ), legend=None)
    )
    
    text = base.mark_text(
        align='left', baseline='middle', dx=5, color='black'
    ).encode(text='标签')

    # configure_view(strokeWidth=0) 去除边框，且不调用 interactive()
    final_chart = (bars + text).properties(height=250).configure_view(strokeWidth=0)
    
    st.altair_chart(final_chart, use_container_width=True)

    # 节省统计
    st.info(f"📉 **节省统计：** 相比全额自费，当前方案预计共为您节省 **¥{(cost_s1 - cost_s3):,.0f}** 元。")


#!/usr/bin/env python3
"""产供销存日报 — 数据采集 + 格式排版 + 内置决策建议（脚本规则驱动）"""
import subprocess, json, sys, os, time, logging
from datetime import datetime, timedelta

# ===== 重试工具 =====
LOG_FILE = f"/tmp/gen_daily_report_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def retry(fn, max_attempts=3, delay=2, backoff=2, label="操作"):
    """指数退避重试装饰器"""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            logging.warning(f"{label} 第{attempt}次失败: {e}")
            if attempt == max_attempts:
                logging.error(f"{label} 重试{max_attempts}次均失败")
                raise
            wait = delay * (backoff ** (attempt - 1))
            time.sleep(wait)

D = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
YD = (datetime.strptime(D, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
WEEKDAY_CN = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]
DW = WEEKDAY_CN[datetime.strptime(D, "%Y-%m-%d").weekday()]

MYSQL = ["mysql", "-h", "127.0.0.1", "-P", "53306", "-u", "tencentbi", "-pAlphy@2026!FineBI_Mysql", "yunzhijia", "--skip-column-names", "-e"]
SKILL_DIR = os.path.expanduser("~/.hermes/skills/ima")
KB_ID = "trunpq0_3Zihd9ziHA8DqEWmba6F2XoZQviX7QjxZ9E="
FOLDER_ID = "folder_7462706554632122"

def OPTS():
    c = open(os.path.expanduser("~/.config/ima/client_id")).read().strip()
    k = open(os.path.expanduser("~/.config/ima/api_key")).read().strip()
    return json.dumps({"clientId": c, "apiKey": k}, ensure_ascii=False)

def ima(api, data):
    """调用IMA API，带重试"""
    def _call():
        r = subprocess.run(["node", f"{SKILL_DIR}/ima_api.cjs", api, json.dumps(data, ensure_ascii=False), OPTS()], capture_output=True, text=True, timeout=30)
        if r.returncode != 0: raise RuntimeError(f"IMA进程异常: {r.stderr[:200]}")
        resp = json.loads(r.stdout)
        if resp.get("code") != 0: raise RuntimeError(f"IMA业务错误 [{api}]: {resp.get('msg')}")
        return resp["data"]
    try:
        return retry(_call, max_attempts=3, label=f"IMA-{api.split('/')[-1]}")
    except Exception as e:
        logging.error(f"IMA调用最终失败 [{api}]: {e}")
        return {"note_id": "", "error": str(e)}

QUERY_FAILURES = []

def q(sql, label=""):
    """执行MySQL查询，带重试。失败返回None"""
    def _call():
        r = subprocess.run(MYSQL + [sql], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(f"MySQL错误: {r.stderr[:200]}")
        return r.stdout.strip()
    try:
        return retry(_call, max_attempts=3, label=f"MySQL-{label or '查询'}")
    except Exception as e:
        logging.error(f"MySQL查询最终失败 [{label}]: {e}")
        QUERY_FAILURES.append(label or sql[:60])
        return None

def gv(sql, label=""):
    """查询并提取第一个非空值。查询失败返回❓，无数据返回0"""
    out = q(sql, label=label)
    if out is None:
        return "❓"  # 查询失败，不是0！让读者知道数据没取到
    for line in out.split("\n"):
        parts = line.split("\t")
        if parts and parts[0].strip() and parts[0].strip() not in ("NULL", "0.00", "0"):
            return parts[0].strip()
    return "0"

def fmt(n):
    try:
        nv = float(n)
        if nv >= 100_000_000: return f"{nv/100_000_000:.2f}亿（¥{nv/100_000_000:.2f}亿）"
        if nv >= 10_000: return f"{nv:,.2f}（¥{nv/10_000:.2f}万）"
        return f"{nv:,.2f}"
    except: return str(n)
def fmt_w(n):
    try:
        nv = float(n)
        if nv >= 100_000_000: return f"¥{nv/100_000_000:.2f}亿"
        if nv >= 10_000: return f"¥{nv/10_000:.2f}万"
        return f"¥{nv:,.2f}"
    except: return str(n)
def pct(n, d):
    try: nd, dd = float(n), float(d); return f"{nd/dd*100:.1f}%" if dd > 0 else "—"
    except: return "—"

def sf(v):
    """safe_float — 将 ❓/None/空 安全转为 float 或 None"""
    try: return float(v) if v not in (None, "", "❓", "0", "0.0", "0.00") else None
    except: return None

def calc_change(today, yesterday):
    """计算环比变化率及方向描述。返回 (pct_str, direction)"""
    t = sf(today)
    y = sf(yesterday)
    if t is None and y is None:
        return "—", ""
    if t is None and y is not None:
        return "—", f"昨日有{y:.1f}，今日无数据"
    if t is not None and y is None:
        return "—", f"新增产出{t:.1f}"
    if y == 0:
        return "—", f"今日产出{t:.1f}"
    chg = (t - y) / y * 100
    if abs(chg) < 5:
        return f"{chg:+.1f}%", "持平"
    elif chg > 30:
        return f"{chg:+.1f}%", f"⬆ 大幅增长{chg:.0f}%，关注是否可持续"
    elif chg > 5:
        return f"{chg:+.1f}%", f"↑ 环比增长{chg:.0f}%"
    elif chg < -30:
        return f"{chg:+.1f}%", f"⬇ 大幅下降{abs(chg):.0f}%，需关注原因"
    else:
        return f"{chg:+.1f}%", f"↓ 环比下降{abs(chg):.0f}%"

def analyze_pct(t, y):
    """直接返回变化率（用于阈值判断），异常返回None"""
    tv, yv = sf(t), sf(y)
    if tv is None or yv is None or yv == 0.0: return None
    return (tv - yv) / yv * 100

# ===== 数据采集 =====
# 产 — 全产线
flash_w  = gv(f"SELECT ROUND(SUM(d.产出_重量),2) FROM `云之家_闪蒸干燥粉记录` m JOIN `云之家_闪蒸干燥粉明细` d ON m.流水号=d.流水号 AND d.类型='产出' WHERE m.生产日期='{D}'")
flash_dw = gv(f"SELECT ROUND(SUM(d.产出_干重),2) FROM `云之家_闪蒸干燥粉记录` m JOIN `云之家_闪蒸干燥粉明细` d ON m.流水号=d.流水号 AND d.类型='产出' WHERE m.生产日期='{D}'")
haema_d  = gv(f"SELECT ROUND(SUM(d.重量KG),2) FROM `云之家_雨生红球藻入库记录` m JOIN `云之家_雨生红球藻入库明细` d ON m.流水号=d.流水号 WHERE d.入库日期='{D}'")
powd_w   = gv(f"SELECT ROUND(SUM(d.重量),2) FROM `云之家_破壁粉记录` m JOIN `云之家_破壁粉明细` d ON m.流水号=d.流水号 WHERE m.生产日期='{D}'")
finish_w = gv(f"SELECT ROUND(SUM(d.重量),2) FROM `云之家_成品破壁粉记录` m JOIN `云之家_成品破壁粉明细` d ON m.流水号=d.流水号 WHERE m.生产日期='{D}'")
aikang_d = gv(f"SELECT ROUND(SUM(d.数量),2) FROM `云之家_爱尔康生产明细` d WHERE d.生产日期='{D}'")
aikang_detail = q(f"""SELECT CASE
  WHEN d.产品名称 LIKE 'GY%' OR d.产品名称 LIKE '虾青素固体饮料%' THEN '固体饮料'
  WHEN d.产品名称 LIKE 'NJ%' THEN '胶囊'
  WHEN d.产品名称 LIKE 'PT%' OR d.产品名称 LIKE '成品虾青素压片糖果%' THEN '压片糖果'
  WHEN d.产品名称 LIKE 'WF%' THEN '微粉'
  WHEN d.产品名称 LIKE 'XY%' OR d.产品名称 LIKE '成品虾青素油%' THEN '虾青素油'
  WHEN d.产品名称 LIKE 'ZF%' OR d.产品名称 LIKE '成品雨生红球藻粉%' THEN '红球藻粉'
  ELSE d.产品名称 END AS cat, d.规格型号, ROUND(SUM(d.数量),2) qty
FROM `云之家_爱尔康生产明细` d WHERE d.生产日期='{D}'
GROUP BY cat, d.规格型号 ORDER BY qty DESC LIMIT 10""")
spray_d  = gv(f"SELECT ROUND(SUM(d.总产量KG),2) FROM `云之家_喷雾干燥生产记录` m JOIN `云之家_喷雾干燥生产明细` d ON m.流水号=d.流水号 WHERE d.生产日期='{D}'")
fresh_d  = gv(f"SELECT ROUND(SUM(毛重),2) FROM `云之家_鲜品采收明细` WHERE 日期='{D}'")
plan_qty = gv(f"SELECT COALESCE(SUM(计划数量),0) FROM `金蝶_计划产出单` WHERE 业务日期='{D}'")
wip_qty  = gv(f"SELECT COALESCE(SUM(在制数量),0) FROM `金蝶_计划产出单` WHERE 业务日期='{D}'")
# 昨日数据
y_flash  = gv(f"SELECT ROUND(SUM(d.产出_重量),2) FROM `云之家_闪蒸干燥粉记录` m JOIN `云之家_闪蒸干燥粉明细` d ON m.流水号=d.流水号 AND d.类型='产出' WHERE m.生产日期='{YD}'")
y_haema  = gv(f"SELECT ROUND(SUM(d.重量KG),2) FROM `云之家_雨生红球藻入库记录` m JOIN `云之家_雨生红球藻入库明细` d ON m.流水号=d.流水号 WHERE d.入库日期='{YD}'")
y_aikang = gv(f"SELECT ROUND(SUM(d.数量),2) FROM `云之家_爱尔康生产明细` d WHERE d.生产日期='{YD}'")
y_spray  = gv(f"SELECT ROUND(SUM(d.总产量KG),2) FROM `云之家_喷雾干燥生产记录` m JOIN `云之家_喷雾干燥生产明细` d ON m.流水号=d.流水号 WHERE d.生产日期='{YD}'")
y_fresh  = gv(f"SELECT ROUND(SUM(毛重),2) FROM `云之家_鲜品采收明细` WHERE 日期='{YD}'")

# 供
pur_amt  = gv(f"SELECT ROUND(SUM(d.含税金额),2) FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{D}'")
pur_items= gv(f"SELECT COUNT(*) FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{D}'")
y_pur    = gv(f"SELECT ROUND(SUM(d.含税金额),2) FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{YD}' AND m.供应商名称 NOT IN ('云南爱尔发生物技术股份有限公司','云南爱尔康生物技术有限公司','爱尔发生物科技（嘉兴）有限公司')")
ret_cnt  = gv(f"SELECT COUNT(*) FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{D}' AND d.退货数量>0")
ret_amt  = gv(f"SELECT ROUND(SUM(d.含税金额),2) FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{D}' AND d.退货数量>0")
pay_cnt  = gv(f"SELECT COUNT(*) FROM `金蝶_付款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D')")
pay_amt  = gv(f"SELECT ROUND(SUM(实付金额),2) FROM `金蝶_付款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D')")
pay_mat  = gv(f"SELECT ROUND(SUM(实付金额),2) FROM `金蝶_付款单` WHERE 业务日期='{D}' AND 付款类型='材料采购付款' AND 单据状态 IN ('C','D')")
pay_top  = q(f"SELECT 收款方名称, ROUND(实付金额,2) amt FROM `金蝶_付款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D') ORDER BY 实付金额 DESC LIMIT 5")
rcv_cnt  = gv(f"SELECT COUNT(*) FROM `金蝶_收款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D')")
rcv_amt  = gv(f"SELECT ROUND(SUM(实收金额),2) FROM `金蝶_收款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D')")
rcv_top  = q(f"SELECT 付款方名称, ROUND(实收金额,2) amt FROM `金蝶_收款单` WHERE 业务日期='{D}' AND 单据状态 IN ('C','D') ORDER BY 实收金额 DESC LIMIT 5")
sup_top  = q(f"SELECT m.供应商名称, d.物料名称, ROUND(d.数量,2), ROUND(d.含税单价,2), ROUND(d.含税金额,2) amt FROM `金蝶_采购入库单主表` m JOIN `金蝶_采购入库明细` d ON m.单据编号=d.单据编号 WHERE m.业务日期='{D}' AND m.供应商名称 NOT IN ('云南爱尔发生物技术股份有限公司','云南爱尔康生物技术有限公司','爱尔发生物科技（嘉兴）有限公司') ORDER BY amt DESC LIMIT 10")

# 销
sale_amt = gv(f"SELECT ROUND(SUM(价税合计),2) FROM `金蝶_销售订单主表` WHERE 业务日期='{D}' AND 客户名称 NOT LIKE '%爱尔康%' AND 客户名称 NOT LIKE '%嘉兴爱尔%' AND 客户名称 NOT LIKE '%爱尔发%'")
sale_cnt = gv(f"SELECT COUNT(*) FROM `金蝶_销售订单主表` WHERE 业务日期='{D}'")
sale_cust= gv(f"SELECT COUNT(DISTINCT 客户名称) FROM `金蝶_销售订单主表` WHERE 业务日期='{D}' AND 客户名称 NOT LIKE '%爱尔康%' AND 客户名称 NOT LIKE '%嘉兴爱尔%' AND 客户名称 NOT LIKE '%爱尔发%'")
y_sale   = gv(f"SELECT ROUND(SUM(价税合计),2) FROM `金蝶_销售订单主表` WHERE 业务日期='{YD}' AND 客户名称 NOT LIKE '%爱尔康%' AND 客户名称 NOT LIKE '%嘉兴爱尔%' AND 客户名称 NOT LIKE '%爱尔发%'")
pend_cnt = gv(f"SELECT COUNT(*) FROM `金蝶_销售订单主表` WHERE 业务日期='{D}' AND 单据状态 IN ('A','Z','')")
pend_amt = gv(f"SELECT ROUND(SUM(价税合计),2) FROM `金蝶_销售订单主表` WHERE 业务日期='{D}' AND 单据状态 IN ('A','Z','')")
pend_top = q(f"SELECT 客户名称, ROUND(价税合计,2) amt FROM `金蝶_销售订单主表` WHERE 业务日期='{D}' AND 单据状态 IN ('A','Z','') AND 客户名称 NOT LIKE '%爱尔康%' AND 客户名称 NOT LIKE '%嘉兴爱尔%' AND 客户名称 NOT LIKE '%爱尔发%' ORDER BY 价税合计 DESC LIMIT 5")

# 合同Pipeline — 待发货合同
contract_pending = q(f"SELECT COUNT(*) FROM `云之家_原料合同评审明细` WHERE 未发货数量 > 0")
contract_pending_qty = gv(f"SELECT ROUND(SUM(未发货数量),2) FROM `云之家_原料合同评审明细` WHERE 未发货数量 > 0")
contract_pending_top = q(f"SELECT m.销售客户, d.产品选择, d.未发货数量, d.单品用途 FROM `云之家_原料合同评审明细` d JOIN `云之家_原料合同评审记录` m ON d.流水号=m.流水号 WHERE d.未发货数量 > 0 ORDER BY d.未发货数量 DESC LIMIT 5")
contract_total = gv(f"SELECT COUNT(*) FROM `云之家_原料合同评审记录`")
contract_completed = gv(f"SELECT COUNT(*) FROM `云之家_原料合同评审记录` WHERE 流程状态='已完成'")

# 原料出库申请 — 当日出库
today_outbound = q(f"SELECT COUNT(*) FROM `云之家_原料出库申请记录` WHERE 业务日期='{D}'")
today_outbound_pending = q(f"SELECT COUNT(*) FROM `云之家_原料出库申请记录` WHERE 流程状态='进行中'")
today_outbound_top = q(f"SELECT 销售人员, 销售客户, 是否开票 FROM `云之家_原料出库申请记录` WHERE 业务日期='{D}' ORDER BY 流水号 DESC LIMIT 5")

# 原料开票申请 — 待开票合同
pending_invoice = q(f"SELECT COUNT(*) FROM `云之家_原料开票申请记录` WHERE 流程状态='进行中'")
pending_invoice_top = q(f"SELECT 销售人员, 销售客户, 出库单流水号 FROM `云之家_原料开票申请记录` WHERE 流程状态='进行中' ORDER BY 制单日期 DESC LIMIT 5")

# ===== 构建数据JSON =====
data = {
    "date": D, "yesterday": YD, "weekday": DW,
    "production": {
        "flash_weight": flash_w, "flash_dry_weight": flash_dw,
        "haema_receipt": haema_d,
        "powder": powd_w, "finish_powder": finish_w,
        "aikang": aikang_d,
        "spray_dry": spray_d,
        "fresh_harvest": fresh_d,
        "plan_qty": plan_qty, "wip_qty": wip_qty,
        "y_flash": y_flash, "y_haema": y_haema,
        "y_aikang": y_aikang, "y_spray": y_spray, "y_fresh": y_fresh,
        "total_output_summary": {
            "flash": f"{fmt(flash_w)} kg / 干重{fmt(flash_dw)} kg" if flash_w and flash_w != "0" and flash_w != "❓" else "无产出",
            "aikang": f"{fmt(aikang_d)} 件" if aikang_d and aikang_d != "0" and aikang_d != "❓" else "无产出",
            "haema": f"{fmt(haema_d)} kg" if haema_d and haema_d != "0" and haema_d != "❓" else "无入库",
            "spray": f"{fmt(spray_d)} kg" if spray_d and spray_d != "0" and spray_d != "❓" else "无产出",
            "fresh": f"{fmt(fresh_d)} kg" if fresh_d and fresh_d != "0" and fresh_d != "❓" else "无采收",
            "powder": f"{fmt(powd_w)} kg" if powd_w and powd_w != "0" and powd_w != "❓" else "无产出",
            "finish": f"{fmt(finish_w)} kg" if finish_w and finish_w != "0" and finish_w != "❓" else "无产出",
        }
    },
    "supply": {
        "pur_amt": pur_amt, "pur_items": pur_items,
        "y_pur_amt": y_pur,
        "ret_cnt": ret_cnt, "ret_amt": ret_amt,
        "pay_cnt": pay_cnt, "pay_amt": pay_amt, "pay_mat": pay_mat,
        "rcv_cnt": rcv_cnt, "rcv_amt": rcv_amt,
        "suppliers_top5": [l.split("\t") for l in (sup_top or "").split("\n") if "\t" in l],
        "pay_top5": [l.split("\t") for l in (pay_top or "").split("\n") if "\t" in l],
        "rcv_top5": [l.split("\t") for l in (rcv_top or "").split("\n") if "\t" in l],
    },
    "sales": {
        "sale_amt": sale_amt, "sale_cnt": sale_cnt,
        "sale_cust": sale_cust, "y_sale_amt": y_sale,
        "pend_cnt": pend_cnt, "pend_amt": pend_amt,
        "pend_top5": [l.split("\t") for l in (pend_top or "").split("\n") if "\t" in l],
    },
    "contract": {
        "pending_cnt": contract_pending,
        "pending_qty": contract_pending_qty,
        "pending_top": [l.split("\t") for l in (contract_pending_top or "").split("\n") if "\t" in l],
        "total": contract_total,
        "completed": contract_completed,
    },
    "outbound": {
        "today_cnt": today_outbound,
        "pending_cnt": today_outbound_pending,
        "top5": [l.split("\t") for l in (today_outbound_top or "").split("\n") if "\t" in l],
    },
    "invoice": {
        "pending_cnt": pending_invoice,
        "top5": [l.split("\t") for l in (pending_invoice_top or "").split("\n") if "\t" in l],
    },
}

# 如果只要求数据就退出
if "--data-only" in sys.argv:
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(0)

# ===== 标准排版（代码格式化） =====
def tab_html(raw, cols):
    """从MySQL tab分隔输出构造Markdown表格"""
    header = "| " + " | ".join(cols) + " |\n"
    sep = "|" + "|".join(":---" for _ in cols) + "|\n"
    rows = ""
    for line in (raw or "").split("\n"):
        if "\t" in line:
            p = line.split("\t")
            rows += "| " + " | ".join(p[i] for i in range(len(p))) + " |\n"
    if not rows.strip():
        rows = f"| {' | '.join(['—' for _ in cols])} |\n"
    return header + sep + rows

aikang_rows = ""
for line in (aikang_detail or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        aikang_rows += f"| {p[0]} | {p[1]} | {p[2]} |\n"
if not aikang_rows.strip():
    aikang_rows = "| （当日无生产记录） | | |"

sup_rows = ""
for line in (sup_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        sup_rows += f"| {p[0]} | {p[1]} | {p[2]} | {fmt_w(p[3])} | {fmt_w(p[4])} |\n"

pay_rows = ""
for line in (pay_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        pay_rows += f"| {p[0]} | {fmt_w(p[1])} |\n"

rcv_rows = ""
for line in (rcv_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        rcv_rows += f"| {p[0]} | {fmt_w(p[1])} |\n"

pend_rows = ""
for line in (pend_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        pend_rows += f"| {p[0]} | {fmt_w(p[1])} |\n"

contract_rows = ""
for line in (contract_pending_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        contract_rows += f"| {p[0]} | {p[1]} | {fmt(p[2])} | {p[3]} |\n"
if not contract_rows.strip():
    contract_rows = "| （当日无待发货合同） | | | |"

outbound_rows = ""
for line in (today_outbound_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        outbound_rows += f"| {p[0]} | {p[1]} | {p[2]} |\n"
if not outbound_rows.strip():
    outbound_rows = "| （今日无出库申请） | | |"

invoice_rows = ""
for line in (pending_invoice_top or "").split("\n"):
    if "\t" in line:
        p = line.split("\t")
        invoice_rows += f"| {p[0]} | {p[1]} | {p[2]} |\n"
if not invoice_rows.strip():
    invoice_rows = "| （无待开票合同） | | |"

# ===== 构建标准部分Markdown（不含决策建议） =====
warn_md = ""
if QUERY_FAILURES:
    warn_md = f"> ⚠️ **数据预警**：以下指标因MySQL超时/中断无法采集，显示 ❓（查询失败），请检查数据库连接：_{'; '.join(QUERY_FAILURES)}_\n>\n"
header_md = f"""{warn_md}# 产供销存日报 · {D}（{DW}）

**数据日期**：{D} | **环比昨日**：{YD}

---

## 🏭 产 · 生产

### ① 今日产线一览
| 产线 | 今日产量 | 昨日产量 | 环比 |
|:---|:-------:|:-------:|:----:|
| 闪蒸干燥粉 | {fmt(flash_w)} kg | {fmt(y_flash)} kg | {pct(flash_w, y_flash)} |
| 雨生红球藻入库 | {fmt(haema_d)} kg | {fmt(y_haema)} kg | {pct(haema_d, y_haema)} |
| 爱尔康 | {fmt(aikang_d)} 件 | {fmt(y_aikang)} 件 | {pct(aikang_d, y_aikang)} |
| 喷雾干燥 | {fmt(spray_d)} kg | {fmt(y_spray)} kg | {pct(spray_d, y_spray)} |
| 鲜品采收 | {fmt(fresh_d)} kg | {fmt(y_fresh)} kg | {pct(fresh_d, y_fresh)} |
| 破壁粉 | {fmt(powd_w)} kg | — | — |
| 成品破壁粉 | {fmt(finish_w)} kg | — | — |

### ② 爱尔康产品明细
| 类别 | 规格 | 数量 |
|:---|:----|:----:|
{aikang_rows}

### ③ 计划+在制（金蝶）
| 指标 | 数值 |
|:----|:----:|
| 计划数量 | {fmt(plan_qty)} |
| 在制数量 | {fmt(wip_qty)} |

---

## 📦 供 · 采购供应

### ④ 采购入库总金额
| 指标 | 今日 | 昨日 | 环比 |
|:----|:---:|:---:|:----:|
| 入库金额 | {fmt_w(pur_amt)} | {fmt_w(y_pur)} | {pct(pur_amt, y_pur)} |
| 入库项数 | {pur_items} | — | — |

### ⑤ 今日到货供应商
| 供应商 | 物料名称 | 数量 | 含税单价 | 含税金额 |
|:-----|:-------|:----:|:-------:|:-------:|
{sup_rows}

### ⑥ 退货预警 · ⑦ 今日实际付款 · ⑧ 今日实际回款
| 指标 | 数值 |
|:----|:----:|
| 退货记录 | {ret_cnt} 条，金额{fmt_w(ret_amt)} |
| 实际付款 | {pay_cnt} 笔，{fmt_w(pay_amt)}（材料采购{fmt_w(pay_mat)}） |
| 实际回款 | {rcv_cnt} 笔，{fmt_w(rcv_amt)} |

| 付款TOP | 金额 |
|:------|:----|
{pay_rows}| 回款TOP | 金额 |
|:------|:----|
{rcv_rows}

---

## 🛒 销 · 销售

### ⑨ 销售订单
| 指标 | 今日 | 昨日 | 环比 |
|:----|:---:|:---:|:----:|
| 销售金额 | {fmt_w(sale_amt)} | {fmt_w(y_sale)} | {pct(sale_amt, y_sale)} |
| 订单数 | {sale_cnt} 单 | — | — |
| 客户数 | {sale_cust} 家 | — | — |

### ⑩ 待审核订单
| 指标 | 数值 |
|:----|:----:|
| 待审笔数 | {pend_cnt} 笔，金额 {fmt_w(pend_amt)} |

| 客户 | 金额 |
|:----|:----|
{pend_rows}

## 📋 合同 Pipeline · 待发货合同

### ⑪ 待发货合同概览
| 指标 | 数值 |
:----|:----:|
| 合同总数 | {contract_total} |
| 已完成 | {contract_completed} |
| 待发货项数 | {contract_pending} 项 |
| 待发货总量 | {fmt(contract_pending_qty)} |

### ⑫ 待发货明细（Top5）
| 客户 | 产品 | 待发货量 | 用途 |
:---|:----|:-------:|:----:|
{contract_rows}

## 📦 出库与开票

### ⑬ 今日出库申请
| 指标 | 数值 |
:----|:----:|
| 今日出库 | {today_outbound} 条 |\n| 进行中 | {today_outbound_pending} 条 |

| 销售人员 | 客户 | 是否开票 |
:---|:----|:----:|
{outbound_rows}

### ⑭ 待开票合同
| 指标 | 数值 |
:----|:----:|
| 待开票数 | {pending_invoice} 条 |

| 销售人员 | 客户 | 出库单流水号 |
:---|:----|:----:|
{invoice_rows}

---

"""

# ===== 决策建议 =====
def generate_advice():
    """
    基于当日数据，分产/供/销三视角生成决策建议。
    规则驱动，不依赖API调用。
    """
    lines = []
    alerts = []   # 异常提醒
    actions = []  # 行动建议
    insights = [] # 趋势洞察

    # ─── 🏭 产线分析 ───
    # 定义产线（名称, 今日值, 昨日值, 单位, 有昨日对比）
    prod_lines = [
        ("闪蒸干燥粉", flash_w, y_flash, "kg", True),
        ("雨生红球藻入库", haema_d, y_haema, "kg", True),
        ("爱尔康", aikang_d, y_aikang, "件", True),
        ("喷雾干燥", spray_d, y_spray, "kg", True),
        ("鲜品采收", fresh_d, y_fresh, "kg", True),
        ("破壁粉", powd_w, None, "kg", False),
        ("成品破壁粉", finish_w, None, "kg", False),
    ]

    has_production = False
    zero_lines = []
    drop_lines = []
    surge_lines = []

    for name, today, yesterday, unit, has_y in prod_lines:
        tv = sf(today)
        if tv is not None:
            has_production = True
        else:
            zero_lines.append(name)
            continue
        if not has_y or yesterday is None:
            continue
        yv = sf(yesterday)
        if yv is None:
            continue
        chg = analyze_pct(today, yesterday)
        if chg is not None:
            if chg > 30:
                surge_lines.append((name, chg, unit))
            elif chg < -30:
                drop_lines.append((name, chg, unit))

    # 产线异常
    if drop_lines:
        for name, chg, unit in drop_lines:
            alerts.append(f"**{name}** 环比骤降{abs(chg):.0f}%，建议排查排产或设备异常")
    if surge_lines:
        for name, chg, unit in surge_lines:
            insights.append(f"**{name}** 环比暴增{chg:.0f}%，如非补单则产能回升")
    if not has_production:
        alerts.append("当日全线无产出，建议确认是否为休息日或停产检修")

    # 计划vs在制
    pv = sf(plan_qty)
    wv = sf(wip_qty)
    if pv is not None and wv is not None and pv > 0:
        wip_ratio = wv / pv
        if wip_ratio > 0.8:
            insights.append(f"在制/计划比={wip_ratio:.0%}，产能接近饱和，订单交期需关注")
        elif wip_ratio < 0.2 and pv > 0:
            actions.append(f"在制率仅{wip_ratio:.0%}，可适当增加排产任务")

    # 爱尔康品类结构
    tv_aikang = sf(aikang_d)
    if tv_aikang is not None and aikang_detail and aikang_detail.strip():
        aikang_rows_raw = [l for l in aikang_detail.split("\n") if "\t" in l]
        if aikang_rows_raw:
            top_cat = aikang_rows_raw[0].split("\t")[0]
            top_qty = aikang_rows_raw[0].split("\t")[2] if len(aikang_rows_raw[0].split("\t")) > 2 else "0"
            insights.append(f"爱尔康主力品类为**{top_cat}**（{top_qty}件），占当日主要产能")

    # ─── 📦 供应分析 ───
    # 采购环比
    pur_chg = analyze_pct(pur_amt, y_pur)
    if pur_chg is not None:
        if pur_chg > 30:
            alerts.append(f"采购入库额环比增长{pur_chg:.0f}%，关注库存积压风险")
        elif pur_chg < -30:
            alerts.append(f"采购入库额环比骤降{abs(pur_chg):.0f}%，关注供应短缺风险")
        else:
            insights.append(f"采购入库额环比{pct(pur_amt, y_pur)}，供应节奏正常")

    # 退货
    ret_v = sf(ret_cnt)
    if ret_v is not None and ret_v > 0:
        ret_amt_v = sf(ret_amt)
        amt_str = f"，涉及金额{fmt_w(ret_amt)}" if ret_amt_v else ""
        alerts.append(f"今日发生退货{int(ret_v)}笔{amt_str}，建议核实退货原因并跟进供应商质量")

    # 资金：付款 vs 回款
    pay_v = sf(pay_amt)
    rcv_v = sf(rcv_amt)
    if pay_v is not None and rcv_v is not None:
        gap = pay_v - rcv_v
        if gap > 0:
            actions.append(f"当日资金净流出{fmt_w(gap)}（付{fmt_w(pay_v)}收{fmt_w(rcv_v)}），关注现金流短期压力")
        elif gap < 0:
            insights.append(f"当日资金净流入{fmt_w(abs(gap))}（收{fmt_w(rcv_v)}付{fmt_w(pay_v)}），回款健康")

    # 供应商集中度
    if sup_top and sup_top.strip():
        sup_rows_raw = [l for l in sup_top.split("\n") if "\t" in l]
        if len(sup_rows_raw) >= 1:
            top_sup = sup_rows_raw[0].split("\t")[0]
            top_sup_amt = sf(sup_rows_raw[0].split("\t")[4]) if len(sup_rows_raw[0].split("\t")) > 4 else None
            total_pur = sf(pur_amt)
            if top_sup_amt is not None and total_pur is not None and total_pur > 0:
                conc = top_sup_amt / total_pur
                if conc > 0.5:
                    alerts.append(f"供应商集中度过高：**{top_sup}** 占比{conc:.0%}，建议分散采购风险")

    # 退货率分析
    ret_v = sf(ret_cnt)
    pur_items_v = sf(pur_items)
    if ret_v is not None and pur_items_v is not None and pur_items_v > 0:
        ret_rate = ret_v / pur_items_v
        if ret_rate > 0.3:
            alerts.append(f"退货率高达{ret_rate:.0%}（{int(ret_v)}/{int(pur_items_v)}项），供应商质量需重点关注")

    # 采购销售比
    pur_v = sf(pur_amt)
    sale_v = sf(sale_amt)
    if pur_v is not None and sale_v is not None and sale_v > 0:
        pur_sale_ratio = pur_v / sale_v
        if pur_sale_ratio > 2:
            actions.append(f"采购额是销售额的{pur_sale_ratio:.1f}倍，关注库存积压风险")
        elif pur_sale_ratio < 0.5:
            insights.append(f"采购额仅为销售额的{pur_sale_ratio:.1f}倍，可能在消耗库存")

    # 付款结构分析
    pay_v2 = sf(pay_amt)
    pay_mat_v = sf(pay_mat)
    if pay_v2 is not None and pay_mat_v is not None and pay_v2 > 0:
        mat_ratio = pay_mat_v / pay_v2
        if mat_ratio < 0.3:
            insights.append(f"材料采购付款仅占{mat_ratio:.0%}，其他付款（工资/费用等）占比偏高")

    # ─── 🛒 销售分析 ───
    sale_chg = analyze_pct(sale_amt, y_sale)
    if sale_chg is not None:
        if sale_chg > 30:
            insights.append(f"销售额环比暴增{sale_chg:.0f}%，如非异常则需求回暖")
        elif sale_chg < -30:
            alerts.append(f"销售额环比骤降{abs(sale_chg):.0f}%，需排查丢单或客户流失")
        else:
            insights.append(f"销售额环比{pct(sale_amt, y_sale)}，销售节奏平稳")

    pend_v = sf(pend_cnt)
    pend_a = sf(pend_amt)
    if pend_v is not None and pend_v > 0:
        actions.append(f"待审核订单{int(pend_v)}笔（{fmt_w(pend_amt)}），建议优先审批避免交期延误")
    if pend_v is not None and pend_v > 5:
        alerts.append(f"待审订单积压{int(pend_v)}笔，存在交期风险，需加快审批流程")

    # 客户集中度
    sale_total = sf(sale_amt)
    if sale_total is not None and sale_total > 0 and pend_top and pend_top.strip():
        pend_rows_raw = [l for l in pend_top.split("\n") if "\t" in l]
        if pend_rows_raw:
            top_cust = pend_rows_raw[0].split("\t")[0]
            top_cust_amt = sf(pend_rows_raw[0].split("\t")[1]) if len(pend_rows_raw[0].split("\t")) > 1 else None
            if top_cust_amt is not None:
                conc = top_cust_amt / sale_total if sale_total > 0 else 0
                if conc > 0.5:
                    alerts.append(f"客户集中度偏高：**{top_cust}** 占当日销售额{conc:.0%}")
    # ─── 📋 合同Pipeline分析 ───
    cp_v = sf(contract_pending)
    cp_qty_v = sf(contract_pending_qty)
    ct_v = sf(contract_total)
    cc_v = sf(contract_completed)
    if cp_v is not None and cp_v > 0:
        actions.append(f"待发货合同{int(cp_v)}项（总量{fmt(contract_pending_qty)}），建议跟进发货计划避免客户催单")
    if cp_v is not None and ct_v is not None and ct_v > 0:
        cp_rate = cp_v / ct_v
        if cp_rate > 0.5:
            alerts.append(f"待发货占比{cp_rate:.0%}（{int(cp_v)}/{int(ct_v)}项），合同执行率偏低，需排查原因")
    if cp_qty_v is not None and cp_qty_v > 1000:
        insights.append(f"待发货总量{fmt(contract_pending_qty)}，集中在虾青素油/微囊粉等核心产品，建议优先排产")

    # ─── 📦 出库与开票分析 ───
    ob_cnt = sf(today_outbound)
    ob_pend = sf(today_outbound_pending)
    inv_pend = sf(pending_invoice)
    if ob_cnt is not None and int(ob_cnt) > 0:
        insights.append(f"今日出库申请{int(ob_cnt)}条，出库执行正常")
    if ob_pend is not None and int(ob_pend) > 3:
        alerts.append(f"出库申请有{int(ob_pend)}条进行中，建议跟进出库进度")
    if inv_pend is not None and int(inv_pend) > 5:
        actions.append(f"待开票合同{int(inv_pend)}条，建议财务部门加快开票处理")
    if inv_pend is not None and int(inv_pend) > 0 and ob_cnt is not None and int(ob_cnt) > 0:
        pipeline_rate = int(inv_pend) / int(ob_cnt) if int(ob_cnt) > 0 else 0
        if pipeline_rate > 0.5:
            insights.append(f"出库→开票转化率偏低（待开票/今日出库={pipeline_rate:.0%}），开票环节可能积压")

    # ─── 汇总生成 ───
    parts = []
    if alerts:
        parts.append("### ⚠️ 需关注事项\n")
        for a in alerts:
            parts.append(f"- {a}")
        parts.append("")
    if actions:
        parts.append("### 💡 行动建议\n")
        for a in actions:
            parts.append(f"- {a}")
        parts.append("")
    if insights:
        parts.append("### 📊 趋势洞察\n")
        for i_val in insights:
            parts.append(f"- {i_val}")
        parts.append("")

    if not parts:
        return ""  # 无建议时跳过
    result = "\n".join(parts)
    return result + "\n\n---\n\n"

# ===== 生成决策建议 =====
# 旧模式：--advice 参数注入（兼容），新模式：自动生成
advice_md = ""
if "--advice" in sys.argv:
    for i, arg in enumerate(sys.argv):
        if arg == "--advice" and i + 1 < len(sys.argv):
            inp = sys.argv[i + 1]
            if os.path.isfile(inp):
                with open(inp) as f:
                    advice_md = f.read()
            else:
                advice_md = inp
            break
if not advice_md:
    advice_md = generate_advice()

footer_md = """>
📋 **日报指标**：产(3)一览表+爱尔康明细+计划 | 供(3)采购+退货+付款+回款 | 销(2)销售+待审核 | 合同(2)待发货概览+待发货明细 | 出库开票(2)今日出库+待开票 | 合计12指标
"""

full_md = header_md + advice_md + footer_md

# ===== 推送 =====
GEN_TODAY = datetime.now().strftime("%Y%m%d")
TITLE = f"产供销存日报 · {D}（{DW}）[{GEN_TODAY}]"
force = "--force" in sys.argv
skip_push = False
try:
    sr = ima("openapi/note/v1/search_note", {"search_type":0,"query_info":{"title":TITLE},"start":0,"end":5})
    if sr and sr.get("error"):
        logging.warning(f"搜索笔记失败，将强制推送: {sr['error']}")
        force = True  # 搜索失败时强制推送，避免永远不推送
    existing = sr.get("search_note_infos") or []
    if existing and not force:
        print(f"⚠️ 已存在同名笔记，跳过创建。如需覆盖请加 --force")
        skip_push = True
except Exception as e:
    logging.warning(f"搜索笔记异常: {e}，将尝试强制推送")
    force = True

if not skip_push:
    try:
        note_data = ima("openapi/note/v1/import_doc", {"title": TITLE, "content": full_md, "content_format": 1})
        if note_data.get("error"):
            print(f"❌ 创建笔记失败: {note_data['error']}")
            sys.exit(1)
        note_id = note_data.get("note_id") or note_data.get("id")
        print(f"📝 笔记已创建 note_id={note_id}")
        kb_data = ima("openapi/wiki/v1/add_knowledge", {"media_type":11,"note_info":{"content_id":note_id},"title":TITLE,"knowledge_base_id":KB_ID,"folder_id":FOLDER_ID})
        if kb_data.get("error"):
            print(f"❌ 添加到知识库失败: {kb_data['error']}")
        else:
            print(f"✅ 日报已推送 → {D}（{DW}）")
    except Exception as e:
        print(f"❌ 推送失败: {e}")
        logging.error(f"推送日报失败: {e}")
        sys.exit(1)
else:
    print(f"⏭️ {TITLE} 已有笔记，未推送")

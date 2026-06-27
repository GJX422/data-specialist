#!/usr/bin/env python3
"""数据健康看板 v4 — 区分源端无数据 vs 同步失败"""
import pymysql, json, os, calendar, subprocess
from datetime import datetime, date

DB = {'host':'127.0.0.1','port':53306,'user':'root','password':'root@2026!FineBI','db':'yunzhijia','charset':'utf8mb4'}
OUTPUT = '/root/.hermes/data_health_dashboard.html'

# ── 每个表对应的同步脚本及最新运行状态 ──
# 格式: { "表名": "同步cron脚本名或job_name关键词" }
TABLE_SYNC_MAP = {
    # 云之家所有表 ← 云之家每日同步 (02:30)
    "云之家_闪蒸干燥粉记录": "云之家数据每日同步",
    "云之家_破壁粉记录": "云之家数据每日同步",
    "云之家_成品破壁粉记录": "云之家数据每日同步",
    "云之家_爱尔康生产明细": "云之家数据每日同步",
    "云之家_喷雾干燥生产明细": "云之家数据每日同步",
    "云之家_鲜品采收明细": "云之家数据每日同步",
    "云之家_雨生红球藻入库明细": "云之家数据每日同步",
    "云之家_饲料原料记录": "饲料原料（产）同步",
    "云之家_工作日报": "云之家数据每日同步",
    "云之家_费用报销申请": "云之家数据每日同步",
    "云之家_用款申请": "云之家数据每日同步",
    "云之家_采购用款申请": "云之家数据每日同步",
    "云之家_预算变动流水": "云之家数据每日同步",
    "云之家_月度工作计划": "云之家数据每日同步",
    "云之家_原料销售订单记录": "云之家数据每日同步",
    # 金蝶所有表 ← 金蝶每日增量同步 (02:45)
    "金蝶_销售订单主表": "金蝶每日增量同步",
    "金蝶_采购入库单主表": "金蝶每日增量同步",
    "金蝶_付款单": "金蝶每日增量同步",
    "金蝶_收款单": "金蝶每日增量同步",
    "金蝶_计划产出单": "金蝶每日增量同步",
    "金蝶_实际产出单": "金蝶每日增量同步",
    "金蝶_成本记录": "金蝶每日增量同步",
    "金蝶_成本调整单": "金蝶每日增量同步",
    "金蝶_入库核算单": "金蝶每日增量同步",
    "金蝶_出库核算单": "金蝶每日增量同步",
    # 考勤 ← 独立同步 (03:10)
    "考勤记录": "云之家考勤记录同步",
    # 终端品销售 ← 独立同步 (03:30)
    "云之家_终端品销售订单": "终端品销售订单每日增量同步",
    # 付款申请 ← 云之家每日同步（同一批）
    "付款单（爱尔发）": "云之家数据每日同步",
    "付款单（爱尔康）": "云之家数据每日同步",
}

# ── 读取cron任务状态 ──
def get_sync_status():
    """返回 { sync_job_name: (last_status, last_run_at) }"""
    try:
        jobs = json.loads(open('/root/.hermes/cron/jobs.json').read()).get('jobs', {})
        result = {}
        for jid, j in jobs.items():
            name = j.get('name', '')
            result[name] = (j.get('last_status'), j.get('last_run_at', ''))
        return result
    except:
        return {}

sync_statuses = get_sync_status()

def check_sync_error(tbl_name):
    """检查该表的同步脚本最近是否出错。返回 True=同步异常, False=同步正常"""
    job_key = TABLE_SYNC_MAP.get(tbl_name)
    if not job_key:
        return False
    # 模糊匹配job name
    for name, (status, run_at) in sync_statuses.items():
        if job_key in name:
            return status == 'error'
    return False

# ── 报表系统分组 ──
REPORT_GROUPS = [
    {"name":"📋 产供销存日报","desc":"每天生成，覆盖生产→采购→销售→收付款全链路",
     "tables":[
        ("云之家_闪蒸干燥粉记录","生产日期","产线停产"),("云之家_破壁粉记录","生产日期","产线停产"),
        ("云之家_成品破壁粉记录","生产日期","产线停产"),("云之家_爱尔康生产明细","生产日期","补录模式"),
        ("云之家_喷雾干燥生产明细","生产日期","补录模式"),("云之家_鲜品采收明细","日期","采收季"),
        ("云之家_雨生红球藻入库明细","入库日期","低频"),("金蝶_销售订单主表","业务日期",""),
        ("云之家_饲料原料记录","生产日期","低频"),
        ("金蝶_采购入库单主表","业务日期",""),("金蝶_付款单","业务日期","不走此通道"),
        ("金蝶_收款单","业务日期","月结模式"),("金蝶_计划产出单","业务日期","月结停更"),
    ]},
    {"name":"📋 产供销存周报","desc":"每周一推送，日报基础上增加原料销售",
     "tables":[
        ("云之家_闪蒸干燥粉记录","生产日期","产线停产"),("云之家_破壁粉记录","生产日期","产线停产"),
        ("云之家_成品破壁粉记录","生产日期","产线停产"),("云之家_爱尔康生产明细","生产日期",""),
        ("云之家_喷雾干燥生产明细","生产日期",""),("云之家_鲜品采收明细","日期",""),
        ("云之家_雨生红球藻入库明细","入库日期",""),("云之家_原料销售订单记录","申请日期",""),
        ("云之家_饲料原料记录","生产日期",""),
        ("金蝶_销售订单主表","业务日期",""),("金蝶_采购入库单主表","业务日期",""),
        ("金蝶_付款单","业务日期","不走此通道"),("金蝶_收款单","业务日期","月结模式"),
    ]},
    {"name":"📋 产供销存月报","desc":"次月1日推送，全面覆盖所有成本/核算维度",
     "tables":[
        ("云之家_闪蒸干燥粉记录","生产日期","产线停产"),("云之家_破壁粉记录","生产日期","产线停产"),
        ("云之家_成品破壁粉记录","生产日期","产线停产"),("云之家_爱尔康生产明细","生产日期",""),
        ("云之家_喷雾干燥生产明细","生产日期",""),("云之家_鲜品采收明细","日期",""),
        ("云之家_雨生红球藻入库明细","入库日期",""),("云之家_原料销售订单记录","申请日期",""),
        ("云之家_饲料原料记录","生产日期",""),
        ("云之家_用款申请","制单日期",""),("云之家_预算变动流水","申请日期",""),
        ("金蝶_销售订单主表","业务日期",""),("金蝶_采购入库单主表","业务日期",""),
        ("金蝶_付款单","业务日期","不走此通道"),("金蝶_收款单","业务日期","月结模式"),
        ("金蝶_计划产出单","业务日期","月结停更"),("金蝶_实际产出单","业务日期","月结停更"),
        ("金蝶_成本记录","业务日期",""),("金蝶_成本调整单","业务日期",""),
        ("金蝶_入库核算单","业务日期",""),("金蝶_出库核算单","业务日期",""),
    ]},
    {"name":"📊 成本收入分析","desc":"次月中下旬推送，产出成本+销售+费用多维分析",
     "tables":[
        ("金蝶_成本记录","业务日期",""),("金蝶_成本调整单","业务日期",""),
        ("金蝶_销售订单主表","业务日期",""),("金蝶_采购入库单主表","业务日期",""),
        ("云之家_费用报销申请","制单日期",""),("云之家_用款申请","制单日期",""),
    ]},
    {"name":"📊 利润分析","desc":"产成品成本×销量估算毛利率",
     "tables":[("金蝶_成本记录","业务日期",""),("金蝶_销售订单主表","业务日期","")]},
    {"name":"📊 回款分析","desc":"收款跟踪",
     "tables":[("金蝶_收款单","业务日期","月结模式"),("金蝶_销售订单主表","业务日期","")]},
    {"name":"🔍 采购单价监控","desc":"每天08:30检查采购入库超价",
     "tables":[("金蝶_采购入库单主表","业务日期","")]},
    {"name":"🔍 供应商分析","desc":"供应商集中度/到货时效分析",
     "tables":[("金蝶_采购入库单主表","业务日期","")]},
    {"name":"💰 预算执行追踪","desc":"预算余额&付款执行进度",
     "tables":[("云之家_预算变动流水","申请日期",""),("付款单（爱尔发）","业务日期",""),("付款单（爱尔康）","业务日期","")]},
    {"name":"📝 工作日报分析","desc":"产供销工作日报综合评分，每天03:30",
     "tables":[("云之家_工作日报","填写日期","正常")]},
    {"name":"📝 工作计划追踪","desc":"月度计划执行率追踪(日报关键词匹配)",
     "tables":[("云之家_月度工作计划","制单日期","月度"),("云之家_工作日报","填写日期","")]},
    {"name":"🏷️ 终端品销售","desc":"终端品销售订单",
     "tables":[("云之家_终端品销售订单","制单日期","")]},
    {"name":"🍽️ 就餐对账","desc":"每天10:00考勤打卡 vs 报饭人数对账",
     "tables":[("考勤记录","打卡时间","")]},
]

STOPPED_LINES = {}

conn = pymysql.connect(**DB)
cur = conn.cursor()

today = date.today()
this_ym = today.strftime("%Y-%m")
_, this_last = calendar.monthrange(today.year, today.month)
this_days = [date(today.year, today.month, d) for d in range(1, this_last + 1)]

months_to_query = []
for m in range(1, today.month + 1):
    _, ld = calendar.monthrange(today.year, m)
    months_to_query.append((today.year, m, ld))

weekday_names = ["日","一","二","三","四","五","六"]

# ── 查询所有表的所有月份数据 ──
table_cache = {}  # tbl -> {"2026-06": {"01": "green|red|yellow", ...}, ...}

for group in REPORT_GROUPS:
    for tbl, date_col, _ in group["tables"]:
        if tbl in table_cache:
            continue
        print(f"查询: {tbl} ...")
        stop_date = STOPPED_LINES.get(tbl)
        sync_error = check_sync_error(tbl)  # 同步是否最近出错过
        if sync_error:
            print(f"  ⚠️ 同步脚本最近出错，该表可能出现黄灯")
        
        all_months = {}
        for yr, mo, ld in months_to_query:
            ym = f"{yr}-{mo:02d}"
            all_months[ym] = {}
            for d in range(1, ld + 1):
                d_date = date(yr, mo, d)
                d_str = d_date.strftime("%Y-%m-%d")
                key = f"{d:02d}"
                
                # 已确认知停产的产线 → 红灯（源端无数据）
                if stop_date and d_str > stop_date:
                    all_months[ym][key] = 'red'
                    continue
                
                try:
                    # 所有日期列统一用DATE()函数包裹，兼容DATE和DATETIME两种类型
                    sql = f"SELECT COUNT(*) FROM `{tbl}` WHERE DATE(`{date_col}`) = '{d_str}'"
                    cur.execute(sql)
                    cnt = cur.fetchone()[0]
                    
                    if cnt > 0:
                        all_months[ym][key] = 'green'
                    else:
                        # 无数据：判断是源端没数据还是同步失败
                        if sync_error:
                            all_months[ym][key] = 'yellow'  # 同步异常
                        else:
                            all_months[ym][key] = 'red'  # 源端无数据
                except Exception as e:
                    all_months[ym][key] = 'yellow'
                    print(f"  ⚠️ 查询异常 {tbl} {d_str}: {e}")
        
        table_cache[tbl] = all_months

conn.close()

# ── 统计 ──
all_tables_set = set()
total_cells = 0; g_total = r_total = y_total = 0
for group in REPORT_GROUPS:
    for tbl, _, _ in group["tables"]:
        if tbl not in all_tables_set:
            all_tables_set.add(tbl)
            for ym_data in table_cache.get(tbl, {}).values():
                for v in ym_data.values():
                    total_cells += 1
                    if v == 'green': g_total += 1
                    elif v == 'red': r_total += 1
                    elif v == 'yellow': y_total += 1

print(f"\n   🟢{g_total} 🔴{r_total} 🟡{y_total} (总计{total_cells})")

# ── 生成HTML（明亮Bento Grid风格）──
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>数据健康看板 · {this_ym}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
    background: #f0f2f5;
    color: #1f2937;
    padding: 32px 24px;
    min-height: 100vh;
  }}
  .container {{ max-width: 1440px; margin: 0 auto; }}

  /* ── Header ── */
  .header {{
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 24px; flex-wrap: wrap; gap: 16px;
  }}
  .header-left {{ }}
  .ym-title {{
    font-size: 28px; font-weight: 800;
    color: #111827; letter-spacing: 1px;
    margin-bottom: 2px;
  }}
  .ym-sub {{ font-size: 14px; color: #6b7280; }}
  .header-right {{
    display: flex; align-items: center; gap: 12px;
    background: #fff; padding: 8px 16px; border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  .update-time {{ font-size: 13px; color: #6b7280; white-space: nowrap; }}
  .badge {{
    font-size: 11px; background: #ecfdf5; color: #059669;
    padding: 4px 12px; border-radius: 20px;
    border: 1px solid #a7f3d0; font-weight: 600;
    white-space: nowrap;
  }}

  /* ── Summary Bar ── */
  .summary {{
    display: flex; align-items: center; gap: 24px;
    margin-bottom: 28px; flex-wrap: wrap;
    background: #fff;
    border-radius: 16px; padding: 20px 28px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }}
  .summary-item {{ display: flex; align-items: center; gap: 10px; font-size: 14px; color: #374151; }}
  .summary-item .num {{ font-size: 28px; font-weight: 800; }}
  .dot {{ width: 14px; height: 14px; border-radius: 50%; display: inline-block; flex-shrink: 0; }}
  .dot-g {{ background: #22c55e; }}
  .dot-r {{ background: #d1d5db; }}
  .dot-y {{ background: #eab308; }}
  .rate-bar {{
    flex: 1; min-width: 180px; height: 10px; border-radius: 6px;
    background: #e5e7eb; overflow: hidden; display: flex;
  }}
  .rate-bar .sg {{ background: #22c55e; }}
  .rate-bar .sr {{ background: #d1d5db; }}
  .rate-bar .sy {{ background: #eab308; }}

  /* ── Groups ── */
  .rgroup {{ margin-bottom: 20px; }}
  .rgroup-header {{
    display: flex; align-items: center; gap: 12px;
    padding: 14px 20px;
    background: #fff;
    border-radius: 14px;
    border-left: 4px solid #3b82f6;
    cursor: pointer;
    transition: all 0.15s;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }}
  .rgroup-header:hover {{
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    transform: translateY(-1px);
  }}
  .rgroup-title {{ font-size: 16px; font-weight: 700; color: #111827; white-space: nowrap; }}
  .rgroup-desc {{ font-size: 12px; color: #9ca3af; }}
  .rgroup-stats {{ margin-left: auto; font-size: 12px; white-space: nowrap; color: #6b7280; }}
  .rgroup-stats .g {{ color:#16a34a; font-weight:600; }}
  .rgroup-stats .r {{ color:#6b7280; font-weight:600; }}
  .rgroup-stats .y {{ color:#ca8a04; font-weight:600; }}
  .month-badge {{
    display: inline-flex; align-items: center; font-size: 12px; font-weight: 700;
    color: #3b82f6; background: #eff6ff;
    padding: 3px 12px; border-radius: 20px; white-space: nowrap;
  }}
  .collapse-btn {{
    background: #fff; border: none;
    color: #3b82f6; cursor: pointer; font-size: 12px; font-weight: 600;
    padding: 6px 14px; border-radius: 8px; margin: 8px 0 4px 0;
    transition: background 0.15s; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }}
  .collapse-btn:hover {{ background: #f0f7ff; }}

  /* ── Table Grid ── */
  .tgrid {{
    display: none;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 12px;
    margin-top: 8px;
  }}
  .tcard {{
    background: #fff;
    border: 1px solid #f3f4f6;
    border-radius: 14px;
    padding: 16px;
    transition: all 0.15s;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
  }}
  .tcard:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    transform: translateY(-2px);
    border-color: #e5e7eb;
  }}
  .tcard-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px;
  }}
  .tcard-name {{ font-size: 14px; font-weight: 700; color: #1f2937; }}
  .tcard-note {{
    font-size: 10px; color: #6b7280;
    background: #f3f4f6; padding: 2px 8px; border-radius: 6px;
    white-space: nowrap;
  }}
  .tcard-stat {{ font-size: 12px; color: #6b7280; margin-bottom: 10px; }}

  /* ── Calendar ── */
  .cal {{ display: flex; flex-direction: column; gap: 2px; }}
  .cal-wd {{
    display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
    font-size: 10px; color: #9ca3af; text-align: center;
    margin-bottom: 2px; font-weight: 600;
  }}
  .cal-r {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }}
  .cal-c {{
    aspect-ratio: 1; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 600;
    position: relative; cursor: default;
  }}
  .cal-c.green {{ background: #dcfce7; color: #166534; }}
  .cal-c.red {{ background: #f3f4f6; color: #9ca3af; }}
  .cal-c.yellow {{ background: #fef9c3; color: #854d0e; }}
  .cal-c.empty {{ background: transparent; color: transparent; }}

  .cal-c .tip {{
    display: none; position: absolute; bottom: calc(100% + 4px);
    left: 50%; transform: translateX(-50%);
    background: #1f2937; color: #fff; padding: 4px 10px;
    border-radius: 6px; font-size: 11px; white-space: nowrap; z-index: 10;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    font-weight: 400;
  }}
  .cal-c:hover .tip {{ display: block; }}

  .tcard-foot {{ margin-top: 10px; text-align: right; }}
  .tcard-foot a {{
    color: #3b82f6; text-decoration: none; cursor: pointer;
    font-size: 12px; font-weight: 600;
  }}
  .tcard-foot a:hover {{ color: #2563eb; text-decoration: underline; }}

  /* ── Legend ── */
  .legend {{
    display: flex; gap: 24px; margin-top: 28px; justify-content: center;
    flex-wrap: wrap;
    background: #fff; border-radius: 14px;
    padding: 14px 24px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
  }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #374151; }}
  .legend-detail {{ font-size: 12px; color: #9ca3af; text-align: center; margin-top: 10px; }}

  /* ── Modal ── */
  .modal-overlay {{
    display: none; position: fixed; z-index: 100; left: 0; top: 0;
    width: 100%; height: 100%; background: rgba(0,0,0,0.5);
    backdrop-filter: blur(4px); overflow-y: auto;
  }}
  .modal-content {{
    background: #fff; margin: 40px auto; max-width: 960px;
    border-radius: 20px; padding: 32px;
    position: relative;
    box-shadow: 0 20px 60px rgba(0,0,0,0.15);
  }}
  .modal-close {{
    position: absolute; top: 16px; right: 20px;
    font-size: 28px; color: #6b7280; cursor: pointer;
    background: none; border: none; line-height: 1;
    transition: color 0.15s;
  }}
  .modal-close:hover {{ color: #111827; }}
  .modal-title {{ font-size: 22px; font-weight: 800; color: #111827; margin-bottom: 24px; }}
  .modal-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px; }}
  .modal-month {{
    background: #f9fafb; border-radius: 14px; padding: 18px;
    border: 1px solid #f3f4f6;
  }}
  .modal-month h3 {{ font-size: 15px; font-weight: 700; margin-bottom: 10px; color: #1f2937; }}
  .modal-month .cal {{ gap: 1px; }}
  .modal-month .cal-c {{ font-size: 11px; }}
  .modal-month .cal-wd {{ font-size: 10px; }}
  .modal-stat {{ font-size: 13px; color: #6b7280; margin-top: 8px; }}

  .footer {{ text-align: center; margin-top: 24px; font-size: 12px; color: #9ca3af; }}

  /* ── Mobile: 600px ── */
  @media (max-width: 600px) {{
    body {{ padding: 14px 10px; }}
    .header {{ flex-direction: column; gap: 10px; }}
    .header-right {{ align-self: stretch; justify-content: center; padding: 8px 12px; }}
    .ym-title {{ font-size: 20px; }}
    .ym-sub {{ font-size: 12px; }}
    .summary {{ flex-direction: column; gap: 10px; padding: 14px 16px; align-items: stretch; }}
    .summary-item {{ justify-content: flex-start; }}
    .summary-item .num {{ font-size: 22px; }}
    .rate-bar {{ min-width: unset; width: 100%; }}
    .rgroup-header {{ flex-wrap: wrap; gap: 8px; padding: 12px 14px; }}
    .rgroup-title {{ font-size: 14px; }}
    .rgroup-desc {{ width: 100%; order: 3; font-size: 11px; margin-top: -2px; }}
    .rgroup-stats {{ margin-left: 0; order: 2; font-size: 11px; }}
    .tgrid {{ grid-template-columns: 1fr; gap: 10px; }}
    .tcard {{ padding: 14px; }}
    .tcard-name {{ font-size: 13px; }}
    .cal-c {{ min-height: 28px; }}
    .cal-c .tip {{ display: none !important; }}
    .cal-c:active .tip, .cal-c:focus .tip {{ display: block !important; bottom: auto; top: calc(100% + 4px); }}
    .legend {{ flex-direction: column; gap: 10px; padding: 12px 16px; }}
    .legend-item {{ font-size: 12px; }}
    .modal-content {{ margin: 8px; padding: 16px; border-radius: 14px; }}
    .modal-title {{ font-size: 18px; }}
    .modal-grid {{ grid-template-columns: 1fr; }}
    .modal-month .cal-c {{ min-height: 30px; }}
  }}

  /* ── Mobile: 380px (very small) ── */
  @media (max-width: 380px) {{
    .ym-title {{ font-size: 18px; }}
    .summary-item .num {{ font-size: 20px; }}
    .tcard-header {{ flex-direction: column; align-items: flex-start; gap: 4px; }}
  }}

  /* ── Tablet: 768px ── */
  @media (min-width: 601px) and (max-width: 900px) {{
    body {{ padding: 20px 16px; }}
    .tgrid {{ grid-template-columns: repeat(2, 1fr); }}
    .rgroup-header {{ padding: 12px 16px; }}
  }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <div class="header-left">
    <div class="ym-title">📊 {today.year}年{today.month}月 数据健康看板</div>
    <div class="ym-sub">按报表系统分组 · 点击组名展开查看明细</div>
  </div>
  <div class="header-right">
    <span class="update-time">更新于 <span id="updateTime">{datetime.now().strftime("%H:%M")}</span></span>
    <span class="badge">⏰ 每天早上8点更新</span>
  </div>
</div>

<div class="summary">
  <div class="summary-item"><span class="dot dot-g"></span> 数据正常 <span class="num" style="color:#16a34a">{g_total}</span></div>
  <div class="summary-item"><span class="dot dot-r"></span> 源端无数据 <span class="num" style="color:#6b7280">{r_total}</span></div>
  <div class="summary-item"><span class="dot dot-y"></span> 同步异常 <span class="num" style="color:#ca8a04">{y_total}</span></div>
  <div class="rate-bar">
    <div class="sg" style="width:{g_total/max(total_cells,1)*100}%"></div>
    <div class="sr" style="width:{r_total/max(total_cells,1)*100}%"></div>
    <div class="sy" style="width:{y_total/max(total_cells,1)*100}%"></div>
  </div>
</div>
"""

# 嵌入JSON数据
tbl_json_str = json.dumps(table_cache, ensure_ascii=False)
html += f'<div id="allData" style="display:none;">{tbl_json_str}</div>\n'

# ── 生成分组 ──
for gi, group in enumerate(REPORT_GROUPS):
    gname = group["name"]; gdesc = group["desc"]
    gg = gr = gy = 0
    gtbl_count = len(group["tables"])
    for tbl, _, _ in group["tables"]:
        days = table_cache.get(tbl, {}).get(this_ym, {})
        for v in days.values():
            if v == 'green': gg += 1
            elif v == 'red': gr += 1
            elif v == 'yellow': gy += 1
    health_pct = round(gg / max(gg+gr+gy, 1) * 100)
    
    html += f'<div class="rgroup">\n'
    html += f'<div class="rgroup-header" onclick="toggleGroup({gi})">'
    html += f'<span class="month-badge">{today.month}月</span>'
    html += f'<div class="rgroup-title">{gname}</div>'
    html += f'<div class="rgroup-desc">{gdesc}</div>'
    html += f'<div class="rgroup-stats">'
    html += f'<span class="g">🟢{gg}</span> <span class="r">🔴{gr}</span> <span class="y">🟡{gy}</span>'
    html += f' 健康率 {health_pct}% · {gtbl_count}个表'
    html += f'</div></div>\n'
    html += f'<button class="collapse-btn" id="b{gi}" onclick="toggleGroup({gi})">展开 ▼</button>\n'
    html += f'<div id="g{gi}" class="tgrid" style="display:none;">\n'
    
    for tbl, date_col, note in group["tables"]:
        days = table_cache.get(tbl, {}).get(this_ym, {})
        g = sum(1 for v in days.values() if v == 'green')
        r = sum(1 for v in days.values() if v == 'red')
        y = sum(1 for v in days.values() if v == 'yellow')
        sync_error = check_sync_error(tbl)
        short = tbl.replace('云之家_','').replace('金蝶_','').replace('付款单（','\n付款（').replace('）','')
        
        html += f'<div class="tcard" data-tbl="{tbl}">'
        html += f'<div class="tcard-header"><span class="tcard-name">{short}</span>'
        if sync_error:
            html += f'<span class="tcard-note" style="color:#eab308;border:1px solid rgba(234,179,8,0.3);">⚠️ 同步异常</span>'
        elif note:
            html += f'<span class="tcard-note">{note}</span>'
        html += '</div>'
        html += f'<div class="tcard-stat">🟢{g} 🔴{r} 🟡{y}</div>'
        html += '<div class="cal"><div class="cal-wd">'
        for wd in weekday_names:
            html += f'<div>{wd}</div>'
        html += '</div><div class="cal-r">'
        
        first_dow = this_days[0].weekday()
        first_sun = (first_dow + 1) % 7
        for _ in range(first_sun):
            html += '<div class="cal-c empty"></div>'
        for d in this_days:
            d_str = d.strftime("%Y-%m-%d")
            status = days.get(f"{d.day:02d}", 'red')
            tip_map = {'green':'✅ 数据正常','red':'⬜ 源端无数据','yellow':'🟡 同步异常'}
            html += f'<div class="cal-c {status}"><span>{d.day}</span>'
            html += f'<div class="tip">{d_str}<br>{tip_map.get(status,"")}</div></div>'
        html += '</div></div>'
        html += f'<div class="tcard-foot"><a href="javascript:void(0)" onclick="showModal(\'{tbl}\')">📅 查看所有月份</a></div>'
        html += '</div>\n'
    
    html += '</div></div>\n'

# ── Modal ──
html += '''
<div id="modal" class="modal-overlay" onclick="if(event.target==this)closeModal()">
  <div class="modal-content">
    <button class="modal-close" onclick="closeModal()">&times;</button>
    <div class="modal-title" id="modalTitle">—</div>
    <div id="modalBody" class="modal-grid"></div>
  </div>
</div>

<script>
function toggleGroup(id) {
  var el = document.getElementById('g'+id);
  var btn = document.getElementById('b'+id);
  if (el.style.display === 'none' || el.style.display === '') {
    el.style.display = 'grid';
    btn.textContent = '收起 ▲';
  } else {
    el.style.display = 'none';
    btn.textContent = '展开 ▼';
  }
}

var ALL_DATA = JSON.parse(document.getElementById('allData').textContent);

function showModal(tblName) {
  var data = ALL_DATA[tblName];
  if (!data) return;
  var short = tblName.replace('云之家_','').replace('金蝶_','').replace('付款单（','付款（').replace('）','');
  document.getElementById('modalTitle').textContent = '📊 ' + short + ' · 全年数据健康';
  
  var body = document.getElementById('modalBody');
  body.innerHTML = '';
  var months = Object.keys(data).sort();
  
  months.forEach(function(ym) {
    var ymData = data[ym];
    var parts = ym.split('-');
    var year = parts[0], month = parts[1];
    var g = 0, r = 0, y = 0;
    Object.values(ymData).forEach(function(v) {
      if (v === 'green') g++;
      else if (v === 'red') r++;
      else if (v === 'yellow') y++;
    });
    var total = g + r + y;
    var health = total > 0 ? Math.round(g / total * 100) : 0;
    
    var firstDay = new Date(parseInt(year), parseInt(month)-1, 1);
    var firstDow = firstDay.getDay();
    var daysInMonth = new Date(parseInt(year), parseInt(month), 0).getDate();
    var wds = ['日','一','二','三','四','五','六'];
    
    var calHtml = '<div class="cal"><div class="cal-wd">';
    wds.forEach(function(w) { calHtml += '<div>'+w+'</div>'; });
    calHtml += '</div><div class="cal-r">';
    for (var i = 0; i < firstDow; i++) calHtml += '<div class="cal-c empty"></div>';
    for (var d = 1; d <= daysInMonth; d++) {
      var key = d < 10 ? '0'+d : ''+d;
      var status = ymData[key] || 'red';
      var tipMap = {'green':'正常','red':'源端无数据','yellow':'同步异常'};
      calHtml += '<div class="cal-c '+status+'"><span>'+d+'</span>';
      calHtml += '<div class="tip">'+year+'-'+month+'-'+key+'<br>'+tipMap[status]+'</div></div>';
    }
    calHtml += '</div></div>';
    
    var monthName = year + '年' + parseInt(month) + '月';
    var monthDiv = '<div class="modal-month"><h3>'+monthName+'</h3>'+calHtml;
    monthDiv += '<div class="modal-stat">🟢'+g+' 🔴'+r+' 🟡'+y+' 健康率 '+health+'%</div></div>';
    body.innerHTML += monthDiv;
  });
  
  document.getElementById('modal').style.display = 'block';
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal').style.display = 'none';
  document.body.style.overflow = '';
}
</script>

<div class="legend">
  <div class="legend-item"><span class="dot dot-g"></span> 数据正常</div>
  <div class="legend-item"><span class="dot dot-r"></span> 源端无数据（同步正常，但源端未产生数据）</div>
  <div class="legend-item"><span class="dot dot-y"></span> 同步异常（同步脚本出错）</div>
</div>
<div class="legend-detail">
  判断依据：同步脚本最近运行正常→源端无数据标记灰色 | 同步脚本出错→标记黄色
</div>

<div class="footer">
  数据健康看板 · c03e6b8b-af07-4894-a67a-c579116a0ae1 · 每天早上8点自动更新
</div>
</div>
</body>
</html>'''

with open(OUTPUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ 看板v4已生成: {OUTPUT}")
print(f"   大小: {os.path.getsize(OUTPUT)} 字节")
print(f"   覆盖 {len(months_to_query)} 个月份，{len(all_tables_set)} 个数据源")

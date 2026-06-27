#!/usr/bin/env python3
"""总经理驾驶舱 - 数据 + HTML 生成器
用法: python3 gen_gm_cockpit.py [--date YYYY-MM-DD] [--output /path/to.html]
默认输出: /tmp/gm_cockpit.html
"""

import os, sys, json, argparse, subprocess, textwrap
from datetime import datetime, timedelta, date

DB = dict(host="127.0.0.1", port=53306, user="root",
          password="root@2026!FineBI", database="yunzhijia")

def q(sql):
    cmd = ["mysql", f"-h{DB['host']}", f"-P{DB['port']}",
           f"-u{DB['user']}", f"-p{DB['password']}",
           DB["database"], "--batch", "--raw", "-e", sql]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0: return []
    lines = r.stdout.strip().split("\n")
    if not lines or len(lines) < 2: return []
    cols = [c.strip() for c in lines[0].split("\t")]
    return [dict(zip(cols, [v.strip() for v in l.split("\t")])) for l in lines[1:]]

def today_production(d):
    rows = []
    r = q(f"SELECT IFNULL(SUM(d.产出_重量),0) as val FROM 云之家_闪蒸干燥粉记录 m JOIN 云之家_闪蒸干燥粉明细 d ON m.流水号=d.流水号 WHERE m.生产日期='{d}' AND d.类型='产出'")
    rows.append({"line":"闪蒸干燥粉","val":float(r[0]["val"]) if r else 0,"unit":"kg"})
    r = q(f"SELECT IFNULL(SUM(d.重量),0) as val FROM 云之家_破壁粉记录 m JOIN 云之家_破壁粉明细 d ON m.流水号=d.流水号 WHERE m.生产日期='{d}' AND d.类型='产出'")
    rows.append({"line":"破壁粉","val":float(r[0]["val"]) if r else 0,"unit":"kg"})
    r = q(f"SELECT IFNULL(SUM(d.重量),0) as val FROM 云之家_成品破壁粉记录 m JOIN 云之家_成品破壁粉明细 d ON m.流水号=d.流水号 WHERE m.生产日期='{d}' AND d.类型='产出'")
    rows.append({"line":"成品破壁粉","val":float(r[0]["val"]) if r else 0,"unit":"kg"})
    r = q(f"SELECT IFNULL(SUM(d.数量),0) as val FROM 云之家_爱尔康生产明细 d WHERE d.生产日期='{d}'")
    rows.append({"line":"爱尔康","val":float(r[0]["val"]) if r else 0,"unit":"瓶"})
    r = q(f"SELECT IFNULL(SUM(d.鲜品重量KG),0) as val FROM 云之家_喷雾干燥生产记录 m JOIN 云之家_喷雾干燥生产明细 d ON m.流水号=d.流水号 WHERE d.生产日期='{d}'")
    rows.append({"line":"喷雾干燥","val":float(r[0]["val"]) if r else 0,"unit":"kg"})
    r = q(f"SELECT IFNULL(SUM(d.干重),0) as val FROM 云之家_鲜品采收明细 d WHERE DATE(d.日期)='{d}'")
    rows.append({"line":"鲜品采收","val":float(r[0]["val"]) if r else 0,"unit":"kg"})
    return rows

def daily_sales(d):
    r = q(f"SELECT COUNT(DISTINCT m.单据编号) as orders, IFNULL(ROUND(SUM(d.含税金额),2),0) as amount FROM 金蝶_销售订单主表 m JOIN 金蝶_销售订单明细 d ON m.单据编号=d.单据编号 WHERE m.业务日期='{d}' AND m.单据状态='C' AND m.客户名称 NOT IN ('云南爱尔发生物技术股份有限公司','云南爱尔康生物技术有限公司','爱尔发生物科技（嘉兴）有限公司')")
    return {"orders":int(r[0]["orders"]),"amount":float(r[0]["amount"])} if r else {"orders":0,"amount":0}

def daily_purchase(d):
    r = q(f"SELECT COUNT(DISTINCT m.单据编号) as orders, IFNULL(ROUND(SUM(d.含税金额),2),0) as amount FROM 金蝶_采购入库单主表 m JOIN 金蝶_采购入库明细 d ON m.单据编号=d.单据编号 WHERE m.业务日期='{d}' AND m.单据状态='C' AND m.供应商名称 NOT IN ('云南爱尔发生物技术股份有限公司','云南爱尔康生物技术有限公司','爱尔发生物科技（嘉兴）有限公司')")
    if r:
        top = q(f"SELECT d.物料名称, ROUND(SUM(d.含税金额),2) as amount FROM 金蝶_采购入库单主表 m JOIN 金蝶_采购入库明细 d ON m.单据编号=d.单据编号 WHERE m.业务日期='{d}' AND m.单据状态='C' AND m.供应商名称 NOT IN ('云南爱尔发生物技术股份有限公司','云南爱尔康生物技术有限公司','爱尔发生物科技（嘉兴）有限公司') GROUP BY d.物料名称 ORDER BY amount DESC LIMIT 1")
        return {"orders":int(r[0]["orders"]),"amount":float(r[0]["amount"]),"top":top[0]["物料名称"] if top else "—"}
    return {"orders":0,"amount":0,"top":"—"}

def daily_attendance(d):
    r = q(f"SELECT COUNT(DISTINCT 用户名) as total, SUM(CASE WHEN 打卡状态='迟到' THEN 1 ELSE 0 END) as late FROM 考勤记录 WHERE 打卡日期='{d}'")
    return {"total":int(r[0]["total"]),"late":int(r[0]["late"])} if r else {"total":0,"late":0}

def production_trend_30d(end_date):
    start = (datetime.strptime(end_date,"%Y-%m-%d")-timedelta(days=29)).strftime("%Y-%m-%d")
    flash = q(f"SELECT m.生产日期 as dt, IFNULL(SUM(d.产出_重量),0) as val FROM 云之家_闪蒸干燥粉记录 m JOIN 云之家_闪蒸干燥粉明细 d ON m.流水号=d.流水号 WHERE m.生产日期>='{start}' AND m.生产日期<='{end_date}' AND d.类型='产出' GROUP BY m.生产日期 ORDER BY dt")
    aikang = q(f"SELECT d.生产日期 as dt, IFNULL(SUM(d.数量),0) as val FROM 云之家_爱尔康生产明细 d WHERE d.生产日期>='{start}' AND d.生产日期<='{end_date}' GROUP BY d.生产日期 ORDER BY dt")
    spray = q(f"SELECT d.生产日期 as dt, IFNULL(SUM(d.鲜品重量KG),0) as val FROM 云之家_喷雾干燥生产记录 m JOIN 云之家_喷雾干燥生产明细 d ON m.流水号=d.流水号 WHERE d.生产日期>='{start}' AND d.生产日期<='{end_date}' GROUP BY d.生产日期 ORDER BY dt")
    fm = {r["dt"]:float(r["val"]) for r in flash}
    am = {r["dt"]:float(r["val"]) for r in aikang}
    sm = {r["dt"]:float(r["val"]) for r in spray}
    dates, vf, va, vs = [], [], [], []
    today = datetime.strptime(end_date,"%Y-%m-%d")
    for i in range(29,-1,-1):
        d = (today-timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append(d[5:]); vf.append(fm.get(d,0)); va.append(am.get(d,0)); vs.append(sm.get(d,0))
    return {"dates":dates,"flash":vf,"aikang":va,"spray":vs}

def sales_trend_30d(end_date):
    start = (datetime.strptime(end_date,"%Y-%m-%d")-timedelta(days=29)).strftime("%Y-%m-%d")
    r = q(f"SELECT m.业务日期 as dt, COUNT(DISTINCT m.单据编号) as orders, IFNULL(ROUND(SUM(d.含税金额),2),0) as amount FROM 金蝶_销售订单主表 m JOIN 金蝶_销售订单明细 d ON m.单据编号=d.单据编号 WHERE m.业务日期>='{start}' AND m.业务日期<='{end_date}' AND m.单据状态='C' GROUP BY m.业务日期 ORDER BY dt")
    rm = {row["dt"]:row for row in r}
    dates, vo, va = [], [], []
    today = datetime.strptime(end_date,"%Y-%m-%d")
    for i in range(29,-1,-1):
        d = (today-timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append(d[5:])
        row = rm.get(d,{})
        vo.append(int(row.get("orders",0)))
        va.append(float(row.get("amount",0)))
    return {"dates":dates,"orders":vo,"amount":va}

def latest_data_date():
    r = q("SELECT MAX(业务日期) as md FROM 金蝶_销售订单主表 WHERE 单据状态='C'")
    if r and r[0]["md"]: return r[0]["md"]
    return date.today().isoformat()

def fmt(v, unit=""):
    if isinstance(v, float):
        if v >= 10000: return f"{v/10000:.1f}万{unit}"
        elif v >= 1: return f"{v:.1f}{unit}"
        else: return f"{v}{unit}"
    return str(v)

def gen_html(data):
    """生成带嵌入数据的驾驶舱 HTML"""
    d = json.dumps(data, ensure_ascii=False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 用 %DATA% 占位符，避免 f-string 与 Vue 的 {} 冲突
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>总经理驾驶舱</title>
<script src="https://cdn.bootcdn.net/ajax/libs/vue/3.4.27/vue.global.prod.min.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/echarts/5.5.0/echarts.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--text1:#f1f5f9;--text2:#94a3b8;--accent:#3b82f6;--green:#22c55e;--orange:#f59e0b;--red:#ef4444;--purple:#8b5cf6;--sidebar:#1a2332}
body{background:var(--bg);color:var(--text1);min-height:100vh;display:flex}
.sidebar{width:200px;min-height:100vh;background:var(--sidebar);padding:20px 0;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-title{padding:0 20px 20px;font-size:18px;font-weight:700;color:var(--text1)}
.sidebar-title small{display:block;font-size:11px;color:var(--text2);font-weight:400;margin-top:2px}
.nav-item{padding:10px 20px;cursor:pointer;color:var(--text2);font-size:14px;display:flex;align-items:center;gap:8px;transition:.15s;border-left:3px solid transparent}
.nav-item:hover{background:rgba(59,130,246,.08);color:var(--text1)}
.nav-item.active{background:rgba(59,130,246,.12);color:var(--accent);border-left-color:var(--accent);font-weight:600}
.sidebar-footer{margin-top:auto;padding:16px 20px;font-size:11px;color:var(--text2)}
.main{flex:1;padding:20px 24px;overflow-y:auto}
.top-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px}
.date-nav{display:flex;align-items:center;gap:10px}
.date-nav button{background:var(--card);border:1px solid var(--border);color:var(--text1);padding:6px 14px;border-radius:8px;cursor:pointer;font-size:14px;transition:.15s}
.date-nav button:hover{background:var(--accent);border-color:var(--accent)}
.date-nav .cur-date{font-size:18px;font-weight:600;min-width:140px;text-align:center}
.refresh-btn{background:var(--accent);border:none;color:#fff;padding:6px 16px;border-radius:8px;cursor:pointer;font-size:13px}
.refresh-btn:hover{opacity:.85}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}
.kpi-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px}
.kpi-card .label{font-size:12px;color:var(--text2);margin-bottom:4px}
.kpi-card .value{font-size:24px;font-weight:700;color:var(--text1)}
.kpi-card .sub{font-size:12px;color:var(--text2);margin-top:4px}
.sec-title{font-size:15px;font-weight:600;margin:16px 0 10px;color:var(--text1)}
.prod-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin-bottom:16px}
.prod-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;text-align:center}
.prod-card .pname{font-size:12px;color:var(--text2);margin-bottom:6px}
.prod-card .pval{font-size:18px;font-weight:700}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px}
.chart-card .ctitle{font-size:13px;font-weight:600;color:var(--text1);margin-bottom:8px}
.chart-container{width:100%;height:280px}
@media(max-width:900px){.kpi-row{grid-template-columns:repeat(2,1fr)}.chart-row{grid-template-columns:1fr}.sidebar{width:60px}.sidebar-title span,.nav-item span,.sidebar-footer{display:none}.sidebar-title small{display:none}.nav-item{padding:12px;justify-content:center;font-size:20px}}
@media(max-width:600px){.kpi-row{grid-template-columns:1fr}.main{padding:12px}.prod-grid{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div id="app">
  <div class="sidebar">
    <div class="sidebar-title">
      <span>🚗 驾驶舱</span>
      <small>总经理</small>
    </div>
    <div class="nav-item" :class="{active:page==='overview'}" @click="page='overview'">📊 <span>总览</span></div>
    <div class="nav-item" :class="{active:page==='production'}" @click="page='production'">🏭 <span>生产</span></div>
    <div class="sidebar-footer"><span>数据截至 %TS%</span></div>
  </div>

  <div class="main" v-if="page==='overview'">
    <div class="top-bar">
      <div class="date-nav">
        <button @click="goDate(-1)">‹</button>
        <span class="cur-date">{{curDate}}</span>
        <button @click="goDate(1)">›</button>
        <button @click="today" style="font-size:12px">今日</button>
      </div>
      <button class="refresh-btn" @click="loadData">⟳ 刷新</button>
    </div>

    <div class="kpi-row">
      <div class="kpi-card">
        <div class="label">📦 当日销售</div>
        <div class="value">{{kpi.sales}}</div>
        <div class="sub">{{kpi.salesOrders}} 笔订单</div>
      </div>
      <div class="kpi-card">
        <div class="label">🏭 当日产量</div>
        <div class="value">{{kpi.output}}</div>
        <div class="sub">7条产线合计</div>
      </div>
      <div class="kpi-card">
        <div class="label">💰 采购入库</div>
        <div class="value">{{kpi.purchase}}</div>
        <div class="sub">{{kpi.purchaseOrders}} 笔 · {{kpi.purchaseTop}}</div>
      </div>
      <div class="kpi-card">
        <div class="label">👥 出勤/迟到</div>
        <div class="value">{{kpi.att}}<span v-if="kpi.late>0" style="font-size:14px;color:var(--orange)"> / {{kpi.late}}迟到</span></div>
        <div class="sub">当日打卡人数</div>
      </div>
    </div>

    <div class="sec-title">🏭 当日产线产出一览</div>
    <div class="prod-grid">
      <div class="prod-card" v-for="p in prodLines" :key="p.line">
        <div class="pname">{{p.line}}</div>
        <div class="pval" :style="{color:p.val>0?'var(--green)':'var(--text2)'}">{{p.val}}{{p.unit}}</div>
      </div>
    </div>

    <div class="chart-row">
      <div class="chart-card">
        <div class="ctitle">📈 近30天产量趋势（3大产线）</div>
        <div id="chart1" class="chart-container"></div>
      </div>
      <div class="chart-card">
        <div class="ctitle">📈 近30天销售趋势</div>
        <div id="chart2" class="chart-container"></div>
      </div>
    </div>
  </div>

  <div class="main" v-else-if="page==='production'">
    <div class="sec-title" style="margin-top:0">🏭 产线详情</div>
    <div class="prod-grid">
      <div class="prod-card" v-for="p in prodLines" :key="p.line">
        <div class="pname">{{p.line}}</div>
        <div class="pval" :style="{color:p.val>0?'var(--green)':'var(--text2)'}">{{p.val}}{{p.unit}}</div>
      </div>
    </div>
    <div class="chart-card">
      <div class="ctitle">近30天产量趋势（按产线）</div>
      <div id="chart3" class="chart-container" style="height:320px"></div>
    </div>
  </div>
</div>

<script>
const {createApp,ref,reactive,onMounted,nextTick} = Vue;
const DATA = %DATA%;

function fmtNum(v) {
  if (!v && v!==0) return '0';
  if (Math.abs(v)>=10000) return (v/10000).toFixed(1)+'万';
  if (v%1===0) return v.toString();
  return v.toFixed(1);
}
function fmtMoney(v) {
  if (!v && v!==0) return '¥0';
  if (Math.abs(v)>=10000) return '¥'+(v/10000).toFixed(1)+'万';
  return '¥'+v.toFixed(0);
}

const app = createApp({
  setup() {
    const page = ref('overview');
    const curDate = ref(DATA.date);
    const prodLines = ref(DATA.production);
    const kpi = ref({
      sales: fmtMoney(DATA.sales.amount),
      salesOrders: DATA.sales.orders,
      output: fmtNum(DATA.production.reduce((a,b)=>a+b.val,0))+'kg',
      purchase: fmtMoney(DATA.purchase.amount),
      purchaseOrders: DATA.purchase.orders,
      purchaseTop: DATA.purchase.top,
      att: DATA.attendance.total,
      late: DATA.attendance.late,
    });
    const trend = ref(DATA.trend);
    const saleTrend = ref(DATA.saleTrend);
    const charts = {};

    function initChart(id, opts) {
      const el = document.getElementById(id);
      if (!el) return null;
      let c = echarts.getInstanceByDom(el);
      if (c) c.dispose();
      c = echarts.init(el);
      if (opts) c.setOption(opts);
      charts[id] = c;
    }

    function renderCharts() {
      nextTick(() => setTimeout(() => {
        const t = trend.value;
        initChart('chart1', {
          tooltip: {trigger:'axis'},
          legend: {data:['闪蒸干燥粉','爱尔康','喷雾干燥'],textStyle:{color:'#94a3b8'},top:0},
          grid: {left:'3%',right:'4%',bottom:'3%',top:40,containLabel:true},
          xAxis: {type:'category',data:t.dates,axisLabel:{color:'#94a3b8',fontSize:10,rotate:45}},
          yAxis: {type:'value',name:'kg',nameTextStyle:{color:'#94a3b8'},axisLabel:{color:'#94a3b8'}},
          series: [
            {name:'闪蒸干燥粉',type:'bar',data:t.flash,itemStyle:{color:'#3b82f6'},barWidth:6},
            {name:'爱尔康',type:'bar',data:t.aikang,itemStyle:{color:'#22c55e'},barWidth:6},
            {name:'喷雾干燥',type:'bar',data:t.spray,itemStyle:{color:'#f59e0b'},barWidth:6},
          ]
        });

        const s = saleTrend.value;
        initChart('chart2', {
          tooltip: {trigger:'axis'},
          grid: {left:'3%',right:'4%',bottom:'3%',top:10,containLabel:true},
          xAxis: {type:'category',data:s.dates,axisLabel:{color:'#94a3b8',fontSize:10,rotate:45}},
          yAxis: {type:'value',name:'¥',nameTextStyle:{color:'#94a3b8'},axisLabel:{color:'#94a3b8',formatter:v=>v>=10000?(v/10000).toFixed(1)+'万':v}},
          series: [{type:'line',data:s.amount,itemStyle:{color:'#8b5cf6'},lineStyle:{color:'#8b5cf6',width:2},areaStyle:{color:'rgba(139,92,246,.15)'},smooth:true,showSymbol:false}]
        });

        initChart('chart3', {
          tooltip: {trigger:'axis'},
          legend: {data:['闪蒸干燥粉','爱尔康','喷雾干燥'],textStyle:{color:'#94a3b8'},top:0},
          grid: {left:'3%',right:'4%',bottom:'3%',top:40,containLabel:true},
          xAxis: {type:'category',data:t.dates,axisLabel:{color:'#94a3b8',fontSize:10,rotate:45}},
          yAxis: {type:'value',name:'kg',nameTextStyle:{color:'#94a3b8'},axisLabel:{color:'#94a3b8'}},
          series: [
            {name:'闪蒸干燥粉',type:'line',data:t.flash,itemStyle:{color:'#3b82f6'},lineStyle:{width:2},smooth:true,areaStyle:{color:'rgba(59,130,246,.1)'}},
            {name:'爱尔康',type:'line',data:t.aikang,itemStyle:{color:'#22c55e'},lineStyle:{width:2},smooth:true,areaStyle:{color:'rgba(34,197,94,.1)'}},
            {name:'喷雾干燥',type:'line',data:t.spray,itemStyle:{color:'#f59e0b'},lineStyle:{width:2},smooth:true,areaStyle:{color:'rgba(245,158,11,.1)'}},
          ]
        });
      }, 100));
    }

    function loadData() { window.location.reload(); }
    function goDate(delta) {
      const d = new Date(curDate.value);
      d.setDate(d.getDate() + delta);
      window.location.href = window.location.pathname + '?date=' + d.toISOString().slice(0,10);
    }
    function today() { window.location.href = window.location.pathname; }

    onMounted(() => renderCharts());
    return {page,curDate,prodLines,kpi,trend,saleTrend,goDate,today,loadData};
  }
});
app.mount('#app');
</script>
</body>
</html>"""
    # 替换占位符
    html = html.replace("%DATA%", d).replace("%TS%", now)
    return html

def main():
    ap = argparse.ArgumentParser(description="总经理驾驶舱生成器")
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD（默认最新数据日期）")
    ap.add_argument("--output", default="/tmp/gm_cockpit.html", help="输出HTML路径")
    args = ap.parse_args()
    dt = args.date or latest_data_date()
    print(f"📅 数据日期: {dt}")
    data = {
        "ts": datetime.now().strftime("%m-%d %H:%M"),
        "date": dt,
        "production": today_production(dt),
        "sales": daily_sales(dt),
        "purchase": daily_purchase(dt),
        "attendance": daily_attendance(dt),
        "trend": production_trend_30d(dt),
        "saleTrend": sales_trend_30d(dt),
    }
    html = gen_html(data)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 已生成: {args.output} ({os.path.getsize(args.output)/1024:.0f}KB)")
    print(f"   在浏览器中打开即可查看")

if __name__ == "__main__":
    main()

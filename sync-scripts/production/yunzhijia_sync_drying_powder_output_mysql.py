#!/usr/bin/env python3
"""
云之家闪蒸干燥粉（产）数据同步脚本 — 写入旧版明细表
从纯产出版本按月汇总表单拉数据，展平写入 云之家_闪蒸干燥粉记录 + 云之家_闪蒸干燥粉明细

用法:
    python3 yunzhijia_sync_drying_powder_output_mysql.py          # 全量同步
    python3 yunzhijia_sync_drying_powder_output_mysql.py --all    # 全量同步
"""

import urllib.request, json, ssl, sys, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from yunzhijia_mysql_base import get_mysql_connection, get_cookie, MYSQL_CONFIG

# ====== 配置 ======
API_URL = "https://www.yunzhijia.com/api/lightcloud/datalist/instance/search2Gen"
FORM_CODE_ID = "303167ed8b1c4ece9c126d3a1dfbe572"
VIEW_ID = "6a2a58cb6b1af31d41f37ee1"

# 旧表名
MAIN_TABLE = "云之家_闪蒸干燥粉记录"
DETAIL_TABLE = "云之家_闪蒸干燥粉明细"

# 产出字段映射: (codeId, 列名, 类型)
OUTPUT_FIELDS = [
    ("Te_1",  "批次",     "textWidget"),
    ("Te_4",  "单位",     "textWidget"),
    ("Da_0",  "生产日期", "dateWidget"),
    ("Nu_7",  "重量",     "numberWidget"),
    ("Nu_8",  "干重",     "numberWidget"),
    ("Nu_9",  "虾青素量", "numberWidget"),
    ("Nu_10", "UV%",      "numberWidget"),
    ("Nu_11", "水分",     "numberWidget"),
    ("Nu_12", "重量收率", "numberWidget"),
    ("Nu_14", "灰分",     "numberWidget"),
    ("Nu_13", "虾青素收率","numberWidget"),
    ("Nu_17", "蛋白质",   "numberWidget"),
    ("Nu_15", "铅",       "numberWidget"),
    ("Te_5",  "感官",     "textWidget"),
    ("Nu_16", "砷",       "numberWidget"),
    ("Ra_0",  "品级",     "radioWidget"),
]


def build_result_items():
    """构造API请求字段列表"""
    details = []
    for code_id, title, ftype in OUTPUT_FIELDS:
        details.append({
            "sum": False, "title": title, "type": ftype,
            "codeId": code_id, "details": None, "parentCodeId": "Dd_1"
        })
    return [
        {"sum": False, "title": "标题", "type": "textWidget", "codeId": "_S_TITLE", "details": [], "parentCodeId": None},
        {"sum": False, "title": "产出", "type": "detailedWidget", "codeId": "Dd_1",
         "details": details, "parentCodeId": ""},
        {"sum": False, "title": "制单日期", "type": "dateWidget", "codeId": "_S_DATE", "details": [], "parentCodeId": None},
    ]


def fetch_all():
    """拉取全部API数据"""
    cookie = get_cookie()
    headers = {
        'Content-Type': 'application/json;charset=UTF-8',
        'x-requested-bizid': 'light-cloud',
        'x-yzj-lang': 'zh-CN',
        'Cookie': cookie
    }
    all_records = []
    page = 1
    while True:
        body = {
            'pageSize': 50, 'formCodeId': FORM_CODE_ID, 'viewId': VIEW_ID,
            'pageNumber': page, 'searchItems': [],
            'resultItems': build_result_items(),
            'sorts': [], 'terminalType': 1, 'groupIds': [], 'language': 'zh-CN'
        }
        req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), headers=headers, method='POST')
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        result = json.loads(resp.read())
        records = result.get('data', {}).get('dataList', [])
        if not records:
            break
        all_records.extend(records)
        page += 1
    return all_records


def parse_batches(records):
    """展平API记录为批次列表"""
    batches = []
    for row in records:
        month_title = next((c['value'] for c in row['colList'] if c['codeId'] == '_S_TITLE'), '')
        s_date = next((c['value'] for c in row['colList'] if c['codeId'] == '_S_DATE'), '')
        create_time = row.get('createTime', 0)

        dd1_data = {}
        for col in row['colList']:
            if col['codeId'] == 'Dd_1' and col.get('details'):
                for d in col['details']:
                    # 优先用 value（已解析的字符串格式），否则用 rawValue
                    if d.get('value'):
                        try:
                            dd1_data[d['codeId']] = json.loads(d['value']) if isinstance(d['value'], str) else d['value']
                        except:
                            dd1_data[d['codeId']] = []
                    else:
                        raw = d.get('rawValue', [])
                        if raw and isinstance(raw, list):
                            dd1_data[d['codeId']] = raw

        batch_count = len(dd1_data.get('Te_1', []))
        for i in range(batch_count):
            batch = {
                '月份标题': month_title,
                '制单日期': s_date,
                '创建时间戳': create_time,
            }
            for code_id, field_name, _ in OUTPUT_FIELDS:
                arr = dd1_data.get(code_id, [])
                val = arr[i] if i < len(arr) else None
                if val == '' or val is None:
                    val = None
                # 日期字段：时间戳转 YYYY-MM-DD
                if val is not None and code_id == 'Da_0':
                    if isinstance(val, (int, float)):
                        from datetime import timezone, timedelta
                        val = datetime.fromtimestamp(val / 1000, tz=timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
                batch[field_name] = val
            batches.append(batch)
    return batches


def parse_number(val):
    if val is None:
        return None
    try:
        return float(val)
    except:
        return None


def sync():
    print(f"{'='*60}")
    print(f"云之家闪蒸干燥粉（产）→ 旧表同步 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # 1. 获取数据
    print("\n[1/3] 从API获取数据...")
    records = fetch_all()
    print(f"    获取 {len(records)} 个月记录")

    batches = parse_batches(records)
    print(f"    展平为 {len(batches)} 批")

    if not batches:
        print("    ❌ 无数据")
        return

    # 2. 写入旧表
    print(f"\n[2/3] 写入 {MAIN_TABLE} + {DETAIL_TABLE} ...")
    conn = get_mysql_connection()
    cursor = conn.cursor()

    # 主表SQL
    main_sql = """INSERT INTO `{}`
        (`流水号`, `标题`, `批号`, `生产日期`, `制单人`, `制单部门`, `制单日期`, `状态`)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
        `标题`=VALUES(`标题`), `批号`=VALUES(`批号`), `生产日期`=VALUES(`生产日期`),
        `制单人`=VALUES(`制单人`), `制单日期`=VALUES(`制单日期`)""".format(MAIN_TABLE)

    # 明细表SQL（先删再插）
    detail_delete_sql = f"DELETE FROM `{DETAIL_TABLE}` WHERE `流水号` = %s"
    detail_insert_sql = """INSERT INTO `{}`
        (`流水号`, `类型`, `投入_名称`, `投入_批次`, `投入_单位`, `投入_毛重`, `投入_含量`,
         `投入_水分`, `投入_铅`, `投入_砷`, `投入_干重`, `投入_虾青素量`,
         `产出_重量`, `产出_干重`, `产出_虾青素量`, `产出_UV%`, `产出_水分`,
         `产出_重量收率`, `产出_虾青素收率`, `产出_感官`, `产出_品级`,
         `产出_灰分`, `产出_蛋白质`, `产出_铅`, `产出_砷`)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""".format(DETAIL_TABLE)

    main_count = 0
    detail_count = 0

    for b in batches:
        batch_no = b.get('批次')
        if not batch_no:
            continue

        serial_no = f"DRYO_{batch_no}"
        prod_date = b.get('生产日期')
        create_ts = b.get('创建时间戳', 0)

        # 制单日期 = 创建时间戳
        s_date = None
        if create_ts:
            try:
                s_date = datetime.fromtimestamp(create_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
            except:
                s_date = b.get('制单日期')

        # 写入主表
        main_vals = (
            serial_no,
            f"闪蒸干燥粉(产): {batch_no}",
            batch_no,
            prod_date,
            "闪蒸干燥粉(产)同步",
            None,
            s_date,
            None,
        )
        try:
            cursor.execute(main_sql, main_vals)
            main_count += 1
        except Exception as e:
            print(f"    ⚠️ 主表写入失败 [{batch_no}]: {e}")
            continue

        # 先删旧明细（同流水号）
        try:
            cursor.execute(detail_delete_sql, (serial_no,))
        except:
            pass

        # 写入明细（产出类型）
        detail_vals = (
            serial_no,
            "产出",
            None, None, None,             # 投入_名称/批次/单位
            None, None, None, None, None,  # 投入_毛重/含量/水分/铅/砷
            None, None,                    # 投入_干重/虾青素量
            parse_number(b.get('重量')),         # 产出_重量
            parse_number(b.get('干重')),         # 产出_干重
            parse_number(b.get('虾青素量')),     # 产出_虾青素量
            parse_number(b.get('UV%')),          # 产出_UV%
            parse_number(b.get('水分')),         # 产出_水分
            parse_number(b.get('重量收率')),     # 产出_重量收率
            parse_number(b.get('虾青素收率')),   # 产出_虾青素收率
            (b.get('感官') or None),             # 产出_感官
            (b.get('品级') or None),             # 产出_品级
            parse_number(b.get('灰分')),         # 产出_灰分
            parse_number(b.get('蛋白质')),       # 产出_蛋白质
            parse_number(b.get('铅')),           # 产出_铅
            parse_number(b.get('砷')),           # 产出_砷
        )
        try:
            cursor.execute(detail_insert_sql, detail_vals)
            detail_count += 1
        except Exception as e:
            print(f"    ⚠️ 明细写入失败 [{batch_no}]: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n[3/3] 完成!")
    print(f"    ✅ 主表 {MAIN_TABLE}: {main_count} 条")
    print(f"    ✅ 明细表 {DETAIL_TABLE}: {detail_count} 条")
    print(f"{'='*60}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='闪蒸干燥粉（产）数据同步到旧表')
    parser.add_argument('--all', action='store_true', help='全量同步')
    args = parser.parse_args()
    sync()

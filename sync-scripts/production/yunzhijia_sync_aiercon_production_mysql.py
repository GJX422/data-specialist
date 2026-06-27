#!/usr/bin/env python3
"""
云之家爱尔康生产结果记录数据同步脚本 (MySQL 版)
功能：从云之家 API 拉取爱尔康生产数据，写入 MySQL 数据库
包含主表（爱尔康生产记录）和明细表（爱尔康生产明细）
"""

import urllib.request
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 导入通用模块
import sys
sys.path.insert(0, str(Path(__file__).parent))
from yunzhijia_mysql_base import get_mysql_connection, get_cookie, MYSQL_CONFIG

# ============ 配置 ============
API_URL = "https://www.yunzhijia.com/api/lightcloud/datalist/instance/search2Gen"
TABLE_NAME = "云之家_爱尔康生产记录"
DETAIL_TABLE_NAME = "云之家_爱尔康生产明细"

# 爱尔康生产表单配置
FORM_CODE_ID = "55d3968232f24da08716f1f55b28285c"
VIEW_ID = "69d6fc8adaf4c75cd4b130d8"

# 要查询的字段
RESULT_ITEMS = [
    {"sum": False, "title": "流水号", "type": "serialNumWidget", "codeId": "_S_SERIAL", "details": [], "parentCodeId": None},
    {"sum": False, "title": "标题", "type": "textWidget", "codeId": "_S_TITLE", "details": [], "parentCodeId": None},
    {"sum": False, "title": "制单人", "type": "personSelectWidget", "codeId": "_S_APPLY", "details": [], "parentCodeId": None},
    {"sum": False, "title": "制单部门", "type": "departmentSelectWidget", "codeId": "_S_DEPT", "details": [], "parentCodeId": None},
    {"sum": False, "title": "制单日期", "type": "dateWidget", "codeId": "_S_DATE", "details": [], "parentCodeId": None},
    {"sum": False, "title": "月份", "type": "dateWidget", "codeId": "Da_1", "details": [], "parentCodeId": None},
    # 明细 Dd_0
    {"sum": False, "title": "明细", "type": "detailedWidget", "codeId": "Dd_0",
     "details": [
         {"sum": True, "title": "总数量", "type": "numberWidget", "codeId": "Nu_0", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "产品名称", "type": "textWidget", "codeId": "Te_0", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "类型", "type": "textWidget", "codeId": "Ra_0", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "规格型号", "type": "textWidget", "codeId": "Te_1", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "单位", "type": "textWidget", "codeId": "Te_2", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "数量", "type": "numberWidget", "codeId": "Nu_0", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "HPLC", "type": "textWidget", "codeId": "Te_3", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "UV", "type": "textWidget", "codeId": "Te_4", "details": None, "parentCodeId": "Dd_0"},
         {"sum": False, "title": "生产日期", "type": "dateWidget", "codeId": "Da_0", "details": None, "parentCodeId": "Dd_0"},
     ], "parentCodeId": ""},
]

# MySQL 主表结构
CREATE_MAIN_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS `{TABLE_NAME}` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `流水号` VARCHAR(50) UNIQUE,
    `标题` VARCHAR(500),
    `制单人` VARCHAR(50),
    `制单部门` VARCHAR(100),
    `制单日期` DATETIME,
    `月份` VARCHAR(20),
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_制单日期` (`制单日期`),
    INDEX `idx_月份` (`月份`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# MySQL 明细表结构
CREATE_DETAIL_TABLE_SQL = f"""\
CREATE TABLE IF NOT EXISTS `{DETAIL_TABLE_NAME}` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `流水号` VARCHAR(50),
    `类型` VARCHAR(20),
    `总数量` DECIMAL(10,4),
    `产品名称` VARCHAR(100),
    `规格型号` VARCHAR(100),
    `单位` VARCHAR(20),
    `数量` DECIMAL(10,4),
    `HPLC` VARCHAR(50),
    `UV` VARCHAR(50),
    `生产日期` DATE,
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_流水号_类型_产品名称_规格型号` (`流水号`, `类型`, `产品名称`, `规格型号`),
    INDEX `idx_流水号` (`流水号`),
    INDEX `idx_产品名称` (`产品名称`),
    INDEX `idx_生产日期` (`生产日期`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 主表列名
MAIN_COLUMNS = [
    '流水号', '标题', '制单人', '制单部门', '制单日期', '月份'
]

# 明细表列名
DETAIL_COLUMNS = [
    '流水号', '类型', '总数量', '产品名称', '规格型号', '单位', '数量', 'HPLC', 'UV', '生产日期'
]


def init_database():
    """初始化数据库表"""
    conn = get_mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_MAIN_TABLE_SQL)
        cursor.execute(CREATE_DETAIL_TABLE_SQL)
        conn.commit()
        print(f"数据库表初始化完成: {TABLE_NAME}, {DETAIL_TABLE_NAME}")
    finally:
        cursor.close()
        conn.close()


def fetch_aiercon_production(cookie, page_size=100, page_number=1, search_items=None):
    """从云之家 API 获取爱尔康生产数据"""
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "x-requested-bizid": "light-cloud",
        "x-yzj-lang": "zh-CN",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": cookie
    }

    data = {
        "pageSize": page_size,
        "formCodeId": FORM_CODE_ID,
        "pageNumber": page_number,
        "searchItems": search_items or [],
        "resultItems": RESULT_ITEMS,
        "sorts": [],
        "terminalType": 1,
        "groupIds": [],
        "viewId": VIEW_ID,
        "language": "zh-CN"
    }

    req = urllib.request.Request(API_URL, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result


def parse_timestamp(ts):
    """解析时间戳或日期字符串"""
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
        return None
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return None


def parse_date(date_val):
    """解析日期值"""
    if not date_val:
        return None
    if isinstance(date_val, str):
        try:
            dt = datetime.strptime(date_val, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
        return None
    try:
        dt = datetime.fromtimestamp(date_val / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d")
    except:
        return None


def clean_value(val):
    """清理值"""
    if val is None or val == '*' or val == ',':
        return None
    if isinstance(val, str):
        val = val.strip().strip('"').strip("'")
        if val == '' or val == 'null':
            return None
    return val


def parse_number(val):
    """解析数字值"""
    if val is None or val == '' or val == '*':
        return None
    try:
        if isinstance(val, str):
            val = val.replace(',', '').strip()
        return float(val)
    except:
        return None


def parse_pipe_values(val):
    """解析管道分隔的多个值（如 "val1 | val2"）"""
    if not val:
        return []
    if isinstance(val, str):
        # 处理 ["val1","val2"] 格式
        if val.startswith('[') and val.endswith(']'):
            try:
                return json.loads(val)
            except:
                pass
        # 处理 "val1 | val2" 格式
        if '|' in val:
            return [v.strip() for v in val.split('|')]
        return [val]
    return [str(val)]


def normalize_to_list(val):
    """将值标准化为列表格式"""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    # 单个值，包装成列表
    return [val]


def save_to_database(records):
    """保存到 MySQL（主表 + 明细表）"""
    if not records:
        print("没有数据需要保存")
        return 0, 0

    conn = get_mysql_connection()
    cursor = conn.cursor()

    # 主表 SQL
    main_col_names = ', '.join([f'`{col}`' for col in MAIN_COLUMNS])
    main_placeholders = ', '.join(['%s'] * len(MAIN_COLUMNS))
    main_update_cols = [col for col in MAIN_COLUMNS if col != '流水号']
    main_update_clause = ', '.join([f'`{col}` = VALUES(`{col}`)' for col in main_update_cols])

    main_sql = f"""
        INSERT INTO `{TABLE_NAME}` ({main_col_names})
        VALUES ({main_placeholders})
        ON DUPLICATE KEY UPDATE {main_update_clause}
    """

    # 明细表 SQL
    detail_col_names = ', '.join([f'`{col}`' for col in DETAIL_COLUMNS])
    detail_placeholders = ', '.join(['%s'] * len(DETAIL_COLUMNS))
    detail_update_cols = [col for col in DETAIL_COLUMNS if col not in ('流水号', '类型')]
    detail_update_clause = ', '.join([f'`{col}` = VALUES(`{col}`)' for col in detail_update_cols])

    detail_sql = f"""
        INSERT INTO `{DETAIL_TABLE_NAME}` ({detail_col_names})
        VALUES ({detail_placeholders})
        ON DUPLICATE KEY UPDATE {detail_update_clause}
    """

    main_saved = 0
    detail_saved = 0

    for record in records:
        cols = {}
        for c in record.get("colList", []):
            code_id = c.get("codeId")
            if c.get("details"):
                cols[code_id] = c
            else:
                cols[code_id] = c.get("value", c.get("rawValue", ""))

        serial_no = clean_value(cols.get("_S_SERIAL"))
        if not serial_no:
            continue

        # 解析明细 Dd_0
        dd0 = cols.get("Dd_0", {})
        dd0_details = dd0.get("details", []) if isinstance(dd0, dict) else []

        # 保存主表
        main_values = (
            serial_no,
            clean_value(cols.get("_S_TITLE")),
            clean_value(cols.get("_S_APPLY")),
            clean_value(cols.get("_S_DEPT")),
            parse_timestamp(cols.get("_S_DATE")),
            clean_value(cols.get("Da_1")),           # 月份
        )

        try:
            cursor.execute(main_sql, main_values)
            main_saved += 1
        except Exception as e:
            print(f"保存主表记录失败 [{serial_no}]: {e}")
            continue

        # ---- 处理明细 (Dd_0) ----
        # Nu_0 出现两次: sum=true(总数量) 和 sum=false(数量)
        # sum=true 的存储在 dd0_summary, sum=false 的存储在 dd0_data
        dd0_data = {}
        dd0_summary = {}  # 存储汇总字段 (sum=true)
        dd0_row_count = 0
        for item in dd0_details:
            code_id = item.get("codeId", "")
            # 检查是否是汇总字段
            if item.get("sum"):
                # 汇总字段，存储单个值到 summary
                raw_val = item.get("rawValue")
                if raw_val is not None:
                    dd0_summary[code_id] = parse_number(str(raw_val))
                continue
            # 明细字段，处理列表值
            raw_val = item.get("rawValue")
            values_list = normalize_to_list(raw_val)
            if not values_list:
                val = item.get("value", "")
                if val:
                    values_list = parse_pipe_values(val)
            # 对于 Nu_0(sum=false)，可能存在多个值（数组），也可能只有一个值
            # 如果已经是单个值但应该是数组中的每个元素，需要特殊处理
            if code_id in dd0_data:
                # 已存在（sum=true已处理过），追加到列表
                dd0_data[code_id] = values_list
            else:
                dd0_data[code_id] = values_list
            if len(values_list) > dd0_row_count:
                dd0_row_count = len(values_list)

        # 预先处理：Ra_0（类型）是单选控件，rawValue 是选项编码，value 才是中文文本
        # 从原始 details 中提取 Ra_0 的 value（中文显示文本）
        ra0_value_map = {}
        for item in dd0_details:
            if item.get("codeId") == "Ra_0" and not item.get("sum"):
                raw_vals = normalize_to_list(item.get("rawValue"))
                vals = item.get("value", "")
                if isinstance(vals, str):
                    try:
                        import json as _json
                        display_vals = _json.loads(vals) if vals.startswith("[") else [vals]
                    except:
                        display_vals = raw_vals  # fallback
                else:
                    display_vals = normalize_to_list(vals)
                for idx, dv in enumerate(display_vals):
                    ra0_value_map[idx] = clean_value(dv)
                break

        for i in range(dd0_row_count):
            def get_dd0_val(code_id, is_date=False):
                # Ra_0 特殊处理：用预存的 value（中文）覆盖 rawValue（编码）
                if code_id == "Ra_0" and i in ra0_value_map:
                    return ra0_value_map[i]
                vals = dd0_data.get(code_id, [])
                if i < len(vals):
                    v = vals[i]
                    if is_date:
                        return parse_date(v)
                    return clean_value(v)
                return None

            # 数量：从 sum=false 的明细数据获取
            def get_dd0_number(code_id):
                # 先尝试从明细数据获取
                vals = dd0_data.get(code_id, [])
                if i < len(vals):
                    v = vals[i]
                    if v is not None and v != '':
                        return parse_number(v)
                # 如果明细数据没有，使用汇总值作为 fallback
                return dd0_summary.get(code_id)

            detail_values = (
                serial_no,
                get_dd0_val("Ra_0"),                  # 类型
                dd0_summary.get("Nu_0"),              # 总数量 (来自 sum=true 的汇总值)
                get_dd0_val("Te_0"),                  # 产品名称
                get_dd0_val("Te_1"),                  # 规格型号
                get_dd0_val("Te_2"),                  # 单位
                get_dd0_number("Nu_0"),               # 数量 (来自 sum=false 的明细值)
                get_dd0_val("Te_3"),                  # HPLC
                get_dd0_val("Te_4"),                  # UV
                get_dd0_val("Da_0", is_date=True),    # 生产日期
            )

            try:
                cursor.execute(detail_sql, detail_values)
                detail_saved += 1
            except Exception as e:
                print(f"保存明细失败 [{serial_no}][{i}]: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    return main_saved, detail_saved


def sync_all():
    """同步所有数据"""
    print("=" * 60)
    print("开始同步云之家爱尔康生产数据到 MySQL")
    print("=" * 60)

    init_database()
    cookie = get_cookie()
    print("Cookie 读取成功")

    page_number = 1
    total_main_saved = 0
    total_detail_saved = 0

    while True:
        print(f"\n正在获取第 {page_number} 页...")
        result = fetch_aiercon_production(cookie, page_size=100, page_number=page_number)

        if not result.get("success"):
            print(f"API 调用失败: {result.get('errorMsg', '未知错误')}")
            break

        data = result.get("data", {})
        data_list = data.get("dataList", [])
        total = data.get("totalElements", 0)
        total_pages = data.get("totalPages", 0)

        if not data_list:
            print("没有更多数据")
            break

        main_saved, detail_saved = save_to_database(data_list)
        total_main_saved += main_saved
        total_detail_saved += detail_saved
        print(f"本页保存: 主表 {main_saved} 条, 明细 {detail_saved} 条")
        print(f"进度: {min(page_number * 100, total)}/{total} 条")

        if page_number >= total_pages:
            break

        page_number += 1

    print("\n" + "=" * 60)
    print(f"同步完成!")
    print(f"主表 ({TABLE_NAME}): {total_main_saved} 条")
    print(f"明细表 ({DETAIL_TABLE_NAME}): {total_detail_saved} 条")
    print(f"数据库: {MYSQL_CONFIG['database']}")
    print("=" * 60)

    return total_main_saved, total_detail_saved


def sync_by_date(start_date, end_date=None):
    """按日期范围同步"""
    if end_date is None:
        end_date = start_date

    print("=" * 60)
    print(f"同步日期范围: {start_date} ~ {end_date}")
    print("=" * 60)

    init_database()
    cookie = get_cookie()

    cst = timezone(timedelta(hours=8))
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=cst)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=cst)

    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    search_items = [{"codeId": "_S_DATE", "condition": "RANGE", "value": [start_ts, end_ts]}]

    result = fetch_aiercon_production(cookie, search_items=search_items)

    if not result.get("success"):
        print(f"API 调用失败: {result.get('errorMsg', '未知错误')}")
        return 0, 0

    data = result.get("data", {})
    data_list = data.get("dataList", [])
    total = data.get("totalElements", 0)

    print(f"查询到 {total} 条记录")

    main_saved, detail_saved = save_to_database(data_list)
    print(f"保存: 主表 {main_saved} 条, 明细 {detail_saved} 条")

    return main_saved, detail_saved


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="云之家爱尔康生产结果记录数据同步 (MySQL)")
    parser.add_argument("--all", action="store_true", help="同步所有数据")
    parser.add_argument("--date", type=str, help="同步指定日期 (YYYY-MM-DD)")
    parser.add_argument("--start", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.all:
        sync_all()
    elif args.date:
        sync_by_date(args.date)
    elif args.start and args.end:
        sync_by_date(args.start, args.end)
    else:
        sync_all()

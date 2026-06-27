#!/usr/bin/env python3
"""
云之家工作日报数据同步脚本 (MySQL 版)
功能：从云之家 API 拉取工作日报数据，写入 MySQL 数据库
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
TABLE_NAME = "云之家_工作日报"

# 工作日报表单配置
FORM_CODE_ID = "c7c1f226cabd49658b601363cc4d210a"
VIEW_ID = "68ca497eec87bd29f7ba4326"

# 要查询的字段
RESULT_ITEMS = [
    {"sum": False, "title": "标题", "type": "textWidget", "codeId": "_S_TITLE"},
    {"sum": False, "title": "流水号", "type": "serialNumWidget", "codeId": "_S_SERIAL"},
    {"sum": False, "title": "提交人", "type": "personSelectWidget", "codeId": "_S_APPLY"},
    {"sum": False, "title": "所属部门", "type": "departmentSelectWidget", "codeId": "_S_DEPT"},
    {"sum": False, "title": "填写日期", "type": "dateWidget", "codeId": "_S_DATE"},
    {"sum": False, "title": "今日工作总结", "type": "textAreaWidget", "codeId": "Ta_0"},
    {"sum": False, "title": "工作进展情况", "type": "textAreaWidget", "codeId": "Ta_1"},
    {"sum": False, "title": "需解决问题", "type": "textAreaWidget", "codeId": "Ta_2"},
    {"sum": False, "title": "流程状态", "type": "radioWidget", "codeId": "_S_STATUS"},
]

# MySQL 表结构（中文字段名）
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `工作日报` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `流水号` VARCHAR(50) UNIQUE,
    `标题` VARCHAR(500),
    `提交人` VARCHAR(50),
    `所属部门` VARCHAR(100),
    `填写日期` DATE,
    `今日工作总结` TEXT,
    `工作进展情况` TEXT,
    `需解决问题` TEXT,
    `流程状态` VARCHAR(20),
    `云之家ID` VARCHAR(100),
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_填写日期` (`填写日期`),
    INDEX `idx_所属部门` (`所属部门`),
    INDEX `idx_提交人` (`提交人`),
    INDEX `idx_流程状态` (`流程状态`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 列名列表
COLUMNS = [
    '流水号', '标题', '提交人', '所属部门', '填写日期',
    '今日工作总结', '工作进展情况', '需解决问题', '流程状态', '云之家ID'
]


def init_database():
    """初始化数据库"""
    conn = get_mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print(f"数据库表初始化完成: {TABLE_NAME}")
    finally:
        cursor.close()
        conn.close()


def fetch_daily_report(cookie, page_size=100, page_number=1, search_items=None):
    """从云之家 API 获取工作日报数据"""
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
        "groupIds": [],
        "language": "zh-CN",
        "resultItems": RESULT_ITEMS,
        "sorts": [{"codeId": "_S_DATE", "sortType": "desc"}],
        "terminalType": 1,
        "viewId": VIEW_ID
    }
    
    req = urllib.request.Request(API_URL, data=json.dumps(data).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    
    return result


def parse_timestamp(ts):
    """解析时间戳或日期字符串"""
    if not ts:
        return None
    # 如果是字符串格式的日期时间
    if isinstance(ts, str):
        # 尝试解析 "2025-09-15 09:26:35" 格式
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
        # 尝试解析 "2025-09-15" 格式
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
        return None
    # 如果是毫秒时间戳
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d")
    except:
        return None


def clean_value(val):
    if val is None or val == '*':
        return None
    return val


def save_to_database(records):
    """保存到 MySQL"""
    if not records:
        print("没有数据需要保存")
        return 0
    
    conn = get_mysql_connection()
    cursor = conn.cursor()
    
    col_names = ', '.join([f'`{col}`' for col in COLUMNS])
    placeholders = ', '.join(['%s'] * len(COLUMNS))
    update_cols = [col for col in COLUMNS if col != '流水号']
    update_clause = ', '.join([f'`{col}` = VALUES(`{col}`)' for col in update_cols])
    
    sql = f"""
        INSERT INTO `{TABLE_NAME}` ({col_names})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """
    
    saved_count = 0
    for record in records:
        cols = {c["codeId"]: c["value"] for c in record["colList"]}
        cols_raw = {c["codeId"]: c.get("rawValue") for c in record["colList"]}
        
        serial_no = cols.get("_S_SERIAL")
        if not serial_no:
            continue
        
        # 从 rawValue 提取 openId
        open_id = None
        raw_val = cols_raw.get("_S_APPLY")
        if raw_val and isinstance(raw_val, list) and len(raw_val) > 0:
            open_id = raw_val[0]
        
        values = (
            clean_value(serial_no),
            clean_value(cols.get("_S_TITLE")),
            clean_value(cols.get("_S_APPLY")),
            clean_value(cols.get("_S_DEPT")),
            parse_timestamp(cols.get("_S_DATE")),
            clean_value(cols.get("Ta_0")),
            clean_value(cols.get("Ta_1")),
            clean_value(cols.get("Ta_2")),
            clean_value(cols.get("_S_STATUS")),
            open_id
        )
        
        try:
            cursor.execute(sql, values)
            saved_count += 1
        except Exception as e:
            print(f"保存记录失败 [{serial_no}]: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return saved_count


def sync_all():
    """同步所有数据"""
    print("=" * 50)
    print("开始同步云之家工作日报数据到 MySQL")
    print("=" * 50)
    
    init_database()
    cookie = get_cookie()
    print("Cookie 读取成功")
    
    page_number = 1
    total_saved = 0
    
    while True:
        print(f"\n正在获取第 {page_number} 页...")
        result = fetch_daily_report(cookie, page_size=100, page_number=page_number)
        
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
        
        saved = save_to_database(data_list)
        total_saved += saved
        print(f"本页保存 {saved} 条记录")
        print(f"进度: {min(page_number * 100, total)}/{total} 条")
        
        if page_number >= total_pages:
            break
        
        page_number += 1
    
    print("\n" + "=" * 50)
    print(f"同步完成! 共保存 {total_saved} 条记录")
    print(f"数据库: {MYSQL_CONFIG['database']}.{TABLE_NAME}")
    print("=" * 50)
    
    return total_saved



def sync_by_status(statuses):
    """按状态过滤同步 (RUNNING=审批中, RETURNED=待提交)"""
    print("=" * 50)
    print(f"按状态过滤同步: {statuses}")
    print("=" * 50)
    
    init_database()
    cookie = get_cookie()
    
    saved_total = 0
    for status in statuses:
        single_search = [{"codeId": "_S_STATUS", "condition": "EQUAL", "value": status}]
        page = 1
        while True:
            result = fetch_daily_report(cookie, page_size=100, page_number=page, search_items=single_search)
            if not result.get("success"):
                print(f"API 调用失败 ({status}): " + str(result.get("errorMsg", "未知错误")))
                break
            data = result.get("data", {})
            data_list = data.get("dataList", [])
            total = data.get("totalElements", 0)
            if not data_list:
                break
            saved = save_to_database(data_list)
            saved_total += saved
            print(f"  {status}: 第{page}页 {len(data_list)}条, 已保存{saved}条 (总计{total})")
            if len(data_list) < 100:
                break
            page += 1
    
    print(f"状态过滤同步完成: 共保存 {saved_total} 条")
    return saved_total

def sync_by_date(start_date, end_date=None):
    """按日期范围同步"""
    if end_date is None:
        end_date = start_date
    
    print("=" * 50)
    print(f"同步日期范围: {start_date} ~ {end_date}")
    print("=" * 50)
    
    init_database()
    cookie = get_cookie()
    
    cst = timezone(timedelta(hours=8))
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=cst)
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=cst)
    
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    search_items = [{"codeId": "_S_DATE", "condition": "RANGE", "value": [start_ts, end_ts]}]
    
    result = fetch_daily_report(cookie, search_items=search_items)
    
    if not result.get("success"):
        print(f"API 调用失败: {result.get('errorMsg', '未知错误')}")
        return 0
    
    data = result.get("data", {})
    data_list = data.get("dataList", [])
    total = data.get("totalElements", 0)
    
    print(f"查询到 {total} 条记录")
    
    saved = save_to_database(data_list)
    print(f"保存 {saved} 条记录到数据库")
    
    return saved


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="云之家工作日报数据同步 (MySQL)")
    parser.add_argument("--all", action="store_true", help="同步所有数据")
    parser.add_argument("--date", type=str, help="同步指定日期 (YYYY-MM-DD)")
    parser.add_argument("--start", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--status", type=str, help="按状态过滤 (逗号分隔: RUNNING,RETURNED,FINISH,ABANDON)")
    
    args = parser.parse_args()
    
    if args.all:
        sync_all()
    elif hasattr(args, "status") and args.status:
        statuses = [s.strip() for s in args.status.split(",")]
        sync_by_status(statuses)
    elif args.date:
        sync_by_date(args.date)
    elif args.start and args.end:
        sync_by_date(args.start, args.end)
    else:
        sync_all()

#!/usr/bin/env python3
"""
云之家用款申请数据同步脚本 (MySQL 版)
功能：从云之家 API 拉取用款申请数据，写入 MySQL 数据库
"""

import urllib.request
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 导入通用模块
import sys
sys.path.insert(0, str(Path(__file__).parent))
from yunzhijia_mysql_base import get_mysql_connection, get_cookie, MYSQL_CONFIG

# ============ 配置 ============
API_URL = "https://www.yunzhijia.com/api/lightcloud/datalist/instance/search2Gen"
TABLE_NAME = "云之家_用款申请"

# 用款申请表单配置
FORM_CODE_ID = "56f7068ebbcd46e4b9a6fbc07db0ab5b"
VIEW_ID = "6966f41170725b7eb6c6c52b"

# 要查询的字段
RESULT_ITEMS = [
    {"sum": False, "title": "标题", "type": "textWidget", "codeId": "_S_TITLE"},
    {"sum": False, "title": "流水号", "type": "serialNumWidget", "codeId": "_S_SERIAL"},
    {"sum": False, "title": "申请人", "type": "personSelectWidget", "codeId": "_S_APPLY"},
    {"sum": False, "title": "制单部门", "type": "departmentSelectWidget", "codeId": "_S_DEPT"},
    {"sum": False, "title": "制单日期", "type": "dateWidget", "codeId": "_S_DATE"},
    {"sum": False, "title": "使用部门", "type": "departmentSelectWidget", "codeId": "Ds_0"},
    {"sum": False, "title": "使用单位", "type": "radioWidget", "codeId": "Ra_1"},
    {"sum": False, "title": "使用类型", "type": "radioWidget", "codeId": "Ra_4"},
    {"sum": False, "title": "普通类型", "type": "radioWidget", "codeId": "Ra_5"},
    {"sum": False, "title": "大类目", "type": "radioWidget", "codeId": "Ra_6"},
    {"sum": False, "title": "申请金额", "type": "moneyWidget", "codeId": "Mo_0"},
    {"sum": False, "title": "用途", "type": "textAreaWidget", "codeId": "Ta_2"},
    {"sum": False, "title": "付款方式", "type": "textWidget", "codeId": "Te_4"},
    {"sum": False, "title": "收款人全称", "type": "basicDataWidget", "codeId": "Bd_1"},
    {"sum": False, "title": "银行账户", "type": "textWidget", "codeId": "Te_1"},
    {"sum": False, "title": "开户行", "type": "textWidget", "codeId": "Te_2"},
    {"sum": False, "title": "备注", "type": "textWidget", "codeId": "Te_5"},
    {"sum": False, "title": "用款月份", "type": "dateWidget", "codeId": "Da_0"},
    {"sum": False, "title": "用款年度", "type": "dateWidget", "codeId": "Da_2"},
    {"sum": False, "title": "流程状态", "type": "radioWidget", "codeId": "_S_STATUS"},
    {"sum": False, "title": "当前节点", "type": "textWidget", "codeId": "activityName"},
    {"sum": False, "title": "项目（名称）", "type": "textWidget", "codeId": "Te_8"},
    {"sum": False, "title": "当前审批人", "type": "personSelectWidget", "codeId": "approver"},
    {"sum": False, "title": "审批完成时间", "type": "dateWidget", "codeId": "_S_FINISH_TIME"},
    {"sum": False, "title": "预算剩余额度", "type": "numberWidget", "codeId": "Nu_0"},
    {"sum": False, "title": "预算项目", "type": "basicDataWidget", "codeId": "Bd_0"},
    {"sum": False, "title": "收款人名称(补充)", "type": "textWidget", "codeId": "Te_6"},
    {"sum": False, "title": "银行账号(补充)", "type": "textWidget", "codeId": "Te_9"},
    {"sum": False, "title": "开户行(补充)", "type": "textWidget", "codeId": "Te_10"},
]

# MySQL 表结构（中文字段名）
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS `云之家_用款申请` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `流水号` VARCHAR(50) UNIQUE,
    `标题` VARCHAR(500),
    `申请人` VARCHAR(50),
    `制单部门` VARCHAR(100),
    `制单日期` DATE,
    `使用部门` VARCHAR(100),
    `使用单位` VARCHAR(50),
    `使用类型` VARCHAR(100),
    `普通类型` VARCHAR(50),
    `大类目` VARCHAR(50),
    `申请金额` DECIMAL(15,2),
    `用途` TEXT,
    `付款方式` VARCHAR(50),
    `收款人` VARCHAR(500),
    `银行账户` VARCHAR(100),
    `开户行` VARCHAR(200),
    `备注` TEXT,
    `用款月份` DATE,
    `用款年度` DATE,
    `流程状态` VARCHAR(20),
    `当前节点` VARCHAR(100),
    `项目名称` VARCHAR(200),
    `当前审批人` VARCHAR(50),
    `审批完成时间` DATETIME,
    `预算项目` VARCHAR(200),
    `预算剩余额度` DECIMAL(15,2),
    `云之家ID` VARCHAR(100),
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_制单日期` (`制单日期`),
    INDEX `idx_使用部门` (`使用部门`),
    INDEX `idx_流程状态` (`流程状态`),
    INDEX `idx_申请金额` (`申请金额`),
    INDEX `idx_大类目` (`大类目`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

# 列名列表
COLUMNS = [
    '流水号', '标题', '申请人', '制单部门', '制单日期', '使用部门',
    '使用单位', '使用类型', '普通类型', '大类目', '申请金额', '用途',
    '付款方式', '收款人', '银行账户', '开户行', '备注', '用款月份',
    '用款年度', '流程状态', '当前节点', '项目名称', '当前审批人',
    '审批完成时间', '预算项目', '预算剩余额度', '云之家ID'
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


def fetch_payment_request(cookie, page_size=100, page_number=1, search_items=None):
    """从云之家 API 获取用款申请数据"""
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
        # 尝试解析 "2026-05" 格式 (用款月份)
        try:
            dt = datetime.strptime(ts, "%Y-%m")
            return dt.strftime("%Y-%m-%d")
        except:
            pass
        # 尝试解析 "2026" 格式 (用款年度)
        try:
            dt = datetime.strptime(ts, "%Y")
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


def parse_datetime_timestamp(ts):
    """解析时间戳或日期时间字符串"""
    if not ts:
        return None
    # 如果是字符串格式的日期时间
    if isinstance(ts, str):
        # 尝试解析 "2025-09-15 09:26:35" 格式
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        # 尝试解析 "2025-09-15" 格式
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d 00:00:00")
        except:
            pass
        return None
    # 如果是毫秒时间戳
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return None


def parse_amount(value):
    if value is None or value == '' or value == '*':
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '')
        return float(value)
    except:
        return None


def extract_amount_from_title(title, original_amount):
    """从标题中提取金额"""
    if original_amount and original_amount > 0:
        return original_amount
    if not title:
        return 0
    match = re.search(r'用款([\d.]+)元', title)
    if match:
        try:
            return float(match.group(1))
        except:
            pass
    return 0


def clean_value(val):
    """清理值，处理None、*及dict-like对象"""
    if val is None or val == '*':
        return None
    # 处理dict/对象类型 (如 basicDataWidget 返回 {"showName":"xxx","name":"xxx"})
    if isinstance(val, dict):
        # 优先取 showName，再取 name，最后取 number
        if 'showName' in val and val['showName']:
            return val['showName']
        if 'name' in val and val['name']:
            return val['name']
        if 'number' in val and val['number']:
            return val['number']
        return str(val)
    # 处理列表中含有dict (如 basicDataWidget 返回 [{...}])
    if isinstance(val, list) and len(val) > 0:
        if isinstance(val[0], dict):
            item = val[0]
            if 'showName' in item and item['showName']:
                return item['showName']
            if 'name' in item and item['name']:
                return item['name']
            if 'number' in item and item['number']:
                return item['number']
        return str(val[0]) if val else None
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
        
        serial_no = cols.get("_S_SERIAL")
        if not serial_no:
            continue
        
        title = cols.get("_S_TITLE")
        original_amount = parse_amount(cols.get("Mo_0"))
        amount = extract_amount_from_title(title, original_amount)
        budget_remaining = parse_amount(cols.get("Nu_0"))
        
        values = (
            clean_value(serial_no),
            clean_value(title),
            clean_value(cols.get("_S_APPLY")),
            clean_value(cols.get("_S_DEPT")),
            parse_timestamp(cols.get("_S_DATE")),
            clean_value(cols.get("Ds_0")),
            clean_value(cols.get("Ra_1")),
            clean_value(cols.get("Ra_4")),
            clean_value(cols.get("Ra_5")),
            clean_value(cols.get("Ra_6")),
            amount,
            clean_value(cols.get("Ta_2")),
            clean_value(cols.get("Te_4")),
            clean_value(cols.get("Bd_1")),
            clean_value(cols.get("Te_1")),
            clean_value(cols.get("Te_2")),
            clean_value(cols.get("Te_5")),
            parse_timestamp(cols.get("Da_0")),
            parse_timestamp(cols.get("Da_2")),
            clean_value(cols.get("_S_STATUS")),
            clean_value(cols.get("activityName")),
            clean_value(cols.get("Te_8")),
            clean_value(cols.get("approver")),
            parse_datetime_timestamp(cols.get("_S_FINISH_TIME")),
            clean_value(cols.get("Bd_0")),
            budget_remaining,
            record.get("id")
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
    print("开始同步云之家用款申请数据到 MySQL")
    print("=" * 50)
    
    init_database()
    cookie = get_cookie()
    print("Cookie 读取成功")
    
    page_number = 1
    total_saved = 0
    
    while True:
        print(f"\n正在获取第 {page_number} 页...")
        result = fetch_payment_request(cookie, page_size=100, page_number=page_number)
        
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
            result = fetch_payment_request(cookie, page_size=100, page_number=page, search_items=single_search)
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
    
    result = fetch_payment_request(cookie, search_items=search_items)
    
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
    
    parser = argparse.ArgumentParser(description="云之家用款申请数据同步 (MySQL)")
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

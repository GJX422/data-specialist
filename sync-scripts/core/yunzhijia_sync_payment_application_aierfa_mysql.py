#!/usr/bin/env python3
"""
云之家付款申请单（爱尔发）数据同步脚本 (MySQL 版)
功能：从云之家 API 拉取爱尔发付款申请单数据，写入 MySQL 数据库
表单：付款申请单（埃尔发版），含付款明细子表
"""

import urllib.request
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 导入通用模块
import sys
sys.path.insert(0, str(Path.home() / '.hermes' / 'scripts'))
from yunzhijia_mysql_base import get_mysql_connection, get_cookie, MYSQL_CONFIG

# ============ 配置 ============
API_URL = "https://www.yunzhijia.com/api/lightcloud/datalist/instance/search2Gen"
TABLE_NAME = "付款单（爱尔发）"

# 爱尔发付款申请单表单配置
FORM_CODE_ID = "00bf561f68c2406ebed5f1ed77c3a74e"
VIEW_ID = "697ac8cd48fc281b1299d007"

# 要查询的字段（完整 resultItems）
# 子表字段用 flat+parentCodeId 独立请求
RESULT_ITEMS = [
    {"sum": False, "title": "请款人", "type": "personSelectWidget", "codeId": "Ps_0"},
    {"sum": False, "title": "标题", "type": "textWidget", "codeId": "_S_TITLE"},
    {"sum": False, "title": "制单日期", "type": "dateWidget", "codeId": "_S_DATE"},
    {"sum": False, "title": "付款组织", "type": "basicDataWidget", "codeId": "Bd_0"},
    {"sum": False, "title": "业务日期", "type": "dateWidget", "codeId": "Da_0"},
    {"sum": False, "title": "付款账号", "type": "basicDataWidget", "codeId": "Bd_1"},
    {"sum": False, "title": "结算方式", "type": "basicDataWidget", "codeId": "Bd_2"},
    {"sum": False, "title": "申请收款单位", "type": "textWidget", "codeId": "Te_2"},
    {"sum": False, "title": "本位币", "type": "basicDataWidget", "codeId": "Bd_3"},
    {"sum": False, "title": "开户银行", "type": "textWidget", "codeId": "Te_3"},
    {"sum": False, "title": "单据类型", "type": "basicDataWidget", "codeId": "Bd_4"},
    {"sum": False, "title": "单位类型", "type": "enumWidget", "codeId": "En_3"},
    {"sum": False, "title": "账号", "type": "textWidget", "codeId": "Te_4"},
    # Dd_0 子表字段：flat+parentCodeId
    {"sum": False, "title": "付款明细-实付金额", "type": "numberWidget", "codeId": "Nu_0", "parentCodeId": "Dd_0"},
    {"sum": False, "title": "付款明细-往来单位类型", "type": "enumWidget", "codeId": "En_1", "parentCodeId": "Dd_0"},
    {"sum": False, "title": "付款明细-往来单位", "type": "multiBasicDataWidget", "codeId": "Mbd_0", "parentCodeId": "Dd_0"},
    {"sum": False, "title": "付款明细-付款用途", "type": "basicDataWidget", "codeId": "Bd_6", "parentCodeId": "Dd_0"},
    {"sum": False, "title": "收款单位类型", "type": "enumWidget", "codeId": "En_2"},
    {"sum": False, "title": "收款单位", "type": "multiBasicDataWidget", "codeId": "Mbd_1"},
    {"sum": False, "title": "是否传ERP", "type": "radioWidget", "codeId": "Ra_2"},
    {"sum": False, "title": "流程状态", "type": "radioWidget", "codeId": "_S_STATUS"},
    {"sum": False, "title": "单据号回写", "type": "fusionFormWidget", "codeId": "Ff_0"},
    {"sum": False, "title": "当前节点", "type": "textWidget", "codeId": "activityName"},
    {"sum": False, "title": "当前审批人", "type": "personSelectWidget", "codeId": "approver"},
    {"sum": False, "title": "预算项目", "type": "basicDataWidget", "codeId": "Bd_7"},
    {"sum": False, "title": "审批完成时间", "type": "dateWidget", "codeId": "_S_FINISH_TIME"},
    {"sum": False, "title": "预算部门", "type": "departmentSelectWidget", "codeId": "Ds_0"},
    {"sum": False, "title": "业务月份", "type": "dateWidget", "codeId": "Da_2"},
    {"sum": False, "title": "业务年度", "type": "dateWidget", "codeId": "Da_1"},
    {"sum": False, "title": "大类目", "type": "radioWidget", "codeId": "Ra_0"},
    {"sum": False, "title": "金额辅助", "type": "moneyWidget", "codeId": "Mo_0"},
    {"sum": False, "title": "是否生成流水", "type": "radioWidget", "codeId": "Ra_3"},
    {"sum": False, "title": "项目（名称）", "type": "textWidget", "codeId": "Te_0"},
    {"sum": False, "title": "单据来源类型", "type": "radioWidget", "codeId": "Ra_1"},
    {"sum": False, "title": "来源单据流水", "type": "textWidget", "codeId": "Te_1"},
]

# MySQL 表结构
CREATE_TABLE_SQL = """CREATE TABLE IF NOT EXISTS `付款单（爱尔发）` (
    `序号` INT AUTO_INCREMENT PRIMARY KEY,
    `云之家ID` VARCHAR(100) UNIQUE COMMENT '表单实例ID formInstId',
    `请款人` VARCHAR(50),
    `标题` VARCHAR(500),
    `制单日期` DATE,
    `付款组织` VARCHAR(200),
    `业务日期` DATE,
    `付款账号` VARCHAR(200),
    `结算方式` VARCHAR(100),
    `申请收款单位` VARCHAR(500),
    `本位币` VARCHAR(50),
    `开户银行` VARCHAR(200),
    `单据类型` VARCHAR(200),
    `单位类型` VARCHAR(50),
    `账号` VARCHAR(200),
    `收款单位类型` VARCHAR(50),
    `收款单位` VARCHAR(500),
    `是否传ERP` VARCHAR(20),
    `流程状态` VARCHAR(20),
    `单据号回写` VARCHAR(200),
    `当前节点` VARCHAR(200),
    `当前审批人` VARCHAR(50),
    `预算项目` VARCHAR(200),
    `审批完成时间` DATETIME,
    `预算部门` VARCHAR(200),
    `业务月份` DATE,
    `业务年度` DATE,
    `大类目` VARCHAR(100),
    `金额辅助` DECIMAL(15,2),
    `是否生成流水` VARCHAR(20),
    `项目名称` VARCHAR(200),
    `单据来源类型` VARCHAR(50),
    `来源单据流水` VARCHAR(200),
    `同步时间` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_制单日期` (`制单日期`),
    INDEX `idx_流程状态` (`流程状态`),
    INDEX `idx_付款组织` (`付款组织`),
    INDEX `idx_业务月份` (`业务月份`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

COLUMNS = [
    '云之家ID', '请款人', '标题', '制单日期', '付款组织', '业务日期',
    '付款账号', '结算方式', '申请收款单位', '本位币', '开户银行', '单据类型',
    '单位类型', '账号', '收款单位类型', '收款单位', '是否传ERP',
    '流程状态', '单据号回写', '当前节点', '当前审批人', '预算项目',
    '审批完成时间', '预算部门', '业务月份', '业务年度', '大类目', '金额辅助',
    '子表_实付金额', '子表_往来单位类型', '子表_往来单位', '子表_付款用途',
    '是否生成流水', '项目名称', '单据来源类型', '来源单据流水'
]


def init_database():
    conn = get_mysql_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print(f"数据库表初始化完成: {TABLE_NAME}")
    finally:
        cursor.close()
        conn.close()


def fetch_payment_applications(cookie, page_size=100, page_number=1, search_items=None):
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
    if not ts:
        return None
    if isinstance(ts, str):
        try:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d")
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
        return dt.strftime("%Y-%m-%d")
    except:
        return None


def parse_datetime_timestamp(ts):
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


def parse_amount(value):
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_value(val):
    if val is None or val == '*':
        return None
    return val


def parse_sub_table(col_list, parent_code_id):
    """从colList中解析子表数据（flat格式）"""
    result = {}
    for c in col_list:
        code_id = c['codeId']
        value = c.get('value')
        # 检查是否是子表字段（通过parentCodeId判断）
        if c.get('parentCodeId') == parent_code_id:
            if value:
                try:
                    parsed = json.loads(value)
                    result[code_id] = parsed[0] if isinstance(parsed, list) and len(parsed) > 0 else parsed
                except:
                    result[code_id] = value
            else:
                result[code_id] = None
    return result if result else None


def save_to_database(records):
    if not records:
        print("没有数据需要保存")
        return 0

    conn = get_mysql_connection()
    cursor = conn.cursor()

    col_names = ', '.join([f'`{col}`' for col in COLUMNS])
    placeholders = ', '.join(['%s'] * len(COLUMNS))
    update_cols = [col for col in COLUMNS if col != '云之家ID']
    update_clause = ', '.join([f'`{col}` = VALUES(`{col}`)' for col in update_cols])

    sql = f"""INSERT INTO `{TABLE_NAME}` ({col_names})
              VALUES ({placeholders})
              ON DUPLICATE KEY UPDATE {update_clause}"""

    saved_count = 0
    for record in records:
        cols = {c["codeId"]: c["value"] for c in record["colList"]}

        instance_id = record.get("formInstId", "")
        if not instance_id:
            instance_id = record.get("id", "")
        if not instance_id:
            continue

        title = cols.get("_S_TITLE", "")
        amount = parse_amount(cols.get("Mo_0"))

        # 收款单位
        payee = cols.get("Mbd_1")
        if payee and isinstance(payee, str) and payee.startswith('['):
            try:
                parsed = json.loads(payee)
                if isinstance(parsed, list):
                    payee_str = ';'.join(str(x) if not isinstance(x, dict) else x.get('name', str(x)) for x in parsed)
                else:
                    payee_str = str(parsed)
            except:
                payee_str = payee
        elif payee and isinstance(payee, list):
            payee_str = ';'.join(str(x) if not isinstance(x, dict) else x.get('name', str(x)) for x in payee)
        else:
            payee_str = clean_value(payee) if not isinstance(payee, (list, dict)) else None
        # 解析子表数据
        sub_table = parse_sub_table(record.get('colList', []), 'Dd_0')
        sub_amount = parse_amount(sub_table.get('Nu_0')) if sub_table else None
        sub_counterpart_type = clean_value(sub_table.get('En_1')) if sub_table else None
        sub_counterpart = clean_value(sub_table.get('Mbd_0')) if sub_table else None
        sub_purpose = clean_value(sub_table.get('Bd_6')) if sub_table else None

        values = (
            clean_value(instance_id),
            clean_value(cols.get("Ps_0")),
            clean_value(title),
            parse_timestamp(cols.get("_S_DATE")),
            clean_value(cols.get("Bd_0")),
            parse_timestamp(cols.get("Da_0")),
            clean_value(cols.get("Bd_1")),
            clean_value(cols.get("Bd_2")),
            clean_value(cols.get("Te_2")),
            clean_value(cols.get("Bd_3")),
            clean_value(cols.get("Te_3")),
            clean_value(cols.get("Bd_4")),
            clean_value(cols.get("En_3")),
            clean_value(cols.get("Te_4")),
            clean_value(cols.get("En_2")),
            payee_str,
            clean_value(cols.get("Ra_2")),
            clean_value(cols.get("_S_STATUS")),
            clean_value(cols.get("Ff_0")),
            clean_value(cols.get("activityName")),
            clean_value(cols.get("approver")),
            clean_value(cols.get("Bd_7")),
            parse_datetime_timestamp(cols.get("_S_FINISH_TIME")),
            clean_value(cols.get("Ds_0")),
            parse_timestamp(cols.get("Da_2")),
            parse_timestamp(cols.get("Da_1")),
            clean_value(cols.get("Ra_0")),
            amount,
            sub_amount,
            sub_counterpart_type,
            sub_counterpart,
            sub_purpose,
            clean_value(cols.get("Ra_3")),
            clean_value(cols.get("Te_0")),
            clean_value(cols.get("Ra_1")),
            clean_value(cols.get("Te_1")),
        )

        try:
            cursor.execute(sql, values)
            saved_count += 1
        except Exception as e:
            print(f"  保存记录失败 [{instance_id}]: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    return saved_count


def sync_all():
    print("=" * 50)
    print("开始同步云之家付款申请单（爱尔发）数据到 MySQL")
    print("=" * 50)

    init_database()
    cookie = get_cookie()
    print("Cookie 读取成功")

    page_number = 1
    total_saved = 0

    while True:
        print(f"\n正在获取第 {page_number} 页...")
        result = fetch_payment_applications(cookie, page_size=100, page_number=page_number)

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
            result = fetch_payment_applications(cookie, page_size=100, page_number=page, search_items=single_search)
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

    search_items = [
        {"codeId": "_S_DATE", "condition": "RANGE", "value": [start_ts, end_ts]}
    ]

    result = fetch_payment_applications(cookie, search_items=search_items)

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

    parser = argparse.ArgumentParser(description="云之家付款申请单（爱尔发）数据同步")
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

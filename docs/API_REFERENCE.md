# 📚 API参考

## 云之家API

### 基础信息

- **Base URL**: `https://open.yunzhijia.com`
- **认证方式**: App ID + Secret
- **API版本**: v1

### 主要接口

#### 1. 获取Access Token

```
POST /gateway/app/accesstoken
```

**请求参数**：
- `appId`: 应用ID
- `secret`: 应用密钥
- `scope`: 权限范围（app）

**响应**：
```json
{
  "accessToken": "xxx",
  "expiresIn": 7200
}
```

#### 2. 查询审批记录

```
POST /gateway/workflow/v2/inst/searchItems
```

**请求参数**：
- `accessToken`: 访问令牌
- `appUniqueId`: 应用唯一标识
- `_S_STATUS`: 状态过滤（rawValue）
- `_S_START_DATE`: 开始日期
- `_S_END_DATE`: 结束日期
- `pageNum`: 页码
- `pageSize`: 每页数量（最大100）

**状态过滤值**：
- `RUNNING`: 审批中
- `FINISH`: 已完成
- `RETURNED`: 待提交
- `ABANDON`: 已废弃

**响应**：
```json
{
  "data": {
    "list": [...],
    "total": 100
  }
}
```

#### 3. 获取所有人员

```
POST /gateway/org/v3/person/getAllPersons
```

**请求参数**：
- `accessToken`: 访问令牌
- `scope`: 权限范围（app）

**响应**：
```json
{
  "data": {
    "persons": [
      {
        "openId": "xxx",
        "name": "张三",
        "department": "xxx"
      }
    ]
  }
}
```

### 错误处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| 401 | 未授权 | 重新获取Token |
| 403 | 无权限 | 检查App权限配置 |
| 429 | 请求过多 | 降低请求频率 |
| 500 | 服务器错误 | 稍后重试 |

## 金蝶云星空API

### 基础信息

- **Base URL**: `https://kingdee.example.com`
- **认证方式**: App ID + App Secret
- **API版本**: v1

### 主要接口

#### 1. 获取Token

```
POST /api/v1/auth/token
```

**请求参数**：
- `appId`: 应用ID
- `appSecret`: 应用密钥

**响应**：
```json
{
  "accessToken": "xxx",
  "expiresIn": 7200
}
```

#### 2. 查询销售订单

```
POST /api/v1/sales/order/list
```

**请求参数**：
- `accessToken`: 访问令牌
- `filter`: 过滤条件
- `pageSize`: 每页数量
- `pageNum`: 页码

**响应**：
```json
{
  "data": {
    "list": [...],
    "total": 100
  }
}
```

### 错误处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| 401 | 未授权 | 重新获取Token |
| 403 | 无权限 | 检查应用权限 |
| 500 | 服务器错误 | 稍后重试 |

## IMA API

### 基础信息

- **Base URL**: `https://api.ima.example.com`
- **认证方式**: Client ID + API Key

### 主要接口

#### 1. 上传文件

```
POST /api/v1/files/upload
```

**请求参数**：
- `file`: 文件内容
- `fileName`: 文件名
- `folderId`: 文件夹ID

**响应**：
```json
{
  "fileId": "xxx",
  "url": "https://..."
}
```

#### 2. 创建笔记

```
POST /api/v1/notes/create
```

**请求参数**：
- `title`: 标题
- `content`: 内容
- `folderId`: 文件夹ID

**响应**：
```json
{
  "noteId": "xxx",
  "url": "https://..."
}
```

## 数据库连接

### MySQL连接配置

```python
import pymysql

config = {
    "host": "183.224.204.51",
    "port": 53306,
    "user": "yunzhijia_rw",
    "password": "your_password",
    "database": "yunzhijia",
    "charset": "utf8mb4"
}

connection = pymysql.connect(**config)
```

### 主要表结构

#### 云之家_费用报销申请

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| 单据编号 | VARCHAR | 单据编号 |
| 制单日期 | DATE | 创建日期 |
| 状态 | VARCHAR | 审批状态 |
| 金额 | DECIMAL | 报销金额 |
| 事由 | TEXT | 报销事由 |

#### 云之家_用款申请

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| 单据编号 | VARCHAR | 单据编号 |
| 制单日期 | DATE | 创建日期 |
| 状态 | VARCHAR | 审批状态 |
| 申请金额 | DECIMAL | 申请金额 |
| 用途 | TEXT | 用途说明 |

## 配置文件

### config.json 结构

```json
{
  "mysql": {
    "host": "数据库主机",
    "port": 53306,
    "user": "用户名",
    "password": "密码",
    "database": "数据库名"
  },
  "yunzhijia": {
    "app_id": "应用ID",
    "secret": "应用密钥"
  },
  "kingdee": {
    "app_id": "应用ID",
    "app_secret": "应用密钥"
  },
  "ima": {
    "client_id": "客户端ID",
    "api_key": "API密钥"
  }
}
```

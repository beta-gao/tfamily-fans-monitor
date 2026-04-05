# TF 家族智能看板

这是一个轻量级的 TF 家族数据看板项目。

目前项目已经完成第一期存储升级：采集和看板主流程改为使用 SQLite，而不是持续追加单个 CSV 文件。

## 项目结构

- `spider.py`: 定时抓取成员数据并写入 SQLite
- `dashboard_server.py`: 启动网页服务并提供 JSON 接口
- `db.py`: SQLite 建表、写入、查询和 CSV 导入逻辑
- `import_csv_to_sqlite.py`: 将历史 CSV 一次性导入 SQLite
- `draw.py`: 旧的 CSV 绘图脚本，暂未迁移
- `web/index.html`: 看板页面
- `web/app.js`: 前端逻辑
- `web/styles.css`: 页面样式

## 环境变量

参考 `.env.example`：

- `TF_AUTH_TOKEN`: 采集接口使用的 token
- `TF_DB_FILE`: SQLite 数据库文件路径
- `TF_POLL_INTERVAL_SECONDS`: 抓取间隔秒数
- `TF_DASHBOARD_HOST`: Web 服务监听地址
- `TF_DASHBOARD_PORT`: Web 服务端口

## 启动看板

```powershell
python dashboard_server.py
```

默认地址：

```text
http://127.0.0.1:8000
```

## 导入历史 CSV

如果你已有旧的 `tf_family_fans_multi.csv`，先执行一次导入：

```powershell
python import_csv_to_sqlite.py --csv tf_family_fans_multi.csv --db tf_dashboard.sqlite3
```

这个脚本会：

- 初始化数据库和索引
- 导入历史有效数据
- 自动跳过重复记录
- 将历史错误行写入 `error_message` 字段

## 部署思路

当前部署方式适合单机服务器：

- `spider.py` 作为一个 `systemd` 服务持续采集
- `dashboard_server.py` 作为一个 `systemd` 服务提供网页和 API
- 反向代理（如 Nginx/Caddy）把域名请求转发到 `127.0.0.1:8000`

示例 service 文件见：

- `deploy/tf-spider.service`
- `deploy/tf-dashboard.service`

## 后续建议

- 将 `draw.py` 和其它历史 CSV 工具也迁移到 SQLite
- 为趋势接口增加时间范围查询，避免前端一次读取全部历史
- 增加归档策略，例如保留原始高频数据并额外维护小时级汇总表

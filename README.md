# TF 家族智能看板

这是一个基于现有 CSV 监控数据搭建的轻量网页看板项目。

## 当前结构

- `spider.py`: 定时抓取成员数据并追加写入 `tf_family_fans_multi.csv`
- `draw.py`: 从 CSV 生成静态图
- `dashboard_server.py`: 启动网页服务并提供 JSON 接口
- `web/index.html`: 看板页面
- `web/app.js`: 前端渲染逻辑
- `web/styles.css`: 页面样式

## 启动网页看板

```powershell
python dashboard_server.py
```

默认地址:

```text
http://127.0.0.1:8000
```

## 看板内容

- 核心概览: 成员数、总粉丝、累计增长、最近增长
- 智能洞察: 自动提炼领跑者、最近冲刺、累计涨幅和波动提醒
- 粉丝总量趋势图
- 相对增长趋势图
- 成员排行表

## 后续建议

- 将 `spider.py` 中的 token 改成环境变量
- 为接口增加缓存和权限控制
- 将 CSV 升级为 SQLite 或 PostgreSQL
- 部署到云服务器或静态站点前端 + API 服务

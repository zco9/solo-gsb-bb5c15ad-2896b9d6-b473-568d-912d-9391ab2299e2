# 木作裁条排样助手

基于 **Python FastAPI + 原生 HTML/CSS/JavaScript** 的一维裁条下料（排样）Web 应用，无需账号，开箱即用。

## 功能

- 输入新料定长、已有余料（逐根长度）、锯缝宽度、裁件长度与数量（裁件总数 ≤ 12 件）
- 精确求解逐根裁切方案，优化目标按字典序：
  1. **新料使用根数最少**；
  2. 新料根数相同时，**已使用原料（新料 + 已动用余料）的尾料总长最少**
- 锯缝规则：每切下一件扣一次锯缝；**末段恰好作为裁件（尾料为 0）时不另扣锯缝**；装不下的裁件不会被硬塞进原料
- 逐根列出每根原料的裁件、锯缝损耗和尾料，并附比例条形图
- 裁件超长无法裁切时，明确指出超长裁件
- 一键打印方案（打印视图自动隐藏输入区）

## 快速启动（单条命令）

```bash
docker compose up --build
```

依赖安装随容器启动自动完成（镜像构建时预装，容器启动命令再次确认后启动服务）。

- 访问地址：**http://localhost:8000**
- 端口：**8000**
- 停止：`Ctrl + C`，或 `docker compose down`

## 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| 对外端口 | `8000` | 通过环境变量 `PORT` 修改，如 `PORT=8080 docker compose up --build`，然后访问 http://localhost:8080 |
| 裁件总数上限 | 12 件 | 代码常量 `MAX_PIECES`（`app/optimizer.py`） |
| 余料根数上限 | 30 根 | 代码常量 `MAX_REMNANTS`（`app/optimizer.py`） |

## 使用说明

1. 填写 **新料定长** 与 **锯缝宽度**（单位 mm，支持小数）；
2. 按需添加 **已有余料**（每行一根的长度，可留空）；
3. 添加 **裁件清单**（长度 + 数量，总件数 ≤ 12）；
4. 点击 **生成裁切方案**，页面下方展示汇总与每根原料的裁件、锯缝损耗、尾料；
5. 点击 **🖨️ 打印方案** 输出纸质裁切单。

## 本地开发（不使用 Docker）

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 项目结构

```
├── app/
│   ├── main.py          # FastAPI 应用：页面路由与 /api/optimize 接口
│   ├── optimizer.py     # 排样算法：子集 DP（NumPy 向量化）精确求解
│   └── static/
│       ├── index.html   # 单页页面
│       ├── style.css    # 样式（含打印样式）
│       └── app.js       # 前端交互与结果渲染
├── requirements.txt     # Python 依赖
├── Dockerfile           # 镜像构建；容器启动时完成依赖安装并启动服务
├── docker-compose.yml   # 单服务编排，端口 ${PORT:-8000}:8000
└── README.md
```

## 接口说明

`POST /api/optimize`

```json
{
  "stock_length": 2440,
  "kerf": 3,
  "remnants": [1250, 700],
  "pieces": [{"length": 600, "qty": 2}, {"length": 300, "qty": 3}]
}
```

返回 `ok: true` 时含 `summary`（新料/余料使用根数、尾料合计、锯缝损耗合计）、`plans`（每根原料的裁件、锯缝损耗、尾料）与 `unused_remnants`；无法裁切时返回 `ok: false` 及 `overlong_pieces`（超长裁件清单）。

# 木作裁条排样（Wood Cut Planner）

一个无需账号的木作裁条排样 Web 应用。输入**新料定长**、**已有余料各根长度**、**锯缝宽度**以及**裁件长度与数量（总计不超过 12 件）**，自动生成**逐根原料的裁切方案**。

- 后端：Python 3.11 + FastAPI
- 前端：原生 HTML / CSS / JavaScript（无构建步骤）
- 优化目标（按优先级）：
  1. **使用的新料根数最少**；
  2. 新料根数相同时，**所有已动用原料的尾料总长最少**（未动用的余料不计）。
- 锯缝计量：每切下一件扣一次锯缝；**末段恰好作为裁件（零尾料）时不另扣该道锯缝**。
- 采用子集动态规划精确求解（裁件 ≤ 12 件），**任何装不下的裁件都不会被硬塞进原料**。
- 支持浏览器直接打印（或另存为 PDF）。

## 一条命令启动

```bash
docker compose up -d --build
```

启动后访问：

> **http://localhost:8000**

依赖（FastAPI / Uvicorn 等）在**容器启动时**由 `entrypoint.sh` 自动安装完成，无需在宿主机预装 Python 环境。

停止：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f
```

## 必要配置

所有配置集中在 `docker-compose.yml`：

| 配置项 | 位置 | 默认值 | 说明 |
| --- | --- | --- | --- |
| 宿主机访问端口 | `ports` 左侧 | `8000` | 改为如 `9000:8000` 即可通过 http://localhost:9000 访问 |
| 容器监听端口 | `environment.PORT` | `8000` | 与 `ports` 右侧保持一致 |
| 重启策略 | `restart` | `unless-stopped` | 可按需删除或修改 |

应用本身无数据库、无外部依赖、无需账号或密钥。

### 不用 Compose 时

```bash
docker build -t woodcut-planner .
docker run --rm -p 8000:8000 woodcut-planner
```

### 本地开发运行（可选）

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## 输入说明

| 输入 | 约束 |
| --- | --- |
| 新料定长 | 正数（如 2400 mm） |
| 锯缝宽度 | ≥ 0（如 3 mm，可填 0） |
| 已有余料 | 每行一根长度；可留空、可增删；最多 30 根 |
| 裁件清单 | 每行“长度 + 数量”；裁件总数（各行数量之和）**≤ 12** |

长度支持小数（如 498.5），单位自行统一（页面按 mm 展示）。

## 输出说明

- 顶部统计：使用新料根数、动用余料根数、裁件总长、锯缝总损耗、尾料总长。
- 每根动用的原料一张卡片：
  - 标签区分**新料 #N** / **余料 #N**（序号与输入一致）；
  - 料条示意：木纹块=裁件、斜纹块=锯缝、浅色块=尾料；
  - 逐段数字标注，以及该根的**锯缝损耗**与**尾料**；
  - 零尾料且末件免锯缝时标注“末段恰为裁件 · 免末道锯缝”。
- 未动用的余料单独列出，可继续留存。
- 存在超长裁件时，页面指出对应的输入行与长度（该裁件单放最长原料、只切一件也排不下），此时不会给出错误方案。

## 接口

- `GET /`：页面
- `POST /api/solve`：排样计算
  ```json
  {
    "new_length": 2400,
    "leftovers": [1200, 800],
    "kerf": 3,
    "pieces": [{"length": 800, "qty": 2}, {"length": 600, "qty": 3}]
  }
  ```
- `GET /api/health`：健康检查
- 交互式文档（FastAPI 自带）：http://localhost:8000/docs

## 目录结构

```
.
├── app/
│   ├── main.py          # FastAPI 路由与输入校验
│   ├── solver.py        # 排样核心：子集 DP、精确最优
│   └── static/
│       ├── index.html   # 页面
│       ├── style.css    # 样式（含打印样式）
│       └── app.js       # 前端交互
├── requirements.txt
├── entrypoint.sh        # 容器启动时安装依赖并启动服务
├── Dockerfile
└── docker-compose.yml
```

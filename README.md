# LoomLot-01 · 染坊缸染与色牢度抽检

靛蓝染坊台：按 **染坊 → 染缸 → 染程 → 色牢度** 工序推进，聚焦缸染调度与抽检，不是库存出入库系统。

## 技术栈

| 层 | 技术 |
| --- | --- |
| Backend | FastAPI + SQLAlchemy 2 + Pydantic v2 + Postgres + JWT |
| Frontend | Svelte 4 + Vite + svelte-spa-router |
| 部署 | docker-compose（db + backend + frontend/nginx） |

## 端口

| 服务 | 端口 |
| --- | --- |
| 前端 | **3600** |
| 后端 API | **8600** |
| PostgreSQL | **5439** |

数据库账号：`loomlot` / `loomlot` / 库名 `loomlot`。

## 演示账号

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | 染坊主管 |
| `dyer` | `123456` | 染程操作员 |

容器启动时 entrypoint 自动建表并 seed。

## 快速启动

```bash
cd D:\work\document\bytecode\claudeCodePro\LoomLot\LoomLot-01
docker compose up -d --build
```

浏览器：http://localhost:3600  
API：http://localhost:8600/api/health

停止：

```bash
docker compose down
```

## 业务实体

1. **DyeHouse** — `name`, `waterNote`, `notes`
2. **Vat** — `dyeHouseId`, `vatCode`, `fiberType`, `capacityL`, `status` ∈ `ready|dyeing|drain`
3. **QueueTicket（叫号排队）** — `vatId`, `takenAt`, `calledAt`(可空), `voidedAt`(可空), `completedAt`(可空), `takenBy`, `dyeLotId`
4. **DyeLot** — `vatId`, `recipeName`, `fabricKg`, `startedAt`, `operatorName`
5. **FastnessCheck** — `dyeLotId`, `checkedAt`, `washFastness`(1–5), `rubFastness`(>0), `tempC`, `notes`

### 规则

- 开染程必须先叫号：操作员可取号，**叫号仅主管**（admin）
- 同一染缸「未作废且未完成」的号同时最多一个
- 叫号后 **30 分钟**内必须开出染程，超时该号自动作废；作废判定与开立拦截共用同一套时钟规则（下一次读/写排队状态时生效）
- 未叫号或号已作废（含超时）时开染程返回 **409 中文**
- 叫号后开立染程成功，该号即完成并挂到该染程；同一号不得再开第二笔染程（改挂染缸同样须有有效叫号并消费该号）
- 仅当染缸状态为 `ready` 或 `dyeing` 时可新建染程，否则 409；新建染程后染缸自动设为 `dyeing`
- 染缸列表返回 `currentTicket`（当前号简要状态）；看板 `queueWaitingCount` 为等待叫号条数，与排队列表等待行同一口径
- 可选接口：`POST /api/vats/{id}/drain` 将染缸置为 `drain`
- 种子数据：一号染缸（V-01）已有一笔「已取号、未叫号」的排队号

## 主要 API

- `POST /api/auth/login`（OAuth2 表单）
- `GET /api/auth/me`
- `GET/POST/PUT/DELETE /api/dye-houses`
- `GET/POST/PUT/DELETE /api/vats` · `POST /api/vats/{id}/drain`
- `GET /api/queue`（`scope=active|all`，可选 `vatId`）· `POST /api/queue/take`（操作员取号）· `POST /api/queue/{id}/call`（仅主管叫号）
- `GET/POST/PUT/DELETE /api/dye-lots`
- `GET/POST/PUT/DELETE /api/fastness-checks`
- `GET /api/dashboard/stats`

除登录外需 `Authorization: Bearer <token>`。字段对外为 camelCase。

## 目录

```
LoomLot-01/
├── docker-compose.yml
├── backend/          # FastAPI
├── frontend/         # Svelte 4 + Vite + nginx
└── README.md
```

## 本地开发

### 数据库

```bash
docker compose up -d db
```

### 后端

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg2://loomlot:loomlot@127.0.0.1:5439/loomlot"
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
uvicorn app.main:app --reload --port 8600
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发态 Vite 将 `/api` 代理到 `http://127.0.0.1:8600`。

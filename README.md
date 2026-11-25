# H5ERP 进销存（PC 端）

进销存管理后台。原 **PHP 5.6 + CodeIgniter 2.2.5**，已升级到 **PHP 8.2 + Apache**，并做成 Docker 镜像，本地和云端都能跑。

**数据库不在镜像里**：使用外部 MySQL（自备），容器只跑应用。

---

## 功能

| 模块 | 内容 |
|---|---|
| 基础资料 | 商品、客户、供应商、仓库、计量单位、结算账户、员工、辅助属性 |
| 单据 | 采购入库、销货出库、调拨、收款、付款、其他入库/出库、成本调整、销售订单 |
| 库存 | 实时库存、盘点、库存预警 |
| 报表 | 销售/采购明细与汇总、往来欠款、应收应付、现金银行、商品库存余额等 51 个 |
| 其他 | Excel 导入导出、PDF 打印（含套打）、数据库备份/恢复、用户与权限 |

---

## 环境要求

- Docker 20.10+，Docker Compose v2
- **MySQL 5.7+ / 8.0 或 MariaDB 10.4+**（自备，需允许应用所在机器访问）
- 浏览器：Chrome / Edge

---

## 一、本地部署

### 方式 1：一条命令（应用 + MySQL，最快）

```bash
git clone git@github.com:szft2026/erp.git
cd erp

docker compose -f docker-compose.local.yml up -d --build
```

打开 <http://localhost:8080>，账号 `admin / admin888`。

首次启动会自动建库、导入 `erp.sql`（25 张表 + 管理员 + 菜单）。

#### 数据库参数

方式 1 的 MySQL 就在 compose 里，**不用填 `DB_HOST`**（应用用服务名 `db` 连接）。默认 root 密码 `root123`、库名 `erp`；想改就在 `erp/` 下建 `.env`：

```env
DB_PASSWORD=换成你的强密码
DB_DATABASE=erp
```

只在 **`db-data` 卷第一次创建时**生效，已初始化过再改不会改变 MySQL 里的密码（见「六、升级与备份」）。

### 方式 2：只跑应用，接本机或远程 MySQL

```bash
docker build -t h5erp .

docker run -d --name h5erp -p 8080:8080 \
  -e DB_HOST=172.17.0.1 \
  -e DB_PORT=3306 \
  -e DB_DATABASE=erp \
  -e DB_USERNAME=erp \
  -e DB_PASSWORD='你的密码' \
  -e AUTO_INIT_SCHEMA=1 \
  -v h5erp-data:/data \
  h5erp
```

- `172.17.0.1` 是 docker0 网桥地址，用于访问**宿主机上的 MySQL**；MySQL 在别的机器就填那台的 IP
- macOS / Windows 用 `host.docker.internal`
- 上传文件、数据库备份都在 `h5erp-data` 卷（容器内 `/data`）

#### 数据库参数怎么填

方式 2 连的是**你自己的 MySQL**，必须显式给出连接信息。最少 5 个：

| 变量 | 示例 | 说明 |
|---|---|---|
| `DB_HOST` | `10.0.0.5` / `mysql.example.com` | 数据库地址；在宿主机上就写 `172.17.0.1`（macOS/Windows 用 `host.docker.internal`） |
| `DB_PORT` | `3306` | 非默认端口要改 |
| `DB_DATABASE` | `erp` | 库要提前建好 |
| `DB_USERNAME` | `erp` | 账号要能从容器所在机器连进来 |
| `DB_PASSWORD` | `你的密码` | 有 `@ : / #` 也没关系，走单变量不需要转义 |

再加一个开关：

| 变量 | 取值 | 说明 |
|---|---|---|
| `AUTO_INIT_SCHEMA` | `1` | 空库：首次启动自动导入 `erp.sql` |
| | `0` | 库里有数据：完全不碰现有表（**生产建议 0**） |

两种给法，任选一种。

**A. 直接写在 `docker run` 上**

```bash
docker run -d --name h5erp -p 8080:8080 \
  -e DB_HOST=10.0.0.5 \
  -e DB_PORT=3306 \
  -e DB_DATABASE=erp \
  -e DB_USERNAME=erp \
  -e DB_PASSWORD='你的密码' \
  -e AUTO_INIT_SCHEMA=0 \
  -v h5erp-data:/data \
  h5erp
```

**B. 用 `.env` 文件（推荐，改配置不用改命令）**

在项目根目录建 `.env`：

```env
DB_HOST=10.0.0.5
DB_PORT=3306
DB_DATABASE=erp
DB_USERNAME=erp
DB_PASSWORD=你的密码
AUTO_INIT_SCHEMA=0
```

启动时带上：

```bash
docker run -d --name h5erp -p 8080:8080 \
  --env-file .env \
  -v h5erp-data:/data \
  h5erp
```

改完 `.env` 要让配置生效，需要重建容器（镜像不用重新 build）：

```bash
docker rm -f h5erp && docker run -d --name h5erp -p 8080:8080 --env-file .env -v h5erp-data:/data h5erp
```

> 数据库账号需要 `CREATE / ALTER / INSERT / UPDATE / DELETE / INDEX` 权限（首次建表用），并且允许应用所在机器访问（安全组 / `user@'%'`）。

---

## 二、云端部署

### 方式 1：blitz.cloud（从 GitHub 直接构建）

1. 把仓库推到 GitHub（私有仓库也可以）
2. blitz 控制台 → **Host something new** → **My own code** → 选仓库、分支 `main`
3. **Advanced settings**：
   - Dockerfile：用仓库根目录这个
   - Size：至少 Small，建议 Medium
   - **数据库用自备的，不要开 “Needs a database”**
4. 在 **Environment** 里填 `DB_HOST / DB_PORT / DB_DATABASE / DB_USERNAME / DB_PASSWORD`
5. Build it and put it online

详细步骤见 **[DEPLOY-blitz.md](DEPLOY-blitz.md)**。

### 方式 2：自有云服务器 + Docker（带域名和 HTTPS）

```bash
# 1) 环境变量
cat > .env <<'ENV'
DOMAIN=erp.example.com
DB_HOST=10.0.0.5
DB_PORT=3306
DB_DATABASE=erp
DB_USERNAME=erp
DB_PASSWORD=你的密码
AUTO_INIT_SCHEMA=0
ENV

# 2) 证书（certbot 或你自己的）
mkdir -p certs
cp /etc/letsencrypt/live/erp.example.com/fullchain.pem certs/
cp /etc/letsencrypt/live/erp.example.com/privkey.pem   certs/

# 3) 启动：app + nginx
docker compose -f docker-compose.prod.yml up -d --build
```

- `app` 容器内监听 8080，`nginx` 负责 80→443 跳转、TLS 和反代
- Nginx 会带 `X-Forwarded-Proto`，应用自动用 https 生成静态资源地址，不会混合内容
- 上传上限 64MB（Nginx 与 php.ini 一致）

---

## 三、数据库（自备）

### 1. 建库建用户

```sql
CREATE DATABASE erp DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;

CREATE USER 'erp'@'%' IDENTIFIED BY '你的强密码';
GRANT ALL PRIVILEGES ON erp.* TO 'erp'@'%';
FLUSH PRIVILEGES;
```

- 用户主机要允许应用所在机器访问（云上通常是 `'%'`，或加安全组白名单）
- 账号需要有 `CREATE / ALTER / INSERT / UPDATE / DELETE / INDEX` 权限（首次建表用）

### 2. 表结构

| 场景 | 设置 |
|---|---|
| **空库** | `AUTO_INIT_SCHEMA=1`：首次启动自动导入 `erp.sql`（25 张表 + `admin/admin888` + 菜单/单据模板） |
| **已有数据的老库** | `AUTO_INIT_SCHEMA=0`：完全不碰现有表 |

`erp.sql` 只含表结构、菜单、单据类型和管理员，**不含业务资料**（商品分类、单位、仓库、账户、客户、商品需要自己建）。

### 3. 版本与兼容

- MySQL 5.7+ / 8.0、MariaDB 10.4+ 均可，**不支持 PostgreSQL**
- 老代码的 `GROUP BY` 写法不符合 `ONLY_FULL_GROUP_BY`，驱动会在每次连接时按会话关闭，**不需要改服务器配置**
- 连接字符集 `utf8`，与建表语句一致

---

## 四、环境变量

连接参数**自动识别**，下面这些名字都认，手填的优先于连接串：

| 字段 | 变量名（从左到右优先） |
|---|---|
| 连接串 | `DATABASE_URL`、`MYSQL_URL`、`DB_URL` |
| 主机 | `DB_HOST`、`DB_HOSTNAME`、`MYSQL_HOST` |
| 端口 | `DB_PORT`、`MYSQL_PORT` |
| 库名 | `DB_DATABASE`、`DB_NAME`、`MYSQL_DATABASE` |
| 用户 | `DB_USERNAME`、`DB_USER`、`MYSQL_USER` |
| 密码 | `DB_PASSWORD`、`DB_PASS`、`MYSQL_PASSWORD` |

其他开关：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUTO_INIT_SCHEMA` | `1` | `0` = 不自动建表（库里有数据时用） |
| `DB_DEBUG` | `1` | `0` = 页面不显示 SQL 错误（正式环境建议 0） |
| `WAIT_DB_SECONDS` | `120` | 启动时等数据库就绪的秒数 |
| `DB_INIT_STRICT` | `0` | `1` = 数据库连不上就让容器退出 |
| `TZ` | `Asia/Shanghai` | 时区 |

参考模板：**[.env.example](.env.example)**

---

## 五、首次使用

1. 浏览器打开服务地址，用 `admin / admin888` 登录，**立即修改密码**
2. 按顺序建基础资料（否则开单会提示库存不足 / 选不到东西）：

```
商品分类 → 计量单位 → 仓库（状态正常）→ 结算账户 → 客户/供应商 → 商品
```

3. 采购入库 → 审核 → 库存增加 → 销货出库 → 审核 → 打印 PDF → 报表

---

## 六、升级与备份

### 升级到新版本

**方式 1（compose，库在容器里）**

```bash
cd erp
git pull
docker compose -f docker-compose.local.yml up -d --build
```

**方式 2（自有 MySQL）**

```bash
cd erp
git pull
docker build -t h5erp .
docker rm -f h5erp
docker run -d --name h5erp -p 8080:8080 \
  --env-file .env \
  -v h5erp-data:/data \
  h5erp
```

- 方式 2 的数据库在你自己那边，升级只换应用，**库不受影响**
- 两种方式的上传文件和备份都在 `h5erp-data` 卷，重建容器不会丢
- 回滚：`git checkout <上一个提交>`，再按对应方式重新构建/启动

### 升级前先备份

系统内：**设置 → 备份与恢复 → 备份**，文件落在 `/data/backup`，可以「下载」取回。

命令行：

```bash
# 方式 1：库在 compose 里
docker exec h5erp-db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' \
  > backup_$(date +%F_%H%M).sql

# 方式 2：库是你自己的
mysqldump -h 10.0.0.5 -P 3306 -u erp -p erp > backup_$(date +%F_%H%M).sql
```

### 表结构会跟着升级吗

**不会自动改。** `erp.sql` 只在**空库首次初始化**时导入；升级只替换代码，不动已有表结构。

如果新版本带了字段变更，按发布说明手工执行 `ALTER TABLE`（或导出数据 → 重建库 → 导回）。升级前先看发布说明里有没有「数据库变更」一节。

### 修改数据库密码

**方式 1**：密码在 MySQL 容器里，改 `.env` 不会同步：

```bash
docker exec -it h5erp-db mysql -uroot -p
# 输入当前密码后：
ALTER USER 'root'@'%' IDENTIFIED BY '新密码';
FLUSH PRIVILEGES;
```

然后把 `.env` 的 `DB_PASSWORD` 改成同一个值，再 `docker compose -f docker-compose.local.yml up -d`。

**方式 2**：在**你自己的 MySQL** 上改密码，然后更新 `.env` 里的 `DB_PASSWORD`，重建容器：

```bash
docker rm -f h5erp && docker run -d --name h5erp -p 8080:8080 --env-file .env -v h5erp-data:/data h5erp
```

### 彻底重来（仅方式 1，会清空数据）

```bash
docker compose -f docker-compose.local.yml down -v   # -v 删除数据卷
docker compose -f docker-compose.local.yml up -d --build
```

---

## 七、目录结构

```
erp/
├── Dockerfile                  # PHP 8.2 + Apache，站点根 = pc/
├── docker-compose.local.yml    # 本地：应用 + MySQL 8
├── docker-compose.prod.yml     # 生产：应用 + Nginx（TLS）
├── deploy/                     # 启动脚本、Nginx 模板、.htaccess
├── pc/                         # CodeIgniter 应用（升级到 PHP 8.2）
├── erp.sql                     # 表结构 + 初始数据（25 张表）
├── docs/                       # API 接口文档、PHP 8 升级说明
├── DEPLOY-blitz.md             # blitz.cloud 部署步骤
└── DOCKER.md                   # Docker 运行说明
```

---

## 八、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 容器起来但页面 502 / 白屏 | 看日志 `docker logs h5erp`，多半是数据库连不上：核对 `DB_HOST`、端口、账号、安全组 |
| 登录提示「账号或密码错误」 | `ci_admin.userpwd` 必须是 32 位 md5；`pbkdf2_sha256$...` 是别的系统写的，本系统不认 |
| 报表 500 / `Incorrect DATE value: ''` | 已修（`mysql_model::query` 会过滤空日期），确认镜像是最新代码 |
| 打印 500 | 已修（`postData` 为空时回退到明细表），确认镜像是最新代码 |
| 页面能开但点不动 | `pc/index.php` 的 `ENVIRONMENT` 必须是 `production`（本仓库已固定），开发模式的提示会污染 AJAX 返回 |
| 中文乱码 | 确认库/表字符集是 `utf8` 或 `utf8mb4`，连接串不要指定 latin1 |
| 免费云平台应用休眠 | 一段时间无访问会休眠，首次访问唤醒需要十几秒到一分钟，属正常 |

---

## 九、相关文档

- **[DEPLOY-blitz.md](DEPLOY-blitz.md)** — blitz.cloud 部署（GitHub 直连、环境变量、日志排查）
- **[DOCKER.md](DOCKER.md)** — 本地 Docker 运行、compose 说明
- **[docs/API-接口文档.md](docs/API-接口文档.md)** — 43 个控制器 / 355 个接口说明
- **[docs/PHP8-升级说明.md](docs/PHP8-升级说明.md)** — 从 PHP 5.6 升级到 8.2 的改动清单

---

## 说明

- 本项目基于 CodeIgniter 2.2.5 改造，PHP 8.2 下已适配并验证：登录、基础资料、采购/销售/调拨/收付款/其他出入库/成本调整、审核、PDF 打印、Excel 导入导出、51 个报表、数据库备份与恢复。
- 数据库请自行备份；容器内 `/data` 只保存上传文件和备份文件，删除容器不会删除该卷。

# 在 blitz.cloud 上部署 H5ERP

这个目录本身就是 blitz 要的仓库根：`Dockerfile` 在最外层，`pc/` 是应用，`erp.sql` 是表结构。
**不需要 docker-compose**，blitz 一个容器跑应用，数据库用平台托管的 MariaDB（外部库）。

---

## 0. 先搞清楚两件事

1. **端口**：blitz 通过 `PORT` 环境变量告诉应用监听端口（默认 8080）。镜像里 Apache 已按 8080 配置，启动脚本会按 `PORT` 再改一次，两个都兼容。
2. **数据库只能从容器里连**：blitz 的托管数据库没有公网地址、没有开放端口，你本机连不上，也没法从本机导入 SQL。
   所以镜像带了一个启动脚本：**首次启动发现库是空的，就自动导入 `erp.sql`**；库里已有 `ci_admin` 表则跳过，绝不动现有数据。

---

## 1. 推到 GitHub（私有仓库可以）

```bash
cd <这个目录>
git init
git add -A
git commit -m "H5ERP PC 端 PHP 8.2，适配 blitz.cloud"
git branch -M main
git remote add origin git@github.com:<你的账号>/h5erp.git
git push -u origin main
```

不要提交 `*.zip`（`.dockerignore` / `.gitignore` 已排除）。

---

## 2. 在 blitz.cloud 建应用

1. 打开 <https://dashboard.blitz.cloud> → **Host something new**
2. 选 **My own code** → **Connect GitHub** → 选中刚才的仓库 → 分支 `main`
3. 应用名就是子域名，例如 `erp` → `erp.<你的名字>.prod.page`
4. 点 **Advanced settings**，确认三件事：
   - **Dockerfile**：用仓库根目录的这个（不要让它自动生成）
   - **Needs a database**：**打开**，引擎选 **MariaDB 11.4**
     （打开后平台才会注入 `DATABASE_URL`；不打开应用连不上库）
   - **Size**：至少 **Small**（128 MB）；建议 **Medium**（256 MB），PDF 打印和批量导出更稳
5. **Build it and put it online**

构建日志里如果看到 `apt-get`、`docker-php-ext-install` 就是在装 PHP 扩展，第一次要几分钟。

---

## 3. 首次启动会发生什么（日志里能看到）

应用启动时依次做：

1. 自动识别数据库连接变量（`DATABASE_URL` / `DB_*` / `MYSQL_*`，见第 4 节）
2. 等数据库能连上（最多 `WAIT_DB_SECONDS`，默认 120 秒；免费套餐休眠唤醒时会慢一点）
3. 库里没有 `ci_admin` 表 → 导入 `erp.sql`（25 张表 + admin 账号 + 菜单/单据模板）
4. 启动 Apache，监听 `PORT`（8080）

日志应当是：

```
[db-init] 连接参数 host=… db=… user=… 密码=已设置
[db-init] 变量来源 host←DB_HOST port←默认值 db←DB_DATABASE user←DB_USERNAME pass←DB_PASSWORD
[db-init] 空库，导入 erp.sql（276 条语句）
[db-init] 导入完成：25 张表，管理员账号 admin 已就绪
```

然后访问 `https://<app>.<你的名字>.prod.page`，账号 **admin / admin888**。
**登录后立刻改密码**（系统设置 → 用户管理）。

---

## 3.5 首次登录后先建基础资料（5 分钟，否则开不了单）

`erp.sql` 只带表结构、菜单和单据模板，不带业务资料。按这个顺序建一遍，之后所有单据才可用：

| 顺序 | 页面 | 建什么 |
|---|---|---|
| 1 | 基础资料 → 商品分类 | 至少一个分类（如「默认分类」） |
| 2 | 基础资料 → 计量单位 | 至少一个单位（如「个」） |
| 3 | 基础资料 → 仓库 | 至少一个仓库（**状态必须是正常/未锁定**，否则开单选不到） |
| 4 | 基础资料 → 结算账户 | 至少一个账户（如「现金」） |
| 5 | 基础资料 → 客户 / 供应商 | 开销售单、采购单前各建一个 |
| 6 | 基础资料 → 商品 | 建商品时要选分类和单位 |

做完这些，采购入库 → 审核 → 库存 → 打印 PDF → 报表 这条链路就通了（这条链路已实测过）。

---

## 4. 环境变量（在应用页的 Environment 标签）

连接参数是**自动识别**的。平台能扫到、会列出来让你填的只有 **5 个**：
`DB_HOST` / `DB_PORT` / `DB_DATABASE` / `DB_USERNAME` / `DB_PASSWORD`。
下面这些别名也都认，但不会出现在平台的待填列表里，想用直接加就行。

| 字段 | 认得的变量名（从左到右优先） |
|---|---|
| 连接串 | `DATABASE_URL`、`MYSQL_URL`、`DB_URL`、`CLEARDB_DATABASE_URL`、`JAWSDB_URL`、`DATABASE_URI` |
| 主机 | `DB_HOST`、`DB_HOSTNAME`、`DATABASE_HOST`、`MYSQL_HOST`、`MYSQL_HOSTNAME`、`MYSQL_SERVER` |
| 端口 | `DB_PORT`、`DATABASE_PORT`、`MYSQL_PORT` |
| 库名 | `DB_DATABASE`、`DB_NAME`、`DB_DB`、`DATABASE_NAME`、`MYSQL_DATABASE`、`MYSQL_DB` |
| 用户 | `DB_USERNAME`、`DB_USER`、`DATABASE_USER`、`MYSQL_USER`、`MYSQL_USERNAME` |
| 密码 | `DB_PASSWORD`、`DB_PASS`、`DB_PWD`、`DATABASE_PASSWORD`、`MYSQL_PASSWORD`、`MYSQL_PASS`、`MYSQL_ROOT_PASSWORD` |

这 5 个在 `pc/application/config/db_env.php` 里是显式 `getenv('DB_HOST')` 写死的（不是动态循环），平台构建时扫得到；别名走动态兜底，所以不会把列表撑长。仓库根的 `.env.example` 是同一份清单。

优先级：**手填的单变量 > 连接串 > 默认值**（`localhost` / `3306` / `erp` / `root`）。
单变量只填一部分也行，没填的字段才用连接串或默认值。

其他可选变量（平台不会提示，需要时手动加）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUTO_INIT_SCHEMA` | `1` | `0` = 不自动导入表结构（库由你自己导好时用） |
| `WAIT_DB_SECONDS` | `120` | 等数据库就绪的秒数 |
| `DB_INIT_STRICT` | `0` | `1` = 数据库连不上就让容器退出；默认继续启动，页面会显示数据库错误，方便排查 |
| `DB_DEBUG` | `1` | `0` = 不把 SQL 错误显示到页面（正式对外时建议 0） |
| `TZ` | `Asia/Shanghai` | 时区 |

启动时日志会把识别结果打出来（**不打印密码**），可以直接核对：

```
[db-init] 连接参数 host=1.2.3.4:3306 db=erp user=erp_user 密码=已设置
[db-init] 变量来源 host←DB_HOST port←默认值 db←DB_DATABASE user←DB_USERNAME pass←DB_PASSWORD
[db-init] 环境里可见的数据库相关变量：DB_DATABASE, DB_HOST, DB_PASSWORD, DB_USERNAME
```

如果连接串和手填变量同时存在，会多一行冲突提示，并以手填的值为准。

改完环境变量要**重启应用**才生效。

---

## 5. 接你自己的 MySQL / MariaDB

Environment 里只填这 5 个就够（名字按上一节，`DB_*` 或 `MYSQL_*` 都行）：

```
DB_HOST=你的地址
DB_PORT=3306
DB_DATABASE=库名
DB_USERNAME=用户
DB_PASSWORD=密码
AUTO_INIT_SCHEMA=0
```

- **不用**再写 `DATABASE_URL`；万一平台也注入了一个，手填的这套优先，日志里会提示冲突
- `AUTO_INIT_SCHEMA=0` 是防止自动导入动到你的生产库；表结构自己用 `erp.sql` 导好
- 库是空的又不想手动导：留默认 `1`，脚本只在没有 `ci_admin` 表时才导入
- 密码里带 `@ : / #` 都行，**别**塞进 `DATABASE_URL`（URL 里要转义）

> 数据库必须是 MySQL 5.7+/8 或 MariaDB 10.4+，**不能用 PostgreSQL**。

---

## 6. 文件与备份

- 上传的商品图片、附件写在 `/data`（镜像里声明了 `VOLUME`，blitz 会持久保留，预留 1 GB）。
  容器重启不会丢，但**免费套餐不做夜间备份**；重要文件用应用页的 **Files** 下载一份。
- 数据库每晚自动备份（免费套餐保留 7 天）。
- 免费套餐应用 **30 分钟无人访问会休眠**，下次访问自动唤醒，第一次会慢 10～60 秒，属正常现象。

---

## 7. 出问题先看哪里

| 现象 | 原因 / 处理 |
|---|---|
| 一直转圈、502 / 打开报数据库错误 | 看 **Logs** 开头两行：`[entrypoint] 容器里可见的环境变量名` 里有没有 `DB_HOST`；再看 `[db-init] 变量来源`，全是「默认值」就说明变量没进来（没保存、没重启，或加到了别的应用上） |
| 打开是目录列表 / 404 | Dockerfile 不在仓库根目录；确认仓库首页就能看到 `Dockerfile` |
| 500 错误 | Logs 里的 PHP 错误。设 `DB_DEBUG=1` 可把 SQL 错误显示到页面 |
| 页面能开但点不动 | 确认 `index.php` 里 `ENVIRONMENT` 是 `production`（本包已固定），dev 模式的提示会污染 AJAX 返回 |
| `1045 Access denied for user ...@<IP>` | 库那边拒绝认证：账号/密码不对，或限制了来源 IP（要把日志里的那个 IP 加白名单）。`1049` 是库名不存在 |
| 报表打不开 | MySQL 8 的 `ONLY_FULL_GROUP_BY` 问题，驱动已在连接时按会话关掉；MariaDB 本身没有这个限制 |
| 中文乱码 | `erp.sql` 建表是 `utf8`，连接也是 `utf8`；若你自己建的库，确认库/表字符集不是 latin1 |
| 内存告警 | 把应用 Size 调到 Medium；镜像已把 Apache prefork 压到最小 |

---

## 8. 本地验证（可选，不用 blitz 也能跑）

```bash
# 用外部库（推荐，和线上一致）
docker build -t h5erp .
docker run -p 8080:8080 \
  -e DB_HOST=host.docker.internal -e DB_DATABASE=erp \
  -e DB_USERNAME=root -e DB_PASSWORD=pass \
  h5erp

# 或者一键起应用 + MySQL 8（仅本地调试用）
docker compose up -d
```

访问 <http://localhost:8080>，admin / admin888。

---

## 9. 和 docker-compose 的区别

`docker-compose.yml` 是给自有服务器/本地用的（应用 + MySQL 两个容器）。

blitz 会读标准命名的 compose 文件，可能把 `db` 服务列成「数据库，已忽略」——这是正常的，
构建仍然只用根目录的 `Dockerfile`。如果向导让你选「哪个是应用」，选 `app` 那个即可。
线上形态：应用一个容器 + 你的 MySQL（或平台托管 MariaDB）。
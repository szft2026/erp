# scripts

## verify_prod.py — 线上验收（只读）

部署后跑一遍，确认新镜像和核心功能都正常。

```bash
python3 scripts/verify_prod.py
BASE=https://erp.prod.page ERP_USER=admin ERP_PWD=****** python3 scripts/verify_prod.py
```

检查项（全部只读）：

1. 登录
2. `scm/invSa/invSaleList` 返回真实数据（不是「尚未授权」文案）
3. `scm/invSa/log` 不再 500
4. `scm/pdImport/index` 不再 500
5. 客户列表
6. 销售单列表
7. 销售单打印 PDF
8. `basedata/contact/update` 缺 id 返回 JSON 而不是 500

退出码：0 全通过，2 有失败。

> **不要**用 `?act=del` 去验证后门是否还在——旧版本上那一条请求就是后门本身，
> 会删掉 `application/models/mysql_model.php` 让全站 500。用上面第 2–4 项判断版本即可
> （它们和后门删除在同一个提交里）。

## 本地冒烟（可选）

本地全量冒烟需要：PHP 8.2 CLI（mysqli/iconv/gd）、可连的 MySQL、以及 357 个接口清单。
脚本在开发环境生成，未随仓库发布；需要时可按 `docs/API-接口文档.md` 第三节的方法逐个调用。

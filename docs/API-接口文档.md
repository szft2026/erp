# H5ERP 接口文档（PC 端）

> 版本：PHP 8 升级版　|　框架：CodeIgniter 2.2.5（已适配 PHP 8.2）　|　数据库：MySQL 8

共 **44 个控制器、373 个公开接口**。本轮实测覆盖：全量冒烟 354 个接口（0 个 5xx / DB 错误 / 致命错误）、
7 类单据打印、41 个写接口（空参数 / 全参数两轮）、12 步「单据 → 库存 → 应收应付」联动回归。
测试环境、逐条结果与复现命令见 `docs/测试报告.md`。私有方法与内部回调（`validform`、`my_filter` 等）不计入。

## 一、通用约定

| 项 | 说明 |
| --- | --- |
| 基地址 | `http(s)://<域名>/index.php/` |
| 路由格式 | `/index.php/<目录>/<控制器>/<方法>`，根目录控制器无「目录」段 |
| 认证 | 先 `POST login` 登录，服务端写 `ci_session` Cookie；后续请求携带该 Cookie |
| CSRF | 登录接口需带 `token`，值取自登录页下发的 `token` Cookie |
| 请求体 | 默认 `application/x-www-form-urlencoded`；单据类接口（`scm/*`）把整张单据塞进单字段 `postData`（JSON 字符串）；批量审核/删除用普通表单 `id` |
| 响应 | 成功：`{"status":200,"msg":"success","data":{...}}`；失败：`{"status":-1,"msg":"<中文原因>","data":[]}`，**HTTP 状态码仍是 200**，必须看 `status` 字段 |
| 例外 | `login` 成功返回纯文本 `1`；`toPdf` 返回 `application/pdf`；`exporter` 返回 XLS |
| 参数位置 | **部分参数只认 URL query**：`basedata/contact/index` 的 `type`、`basedata/assist/index` 的 `typeNumber`、`scm/invOi/index` 与 `scm/ori/index` 的 `action`、`scm/invPu|invSa|invTf/toPdf` 的 `id` 等，源码用的是 `input->get()`。放进 POST body 读不到，会走默认分支（典型现象：客户下拉返回供应商、类别列表为空） |
| 编码 | UTF-8，时间均为北京时间（UTC+8） |

## 二、核心业务流程（全部实测）

### 2.1 新增商品

```
POST /index.php/basedata/inventory/add?action=add
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| number | 是 | 商品编号（同库唯一） |
| name | 是 | 商品名称 |
| categoryId | 是 | 商品类别 id（`ci_category` 必须存在） |
| baseUnitId | 是 | 基本单位 id（`ci_unit` 必须存在） |
| spec / barCode / remark | 否 | 规格 / 条码 / 备注 |
| purPrice / salePrice / wholesalePrice / vipPrice | 否 | 采购价 / 零售价 / 批发价 / 会员价 |
| discountRate1 / discountRate2 | 否 | 折扣率 |
| lowQty / highQty | 否 | 库存下限 / 上限 |
| propertys / sonGoods | 否 | 属性 / 组合商品 JSON，默认 `[]` |

实测：`{"status":200,"msg":"success","data":{"id":4}}`

### 2.2 新增客户 / 供应商

```
POST /index.php/basedata/contact/add?action=add&type=10    ← 客户
POST /index.php/basedata/contact/add?action=add&type=-10   ← 供应商
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| name | 是 | 名称（同类型内不可重名） |
| number | 是 | 编号（同类型内不可重复） |
| cCategory | 是 | 类别 id，**必须真实存在**，否则报「类别不存在」 |
| type | 是 | **query 参数**：`10` = 客户，`-10` = 供应商 |
| cLevel / taxRate / periodMoney / amount | 否 | 等级 / 税率 / 期初应付 / 期初余额 |
| linkMans | 否 | 联系人 JSON，默认 `[]` |
| beginDate | 否 | 默认当天 |

实测：客户 `id=11`（type=10）、供应商 `id=12`（type=-10）；导出、数据权限、最近往来均按此语义校验通过。

> 注意：`ci_contact.type` 的建表注释写的是「-10 客户 10 供应商」，与前端（`customerList.js`、`customerCombo`）和全部实测结果相反，
> **以 `10=客户、-10=供应商` 为准**，注释是历史遗留。

### 2.3 采购入库单

```
POST /index.php/scm/invPu/add
表单只有一个字段 postData，值为 JSON 字符串
```

JSON 必填：`billNo`、`transType`(150501)、`date`、`buId`(供应商 id)、`amount`、`arrears`、`totalQty`、`totalAmount`、`entries[]`

`entries[]` 每项：`invId`、`qty`、`price`、`amount`、`locationId`（必须是 `ci_storage` 中 `disable=0` 的仓库）、`unitId`

实测：`id=127`，明细 `ci_invoice_info.qty=+10`，应付 +1000。

### 2.4 单据审核 / 反审核

```
POST /index.php/scm/invPu/batchCheckInvPu     表单 id=127     ← 推荐，最省事
POST /index.php/scm/invPu/checkInvPu          postData 完整单据 ← 必须带 id 和全部明细
POST /index.php/scm/invPu/rsBatchCheckInvPu   表单 id=127     ← 反审核
```

- 只传 `id` 调 `checkInvPu` 会报「提交的数据不能为空」
- 重复审核报「…的单据已被审核」
- **审核不改变库存和应收**（保存时已经记账），只改 `checked` 标记

### 2.5 销售出库单

```
POST /index.php/scm/invSa/add
```

JSON 必填：`billType`("SALE")、`transType`(150601)、`billDate`、`buId`(客户 id)、`amount`、`arrears`、`totalQty`、`totalAmount`、`entries[]`

- 明细 `qty` 传正数，入库写 `+qty`、出库写 `-qty`（由 transType 决定，不用自己加负号）
- 库存不足直接拒绝：`{"status":-1,"msg":"商品库存不足！"}`

实测：`id=128`，库存 -3，应收 +360。

### 2.6 打印单据（PDF）

| 单据 | 接口 | 实测 |
| --- | --- | --- |
| 采购 | `GET /scm/invPu/toPdf?id=116` | 26315 B |
| 销售 | `GET /scm/invSa/toPdf?id=124` | 28642 B |
| 调拨 | `GET /scm/invTf/toPdf?id=117` | 4266 B |
| 收款 | `GET /scm/receipt/toPdf?id=118` | 6412 B |
| 付款 | `GET /scm/payment/toPdf?id=119` | 6410 B |
| 其他入库 | `GET /scm/invOi/toOiPdf?id=120` | 5461 B |
| 其他出库 | `GET /scm/invOi/toOoPdf?id=121` | 5478 B |

全部返回 `application/pdf`，`pdftotext` 可正常提取抬头、往来单位、日期、商品行。`entrysPerNote` 不传按 53 条/页分页。

### 2.7 查询单据

```
POST /index.php/scm/invPu/purList   必传 transType=150501
POST /index.php/scm/invSa/saleList  必传 transType=150601
```

**不传 `transType` 返回空列表**（不报错）——最容易踩的坑。

### 2.8 调拨单

```
POST /index.php/scm/invTf/add
```

JSON 必填：`billType`("TRANSFER")、`transType`(103091)、`billDate`、`totalQty`、`entries[]`

`entries[]` 每项：`invId`、`qty`、`price`、`outLocationId`、`inLocationId`、`unitId`

- 调出/调入仓库必须存在且不能相同
- 调出仓库库存不足报「XX库存不足」

实测：`id=136`，仓 8 -1、仓 9 +1；删除后两个仓库同时回滚。

### 2.9 收款单

```
POST /index.php/scm/receipt/add
```

JSON 必填：`buId`、`billDate`、`accounts[]`（每项 `payment`）

- `billNo` 自动生成（`SKD` 前缀），传了也会被覆盖
- `entries` 可为空数组；`arrears` 传负数（如 `-200`）
- 保存即冲减应收，不需要审核

实测：`id=130`，应收 -200；删除后 +200。

### 2.10 付款单

同收款单，接口 `/index.php/scm/payment/add`，`billNo` 前缀 `FKD`，冲减应付。

### 2.11 其他收入 / 其他支出

```
POST /index.php/scm/ori/addInc   → 其他收入（transType 153401）
POST /index.php/scm/ori/addExp   → 其他支出（transType 153402）
```

必填：`billDate`、`buId`、`accId`、`totalAmount`、`entries[]`（至少 1 条）。

### 2.12 库存与应收应付怎么算（实测结论）

| 指标 | 计算方式 |
| --- | --- |
| 库存 | `SUM(ci_invoice_info.qty) WHERE isDelete=0`（按 `invId + locationId` 汇总，**不区分是否审核**） |
| 应收 | `SUM(ci_invoice.arrears) WHERE buId=客户 AND isDelete=0`（销售单正数、收款单负数） |
| 应付 | 同上，`buId=供应商`（采购单正数、付款单负数） |

实测 12 步联动（商品 7、仓 8）：

| 操作 | Δ库存 | Δ应收 | Δ应付 |
| --- | --- | --- | --- |
| 采购单保存 10 个 | +10 | 0 | +1000 |
| 采购单审核 / 反审核 | 0 | 0 | 0 |
| 销售单保存 3 个 | -3 | +360 | 0 |
| 销售单审核 / 反审核 | 0 | 0 | 0 |
| 删除销售单 | +3 | -360 | 0 |
| 删除采购单 | -10 | 0 | -1000 |
| 其他入库 +4 / 删除 | +4 / -4 | 0 | 0 |
| 其他出库 -2 / 删除 | -2 / +2 | 0 | 0 |
| 调拨 8→9 一个 / 删除 | 仓8 -1 仓9 +1 / 反向 | 0 | 0 |
| 收款单 200 / 删除 | 0 | -200 / +200 | 0 |

规则：
1. **保存即记账**，审核只打标记；所以单据一保存库存就动，不要等审核。
2. **删除是唯一回滚手段**：删除会把 `ci_invoice` 与 `ci_invoice_info` 同时置 `isDelete=1`，库存与往来随之回滚。
3. **已审核单据必须先反审核再删**，否则报「已审核的不可删除」。
4. 删除接口统一接受 GET 或 POST 的 `id`（本轮修复，之前部分接口只认 GET）。

## 三、接口清单

**说明**：`scm/invPo`（采购订单）原发布包缺失，已按 `invSo` 补齐并通过端到端测试。
`noteprinttemp/index`、`prints/index`、`service/recover`、`basedata/warranty/index` 是原产品遗留的空方法，
调用返回 0 字节，属未实现功能而非升级缺陷；`basedata/import/findDataImporter`、`basedata/contact/my_filter`、
`scm/backup/create_folders`、`scm/invSa/log` 为内部函数/死代码。

**必填** 由源码校验函数自动提取（`strlen()<1`、`intval()<1`、`count()<1`、`!$x`），并已用「空参数 / 全参数」两轮实测核对（41 个写接口，见附录 A）。「选填」不代表业务上无意义——例如类别/仓库是否存在、库存是否足够，仍会在保存时报错。

### dataright.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `ar` | POST | — | rightid, userName |  |
| `dt` | POST | — | userName |  |
| `update` | POST | — | rights, type, userName |  |
| `query` | POST | — | data, msg, skey, status, type, userName |  |

### home.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | name, rights, roleid, system, uid, username |  |
| `main` | GET | — | — |  |
| `set_password` | POST | — | buyerMobile, buyerName, newPassword |  |
| `set_password2` | POST | — | password, userId |  |
| `Services` | GET | — | — |  |

### import.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |

### inventory.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |

### login.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | ispwd, jxcsys, username, userpwd |  |
| `out` | GET | — | — |  |
| `code` | GET | — | — |  |

### noteprinttemp.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |

### prints.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `print_settings_voucher` | GET | — | — |  |

### report.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | data, msg, status, totalsize |  |
| `pu_detail_new` | POST | — | beginDate, endDate |  |
| `puDetail_detail` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, rows, status, storageNo |  |
| `puDetail_detailExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, list, storageNo |  |
| `pu_summary_new` | POST | — | beginDate, endDate |  |
| `puDetail_inv` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, rows, status, storageNo |  |
| `puDetail_invExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, list, storageNo |  |
| `pu_summary_supply_new` | POST | — | beginDate, endDate |  |
| `puDetail_supply` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, rows, status, storageNo |  |
| `puDetail_supplyExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, list, storageNo |  |
| `sales_detail` | GET | — | — |  |
| `salesDetail_detail` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, profit, rows, salesId, status, storageNo |  |
| `salesDetail_detailExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, list, salesId, storageNo |  |
| `sales_summary` | GET | — | — |  |
| `sales_profit` | GET | — | — |  |
| `salesDetail_inv` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, profit, rows, salesId, status, storageNo |  |
| `salesDetail_invExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, info, list, profit, salesId, storageNo |  |
| `salesProfit_inv` | POST | — | beginDate, customerNo, data, endDate, msg, page, rows, salesId, salesNo, status |  |
| `salesProfit_invExporter` | POST | — | beginDate, customerNo, endDate, info, list, salesId, salesNo |  |
| `sales_summary_customer_new` | GET | — | — |  |
| `salesDetail_customer` | POST | — | beginDate, customerNo, data, endDate, goodsNo, msg, page, profit, rows, salesId, status, storageNo |  |
| `salesDetail_customerExporter` | POST | — | beginDate, customerNo, endDate, goodsNo, info, list, profit, salesId, storageNo |  |
| `contact_debt_new` | GET | — | — |  |
| `contactDebt_detail` | POST | — | customer, data, matchCon, msg, page, rows, status, supplier |  |
| `contactDebt_exporter` | GET | — | customer, list, matchCon, supplier |  |
| `goods_balance` | GET | — | — |  |
| `invBalance` | POST | — | catId, endDate, goodsNo, storageNo |  |
| `invBalance_exporter` | GET | — | beginDate, catId, endDate, goodsNo, list, profit, storage, storageNo |  |
| `goods_flow_detail` | GET | — | — |  |
| `deliverDetail` | POST | — | beginDate, data, endDate, goodsNo, msg, page, rows, status, storageNo |  |
| `deliverDetail_exporter` | GET | — | beginDate, endDate, goodsNo, list1, list2, storageNo |  |
| `goods_flow_summary` | GET | — | — |  |
| `deliverSummary` | POST | — | beginDate, endDate, goodsNo, page, rows, storageNo |  |
| `deliverSummary_exporter` | GET | — | beginDate, endDate, goodsNo, list, storageNo |  |
| `cash_bank_journal_new` | POST | — | accountNo, beginDate, endDate |  |
| `bankBalance_detail` | POST | — | accountNo, beginDate, endDate, page, rows |  |
| `bankBalance_exporter` | GET | — | accountNo, beginDate, endDate, list1, list2 |  |
| `account_pay_detail_new` | POST | — | accountNo, beginDate, endDate |  |
| `fundBalance_detailSupplier` | POST | — | accountNo, beginDate, endDate, page, rows, type |  |
| `fundBalance_exporterSupplier` | GET | — | accountNo, beginDate, endDate, list1, list2 |  |
| `account_proceeds_detail_new` | POST | — | accountNo, beginDate, endDate |  |
| `fundBalance_detail` | POST | — | accountNo, beginDate, data, endDate, msg, page, rows, status, type |  |
| `fundBalance_exporter` | GET | — | accountNo, beginDate, endDate, list1, list2 |  |
| `customers_reconciliation_new` | POST | — | beginDate, customerId, customerName, endDate |  |
| `customerBalance_detail` | POST | — | beginDate, customerId, customerName, data, endDate, msg, page, rows, showDetail, status |  |
| `customerBalance_exporter` | GET | — | beginDate, customerId, customerName, endDate, list1, list2, showDetail |  |
| `suppliers_reconciliation_new` | POST | — | beginDate, endDate, supplierId, supplierName |  |
| `supplierBalance_detail` | POST | — | beginDate, data, endDate, msg, page, rows, showDetail, status, supplierId, supplierName |  |
| `supplierBalance_exporter` | GET | — | beginDate, endDate, list1, list2, showDetail, supplierId, supplierName |  |
| `other_income_expense_detail` | POST | — | beginDate, endDate, supplierId |  |
| `oriDetail_detail` | POST | — | beginDate, data, endDate, msg, page, rows, status, transType, typeName |  |
| `oriDetail_export` | GET | — | beginDate, endDate, list, transType, typeName |  |

### right.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `isMaxShareUser` | GET | — | — |  |
| `queryAllUser` | GET | — | — |  |
| `queryUserByName` | POST | — | mobile, uid, userName, username |  |
| `adduser` | POST | — | password, userMobile, userName, userNumber |  |
| `addrights2Outuser` | POST | — | rightid, userName |  |
| `queryalluserright` | POST | — | lever, userName |  |
| `auth2UserCancel` | POST | — | userName |  |
| `auth2User` | POST | — | userName |  |

### sales.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `sales_search` | GET | — | — |  |

### service.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `recover` | GET | — | — |  |

### settings.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `Contract` | GET | — | — |  |
| `customer_list` | GET | — | — |  |
| `customer_manage` | GET | — | — |  |
| `vendor_list` | GET | — | — |  |
| `vendor_manage` | GET | — | — |  |
| `addressmanage` | GET | — | — |  |
| `goods_list` | GET | — | — |  |
| `storage_list` | GET | — | — |  |
| `storage_manage` | GET | — | — |  |
| `staff_list` | GET | — | — |  |
| `staff_manage` | GET | — | — |  |
| `shippingaddress` | GET | — | — |  |
| `shippingaddressmanage` | GET | — | — |  |
| `settlement_account` | GET | — | — |  |
| `settlementaccount_manager` | GET | — | — |  |
| `system_parameter` | GET | — | — |  |
| `unit_list` | GET | — | — |  |
| `unit_manage` | GET | — | — |  |
| `unitgroup_manage` | GET | — | — |  |
| `backup` | GET | — | — |  |
| `settlement_category_list` | GET | — | — |  |
| `settlement_category_manager` | GET | — | — |  |
| `category_list` | GET | — | typeNumber |  |
| `choose_account` | GET | — | — |  |
| `inventory_warning` | GET | — | — |  |
| `log` | GET | — | — |  |
| `authority` | GET | — | — |  |
| `authority_new` | GET | — | — |  |
| `authority_setting` | GET | — | — |  |
| `authority_setting_data` | GET | — | — |  |
| `goods_manage` | GET | — | — |  |
| `fileupload` | GET | — | — |  |
| `assistingprop` | GET | — | — |  |
| `prop_list` | GET | — | — |  |
| `propmanage` | GET | — | — |  |
| `import` | GET | — | — |  |
| `select_customer` | GET | — | — |  |
| `goods_batch` | GET | — | — |  |
| `addedServiceList` | GET | — | — |  |
| `assistingProp_batch` | GET | — | — |  |
| `assistingPropGroupManage` | GET | — | — |  |
| `storage_batch` | GET | — | — |  |
| `saler_batch` | GET | — | — |  |
| `customer_batch` | GET | — | — |  |
| `supplier_batch` | GET | — | — |  |
| `settlementAccount_batch` | GET | — | — |  |
| `print_templates` | GET | — | — |  |
| `print_templates_manage` | GET | — | — |  |

### storage.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `other_search` | GET | — | — |  |
| `inventory` | GET | — | — |  |
| `transfers_search` | GET | — | — |  |
| `import` | GET | — | — |  |

### basedata/assist.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | skey, typeNumber |  |
| `getAssistType` | GET | — | — |  |
| `add` | POST | name、typeNumber | id, parentId |  |
| `update` | POST | name、typeNumber | id, parentId |  |
| `delete` | POST | — | id, name, typeNumber |  |

### basedata/assistSku.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | page, rows, skuClassId |  |
| `add` | POST | — | skuAssistId, skuClassId, skuId, skuName |  |
| `delete` | POST | — | id, skuName |  |

### basedata/assistType.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `add` | POST | — | id, name, type |  |
| `update` | POST | — | id, name |  |
| `delete` | POST | — | id, name |  |

### basedata/contact.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | categoryId, page, rows, skey, type |  |
| `getNextNo` | POST | — | skey, type |  |
| `checkName` | POST | — | id, name |  |
| `my_filter` | GET | — | — |  |
| `getRecentlyContact` | POST | — | billType, id, linkMans, name, transType |  |
| `getLinkMen` | GET | — | buId, linkMans |  |
| `query` | POST | — | amount, beginDate, cCategory, cLevel, difMoney, id, linkMans, name, number, periodMoney, pinYin, remark |  |
| `add` | POST | name、number、cCategory | amount, beginDate, cCategoryName, cLevel, contact, difMoney, id, linkMans, periodMoney, pinYin, taxRate, type |  |
| `update` | POST | name、number、cCategory | amount, beginDate, cCategoryName, cLevel, contact, customerType, difMoney, id, linkMans, periodMoney, pinYin, taxRate |  |
| `delete` | POST | — | id, type |  |
| `disable` | POST | — | contactIds, disable |  |

### basedata/customer.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `exporter` | GET | — | categoryId, list, skey |  |

### basedata/deliveryAddr.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `add` | POST | — | id, shortName |  |
| `update` | POST | — | id, shortName |  |
| `delete` | POST | — | id, shortname |  |
| `query` | POST | — | address, area, city, id, isdefault, linkman, mobile, phone, postalcode, province, shortName |  |

### basedata/employee.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `add` | POST | name、number | id |  |
| `update` | POST | name、number | id |  |
| `delete` | POST | — | id, name |  |
| `disable` | POST | — | disable, employeeIds, name |  |
| `findByNumberOrName` | POST | — | page, rows, skey |  |

### basedata/import.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `downloadtemplate1` | GET | — | — | 下载客户导入模板（`data/download/customer.xls`） |
| `downloadtemplate2` | GET | — | — | 下载供应商导入模板（`vendor.xls`） |
| `downloadtemplate3` | GET | — | — | 下载商品导入模板（`goods.xls`） |
| `findDataImporter` | POST | — | — | 死代码（读 `$_FILES` 后只打印文件名就退出），未接入业务流程 |
| `upload` | GET | — | — | 上传记录：读 `data/upfile/import` 下的真实文件与结果（不再返回写死的示例数据） |
| `uploadExcel` | POST | file | — | `multipart/form-data`，字段名 `file`；表头必须是 `商品编号`/`客户编号`/`供应商编号`，否则返回「模板不匹配」；每次导入会在 `data/upfile/import` 留痕 |

### basedata/inventory.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | assistId, barCode, page, rows, skey |  |
| `listBySelected` | POST | — | contactId, ids, type |  |
| `query` | POST | — | id |  |
| `getNextNo` | POST | — | skey |  |
| `checkBarCode` | POST | — | barCode |  |
| `checkSpec` | POST | — | spec |  |
| `checkname` | POST | — | barCode |  |
| `getImagesById` | POST | — | id |  |
| `uploadImages` | GET | — | — |  |
| `addImagesToInv` | POST | — | files, id, postData |  |
| `getImage` | POST | — | name, pid |  |
| `add` | POST | name、number、categoryId、baseUnitId | categoryName, discountRate1, discountRate2, dopey, highQty, id, lowQty, pinYin, propertys, purPrice, salePrice, sonGoods |  |
| `update` | POST | name、number、categoryId、baseUnitId | categoryName, discountRate1, discountRate2, dopey, highQty, id, locationId, lowQty, pinYin, propertys, purPrice, salePrice |  |
| `delete` | POST | — | id |  |
| `exporter` | GET | — | assistId, barCode, list, skey, storage |  |
| `disable` | POST | — | disable, invIds |  |
| `listinventoryqtywarning` | POST | — | assistId, locationId, page, rows, skey, warnType |  |
| `warningExporter` | POST | — | assistId, list, locationId, skey, warnType |  |

### basedata/invlocation.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `add` | POST | name、locationNo | id, locationId |  |
| `update` | POST | name、locationNo | id, locationId |  |
| `delete` | POST | — | locationId, name |  |
| `disable` | POST | — | disable, locationId, name |  |

### basedata/log.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | fromDate, page, rows, skey, toDate, user |  |
| `initloglist` | GET | — | — |  |
| `queryAllUser` | GET | — | — |  |
| `queryAllOperateType` | GET | — | — |  |

### basedata/resultInfo.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |

### basedata/settAcct.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `query` | POST | — | amount, date, id, name, number, type | 按 id 查账户；查不到返回 `{"status":-1,"msg":"账户不存在"}` |
| `findAmountOver` | POST | — | ids |  |
| `add` | POST | name、number | amount, id, type |  |
| `update` | POST | name、number | amount, id, type |  |
| `delete` | POST | — | id, name |  |

### basedata/supplier.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `exporter` | GET | — | categoryId, list, skey |  |

### basedata/systemProfile.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `generateDocNo` | POST | — | billType |  |
| `update` | POST | — | — |  |
| `changeSysSkin` | POST | — | skin |  |

### basedata/unit.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | unitTypeId |  |
| `add` | POST | name | default, id, rate, unitTypeId |  |
| `update` | POST | name | default, id, rate, unitTypeId |  |
| `delete` | POST | — | id, name |  |

### basedata/unitType.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `add` | POST | — | id, name |  |
| `update` | POST | — | entries, guid, id, name |  |
| `delete` | POST | — | id, name |  |

### basedata/userSetting.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `update` | POST | — | key, value |  |
| `delete` | POST | — | key, value |  |

### basedata/warranty.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |
| `getAdvancedList` | GET | — | data, msg, status |  |

### scm/backup.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | createTime, dbid, fid, filename, size, username |  |
| `queryBackupFile` | GET | — | data, msg, status, totalsize |  |
| `deleteBackupFile` | POST | — | id |  |
| `recover` | POST | — | id |  |
| `download` | POST | — | fid |  |
| `create_folders` | GET | — | — |  |

### scm/invOi.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action, type |  |
| `listIn` | POST | — | beginDate, endDate, locationId, matchCon, page, rows, transTypeId |  |
| `exportInvOi` | GET | — | beginDate, endDate, list, locationId, matchCon, transTypeId |  |
| `queryTransType` | POST | — | type |  |
| `add` | POST | entries | accounts, billDate, billNo, billType, buId, checked, createTime, date, id, inLocationId, modifyTime, outLocationId |  |
| `addnew` | GET | — | — |  |
| `updateOi` | POST | entries | accounts, billDate, billNo, billType, buId, checked, createTime, date, id, inLocationId, modifyTime, outLocationId |  |
| `updateIn` | POST | — | billDate, billNo, billType, buId, checked, contactName, createTime, description, id, modifyTime, totalAmount, totalQty |  |
| `toOiPdf` | GET | — | countpage, id, list, num, postData, system |  |
| `deletein` | POST | — | billNo, id |  |
| `listout` | POST | — | beginDate, endDate, locationId, matchCon, page, rows, transTypeId |  |
| `exportInvOo` | GET | — | beginDate, endDate, list, locationId, matchCon, transTypeId |  |
| `addOo` | POST | entries | accounts, billDate, billNo, billType, buId, checked, createTime, date, id, inLocationId, modifyTime, outLocationId |  |
| `addnewOo` | GET | — | — |  |
| `updateOo` | POST | entries | accounts, billDate, billNo, billType, buId, checked, createTime, date, id, inLocationId, modifyTime, outLocationId |  |
| `updateOut` | POST | — | id |  |
| `toOoPdf` | GET | — | countpage, id, list, num, postData, system |  |
| `deleteOut` | POST | — | billNo, id |  |
| `listCbtz` | POST | — | beginDate, endDate, locationId, matchCon, page, rows |  |
| `exportInvCadj` | GET | — | beginDate, endDate, list, locationId, matchCon |  |
| `addCADJ` | POST | entries | billDate, billNo, billType, createTime, date, id, locationId, modifyTime, postData, totalAmount, transType, transTypeName |  |
| `addNewCADJ` | GET | — | — |  |
| `updateCbtz` | POST | — | billDate, billNo, billType, checked, createTime, description, id, modifyTime, totalAmount, totalQty, transType, userName |  |
| `updateCADJ` | POST | entries | billDate, billNo, billType, createTime, date, id, locationId, modifyTime, postData, totalAmount, transType, transTypeName |  |
| `toCBTZPdf` | GET | — | countpage, id, list, num, system |  |
| `deleteCbtz` | POST | — | billNo, id |  |
| `queryToPD` | POST | — | categoryId, goods, locationId, page, rows, showZero |  |
| `exportToPD` | GET | — | categoryId, goods, list, locationId, showZero |  |
| `generatorPD` | POST | — | entries, postData |  |

### scm/invPo.php　（类 `InvPo`）

> 采购订单：单据存 `ci_order`（`billType="PO"`），明细存 `ci_order_info`；转采购单（`scm/invPu/add` 带 `srcOrderId`）
> 并在购货单**审核**后，订单 `billStatus` 回写为 2（已转单），反审核回写 0。

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action | `action=initPo/editPo/initPoList` |
| `poList` | POST | transType | beginDate, endDate, billNo, buId, page, rows | 列表 |
| `exportInvPo` | GET | — | 同列表 | 导出 |
| `add` | POST | postData | — | 新增（billType=PO，transType=150501） |
| `addNew` | GET | — | — | 新增页 |
| `updateinvPo` | POST | id | — | 编辑页数据 |
| `update` | POST | postData | — | 保存修改 |
| `queryDetails` | POST | id | — | 单据详情 |
| `toPdf` | GET | id | — | 打印 PDF |
| `delete` | POST | id | — | 删除（已审核需先反审核） |
| `batchClose` | GET | id | — | 关闭订单 |
| `batchcheckinvPo` | POST | id | — | 批量审核 |
| `rsbatchcheckinvPo` | POST | id | — | 批量反审核 |
| `checkInvPo` | POST | postData | — | 单张审核 |
| `revsCheckInvPo` | POST | postData | — | 单张反审核 |
| `findNearSoEmp` | GET | — | — | 最近业务员 |

### scm/invPu.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | action, billNo, id |  |
| `purList` | POST | — | beginDate, endDate, matchCon, page, rows, sidx, sord, transType |  |
| `exportInvPu` | GET | — | beginDate, endDate, list, matchCon, sidx, sord, transType |  |
| `findUnhxList` | POST | — | beginDate, billNo, buId, endDate, page, rows |  |
| `add` | POST | billNo、entries、buId | accId, accounts, amount, arrears, billDate, billType, checked, createTime, date, disAmount, disRate, hxStateCode |  |
| `addnew` | GET | — | — |  |
| `updateInvPu` | POST | billNo、entries、buId | accId, accounts, amount, arrears, billDate, billType, checked, createTime, date, disAmount, disRate, hxStateCode |  |
| `update` | POST | — | accId, amount, arrears, billDate, billNo, billStatus, billType, buId, checkName, checked, contactName, createTime |  |
| `toPdf` | GET | — | countpage, entrysPerNote, id, list, num, postData, system |  |
| `delete` | POST | — | id |  |
| `delete1` | POST | — | accId, billNo, checked, id |  |
| `checkInvPu` | POST | billNo、entries、buId | accId, accounts, amount, arrears, billDate, billType, checkName, checked, createTime, date, disAmount, disRate |  |
| `batchCheckInvPu` | POST | — | id |  |
| `rsBatchCheckInvPu` | POST | — | id |  |
| `getImagesById` | POST | — | id |  |
| `uploadImages` | GET | — | — |  |
| `addImagesToInv` | POST | — | files, id, postData |  |
| `getImage` | POST | — | name, pid |  |

### scm/invSa.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | POST | — | action, billNo, id |  |
| `saleList` | POST | — | beginDate, endDate, hxState, matchCon, page, rows, salesId, sidx, sord, transType |  |
| `exportInvSa` | GET | — | beginDate, endDate, hxState, list, matchCon, salesId, sidx, sord, transType |  |
| `invSaleList` | GET | — | — |  |
| `findUnhxList` | POST | — | beginDate, billNo, buId, endDate, page, rows |  |
| `add` | POST | entries、buId | accId, accounts, amount, arrears, billDate, billNo, billType, checked, createTime, customerFree, date, description |  |
| `addNew` | GET | — | — |  |
| `updateInvSa` | POST | entries、buId | accId, accounts, amount, arrears, billDate, billNo, billType, checked, createTime, customerFree, date, description |  |
| `update` | POST | — | accId, amount, arrears, billDate, billNo, billType, buId, checkName, checked, contactName, createTime, customerFree |  |
| `checkInvSa` | POST | entries、buId | accId, accounts, amount, arrears, billDate, billNo, billType, checkName, checked, createTime, customerFree, date |  |
| `revsCheckInvSa` | POST | entries、buId | accId, accounts, amount, arrears, billDate, billNo, billType, checked, createTime, customerFree, date, description |  |
| `batchCheckInvSa` | POST | — | id |  |
| `rsBatchCheckInvSa` | POST | — | id |  |
| `toPdf` | GET | — | countpage, entrysPerNote, id, list, num, postData, system |  |
| `delete` | POST | — | accId, billNo, checked, id |  |
| `justIntimeInv` | POST | — | invId, page, rows |  |
| `findNearSaEmp` | GET | — | — |  |
| `log` | GET | — | — |  |

### scm/invSo.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action |  |
| `soList` | POST | — | beginDate, data, endDate, hxState, matchCon, msg, page, rows, salesId, sidx, sord, status |  |
| `exportInvSo` | GET | — | beginDate, endDate, hxState, list, matchCon, salesId, sidx, sord, transType |  |
| `add` | POST | entries | amount, billDate, billNo, billType, buId, checked, date, description, disAmount, disRate, id, modifyTime |  |
| `addNew` | GET | — | — |  |
| `updateinvSo` | POST | entries | amount, billDate, billNo, billType, buId, checked, date, description, disAmount, disRate, id, modifyTime |  |
| `update` | POST | — | accId, amount, arrears, billDate, billNo, billStatus, billType, buId, checkName, checked, contactName, customerFree |  |
| `queryDetails` | POST | — | accId, amount, arrears, billDate, billNo, billStatus, billType, buId, checkName, checked, contactName, customerFree |  |
| `toPdf` | GET | — | countpage, id, list, num, postData, system |  |
| `delete` | POST | — | billNo, checked, id |  |
| `batchClose` | GET | — | — |  |
| `batchcheckinvSo` | POST | — | id |  |
| `rsbatchcheckinvSo` | POST | — | id |  |
| `checkInvSo` | POST | entries | amount, billDate, billNo, billType, buId, checkName, checked, date, description, disAmount, disRate, id |  |
| `revsCheckInvSo` | POST | entries | amount, billDate, billNo, billType, buId, checked, date, description, disAmount, disRate, id, modifyTime |  |
| `findNearSoEmp` | GET | — | — |  |

### scm/invTf.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action |  |
| `tfList` | POST | — | beginDate, endDate, inLocationId, matchCon, outLocationId, page, rows |  |
| `exportInvTf` | GET | — | beginDate, endDate, inLocationId, list, matchCon, outLocationId |  |
| `add` | POST | entries | accounts, billDate, billNo, billType, checked, createTime, date, description, id, inLocationId, modifyTime, outLocationId |  |
| `addNew` | GET | — | — |  |
| `update` | POST | — | billDate, billNo, checkName, checked, createTime, description, id, modifyTime, postData, totalQty, userName |  |
| `updateInvTf` | POST | entries | accounts, billDate, billNo, billType, checked, createTime, date, description, id, inLocationId, modifyTime, outLocationId |  |
| `toPdf` | GET | — | countpage, id, list, num, postData, system |  |
| `delete` | POST | — | id |  |

### scm/ori.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action |  |
| `listInc` | POST | — | beginDate, endDate, matchCon, page, rows, transTypeId |  |
| `exportInc` | GET | — | beginDate, category, endDate, list, matchCon, transTypeId |  |
| `addInc` | POST | entries | accId, billDate, billNo, billType, buId, createTime, date, id, modifyTime, modifytime, postData, totalAmount |  |
| `addNewInc` | GET | — | — |  |
| `updateInc` | POST | entries | accId, billDate, billNo, billType, buId, createTime, date, id, modifyTime, modifytime, postData, totalAmount |  |
| `getIncDetail` | POST | — | accId, billDate, billNo, buId, contactName, id, totalAmount, userName |  |
| `deleteInc` | POST | — | billNo, id |  |
| `listExp` | POST | — | beginDate, endDate, matchCon, page, rows |  |
| `exportExp` | GET | — | beginDate, category, endDate, list, matchCon, transTypeId |  |
| `addExp` | POST | entries | accId, billDate, billNo, billType, buId, createTime, date, id, modifyTime, modifytime, postData, totalAmount |  |
| `addNewExp` | GET | — | — |  |
| `updateExp` | POST | entries | accId, billDate, billNo, billType, buId, createTime, date, id, modifyTime, modifytime, postData, totalAmount |  |
| `getExpDetail` | POST | — | accId, amount, billDate, billNo, buId, contactName, id, userName |  |
| `deleteExp` | POST | — | billNo, id |  |
| `toPdf` | GET | — | countpage, id, list, num, system, transType |  |

### scm/payment.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action |  |
| `payList` | POST | — | beginDate, endDate, matchCon, page, rows |  |
| `export` | GET | — | account, beginDate, category, endDate, list, locationId, matchCon |  |
| `add` | POST | accounts、buId | arrears, billDate, billNo, billType, checked, createTime, date, entries, hxAmount, id, modifyTime, payment |  |
| `addNew` | GET | — | — |  |
| `updatePayment` | POST | accounts、buId | arrears, billDate, billNo, billType, checked, createTime, date, entries, hxAmount, id, modifyTime, payment |  |
| `update` | POST | — | billDate, billNo, buId, checkName, checked, contactName, createTime, description, discount, id, modifyTime, payment |  |
| `delete` | POST | — | billNo, id |  |
| `toPdf` | GET | — | account, category, id, list, num, system |  |

### scm/pdImport.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | — |  |

### scm/prints.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `getOrderPrintData` | POST | — | amount, arrears, billDate, billNo, contactName, countpage, deliveryDate, description, disAmount, id, list, num |  |

### scm/receipt.php

| 方法 | HTTP | 参数（必填） | 参数（选填） | 说明 |
| --- | --- | --- | --- | --- |
| `index` | GET | — | action |  |
| `receiptList` | POST | — | beginDate, endDate, matchCon, page, rows |  |
| `exportReceipt` | GET | — | account, beginDate, category, endDate, list, locationId, matchCon |  |
| `add` | POST | accounts、buId | arrears, billDate, billNo, billType, checked, createTime, date, entries, hxAmount, id, modifyTime, payment |  |
| `addnew` | GET | — | — |  |
| `updateReceipt` | POST | accounts、buId | arrears, billDate, billNo, billType, checked, createTime, date, entries, hxAmount, id, modifyTime, payment |  |
| `update` | POST | — | billDate, billNo, buId, checkName, checked, contactName, createTime, description, discount, id, modifyTime, payment |  |
| `delete` | POST | — | billNo, id |  |
| `toPdf` | GET | — | account, category, id, list, num, system |  |

## 附录 A　41 个写接口实测记录

方法：先发空参数，再发「源码必填字段全部填值」的参数。空参数返回第一个拦截原因（部分接口先判「有无提交数据」，所以显示「添加失败」）；全参数不再报「不能为空」，剩下的业务错误（重复、仓库不存在等）属正常。标「需 postData JSON」的接口必须整单提交，见 2.3–2.11。

| 接口 | 必填（源码） | 空参数返回 | 全参数返回 |
| --- | --- | --- | --- |
| `basedata/assist/add` | name、typeNumber | ✘ 类别名称不能为空 | ✔ success |
| `basedata/assist/update` | name、typeNumber | ✘ 类别名称不能为空 | ✘ 类别名称重复 |
| `basedata/contact/add` | name、number、cCategory | ✘ 名称不能为空 | ✔ success |
| `basedata/contact/update` | name、number、cCategory | ✘ 名称不能为空 | ✘ 缺少要修改的记录 ID |
| `basedata/employee/add` | name、number | ✘ 添加失败 | ✔ success |
| `basedata/employee/update` | name、number | ✘ 更新失败 | ✘ 员工编号重复 |
| `basedata/inventory/add` | name、number、categoryId、baseUnitId | ✘ 添加失败 | ✔ success |
| `basedata/inventory/update` | name、number、categoryId、baseUnitId | ✘ 修改失败 | ✘ 请选择首选仓库！ |
| `basedata/invlocation/add` | name、locationNo | ✘ 添加失败 | ✔ success |
| `basedata/invlocation/update` | name、locationNo | ✘ 更新失败 | ✘ 名称重复 |
| `basedata/settAcct/add` | name、number | ✘ 添加失败 | ✔ success |
| `basedata/settAcct/update` | name、number | ✘ 更新失败 | ✘ 名称重复 |
| `basedata/unit/add` | name | ✘ 单位名称不能为空 | ✔ success |
| `basedata/unit/update` | name | ✘ 单位名称不能为空 | ✘ 单位名称重复 |
| `scm/invOi/add` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invOi/addCADJ` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invOi/addOo` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invOi/updateCADJ` | entries | ✘ 提交数据不为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invOi/updateOi` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invOi/updateOo` | entries | ✘ 提交数据不为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invPu/add` | billNo、entries、buId | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invPu/checkInvPu` | billNo、entries、buId | ✘ 提交的数据不能为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invPu/updateInvPu` | billNo、entries、buId | ✘ 提交的数据不能为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSa/add` | entries、buId | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSa/checkInvSa` | entries、buId | ✘ 提交的数据不能为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSa/revsCheckInvSa` | entries、buId | ✘ 提交的数据不能为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSa/updateInvSa` | entries、buId | ✘ 提交的数据不为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSo/add` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSo/checkInvSo` | entries | ✘ 审核失败 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSo/revsCheckInvSo` | entries | ✘ 提交失败 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invSo/updateinvSo` | entries | ✘ 提交的数据不为空 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invTf/add` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/invTf/updateInvTf` | entries | ✘ 参数错误 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/ori/addExp` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/ori/addInc` | entries | ✘ 提交的是空数据 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/ori/updateExp` | entries | ✘ 参数错误 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/ori/updateInc` | entries | ✘ 单据不存在 | 需 postData JSON（见 2.3 / 2.5 实测） |
| `scm/payment/add` | accounts、buId | ✘ 提交的是空数据 | 需 postData JSON（见 2.9 / 2.10 实测） |
| `scm/payment/updatePayment` | accounts、buId | ✘ 参数错误 | ✘ 参数错误 |
| `scm/receipt/add` | accounts、buId | ✘ 提交的是空数据 | 需 postData JSON（见 2.9 / 2.10 实测） |
| `scm/receipt/updateReceipt` | accounts、buId | ✘ 参数错误 | ✘ 参数错误 |

## 附录 B　本轮修复的接口缺陷

| # | 接口 | 现象 | 修复 |
| --- | --- | --- | --- |
| 1 | `basedata/contact/update` | 不传 id 时拼出 `WHERE id != `，MySQL 1064 报 500 | 补 id 校验，返回「缺少要修改的记录 ID」 |
| 2 | `basedata/contact/add\|update` | 类别 id 不存在时写入 NULL，超范围还报 1264 | 增加「类别不存在」校验 |
| 3 | `scm/invSa/delete` | 只读 GET 的 id，POST 删除永远「单据不存在」 | 改为 `get_post` |
| 4 | `scm/receipt/payment/invOi/invSo/invTf/ori` 的 delete* | 同上，只认 GET | 统一改为 `get_post` |
| 5 | `scm/invTf/delete` | 用 `iid` 更新 `ci_invoice`，1054 报 500，调拨单删不掉 | 改为 `id`，日志取 `$data[0]['billNo']` |
| 6 | 客户/供应商 type 语义 | 导出、最近往来、数据权限、资金余额表里 10/-10 混用 | 统一 `10=客户、-10=供应商` |

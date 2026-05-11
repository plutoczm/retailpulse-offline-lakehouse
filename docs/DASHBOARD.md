# 可视化大屏

## 目标

大屏直接展示 RetailPulse ADS 层指标，面向经营分析和面试演示，覆盖 GMV、支付金额、订单量、支付转化率、真实行为漏斗、TopN、留存、RFM、库存周转和公开数据资产画像。

当前版本为企业级三维沉浸式大屏，使用 `100vw × 100vh` 全屏驾驶舱布局，界面和图表文字统一使用中文字体，Windows 优先使用 `Microsoft YaHei UI` / `Microsoft YaHei`：

- 使用本地 `dashboard/vendor/three.module.min.js` 构建 WebGL 粒子、光线和三维数据柱体背景。
- 图表面板采用悬浮式 3D 纵深布局、发光边缘、流光扫描和空间漂浮动效。
- 桌面端去掉最大宽度限制，超宽屏或浏览器缩放时仍会铺满窗口。
- 支持折线/面积、3D 柱状、中心转化环、散点星图、行为热力图、资产表格。
- 支持日期筛选、指标选择、纵深调节、鼠标悬停 tooltip、图表滚轮缩放、WebGL 背景拖拽旋转。
- 点击趋势图日期后，中心转化核心、商品排行和三维柱体会联动刷新。

## 生成数据

先跑完整链路：

```powershell
conda activate retailpulse-lakehouse
python scripts/run_all.py --scale tiny --start-date 2025-01-01 --days 7
```

导出大屏 JSON：

```powershell
python scripts/export_dashboard_data.py --data-root data --external-root external_data/synerise-recsys-2025/extracted --output dashboard/data/dashboard.json --topn 10
```

启动本地服务：

```powershell
python scripts/serve_dashboard.py --port 8508
```

浏览器打开：

```text
http://127.0.0.1:8508
```

## 大屏文件

```text
dashboard/
  index.html
  data/
    dashboard.json
```

`index.html` 使用原生 HTML/CSS/Canvas + 本地 Three.js 实现，不依赖前端构建工具。数据由 `scripts/export_dashboard_data.py` 从 ADS Parquet 汇总生成。

## 展示模块

| 模块 | 来源表 |
| --- | --- |
| KPI 卡片 | `ads_retail_dashboard_daily` |
| 交易趋势 | `ads_retail_dashboard_daily` |
| 商品购买排行 | `ads_synerise_product_topn` |
| 品类销售 TopN | `ads_category_topn` |
| 店铺销售排行 | `ads_shop_rank` |
| RFM 用户分层 | `ads_rfm_user_segment` |
| 留存与库存明细 | `ads_user_retention`、`ads_inventory_turnover`、`ads_refund_analysis` |
| 中心转化核心 | `ads_synerise_behavior_dashboard_daily` |
| 行为能量波 | `ads_synerise_behavior_dashboard_daily` |
| 转化星图 | `ads_synerise_behavior_dashboard_daily` |
| 行为热力矩阵 | `ads_synerise_event_type_trend` |
| 公开大规模行为数据资产 | `external_data/synerise-recsys-2025/extracted/*.parquet` 的 Parquet metadata |

## 验证

已使用 Playwright 在桌面 `1440x1000` 和移动端 `390x844` 两个视口截图验证，并对所有 canvas 做非空像素检查。截图输出：

```text
reports/enterprise_dashboard_desktop.png
reports/enterprise_dashboard_mobile.png
```

## 面试讲法

这个大屏不是直接扫明细事实表，而是读取 ADS 应用层结果。这样做的好处是展示层和计算层解耦，页面刷新不触发重计算；如果后续接入 Superset、FineBI 或 Grafana，也只需要替换展示工具，不需要重写数仓链路。

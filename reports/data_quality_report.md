# RetailPulse 数据质量报告

- 检查项总数：12
- 通过：12
- 失败：0

| 规则ID | 规则名称 | 检查表 | 状态 | 异常数 | 说明 |
| --- | --- | --- | --- | ---: | --- |
| DQ001 | 主键重复检查 | `dwd_trade_order_detail` | PASS | 0 | 订单明细主键 order_item_id 不应重复。 |
| DQ002 | 关键字段为空检查 | `dwd_trade_order_detail` | PASS | 0 | 交易明细关键字段不能为空。 |
| DQ003 | 订单金额异常检查 | `dwd_trade_order_detail` | PASS | 0 | 订单金额、优惠金额和应付金额需满足基本金额关系。 |
| DQ004 | 支付金额与订单金额一致性检查 | `dwd_trade_payment_detail` | PASS | 0 | 成功支付金额应与订单应付金额基本一致。 |
| DQ005 | 支付时间早于下单时间检查 | `dwd_trade_payment_detail` | PASS | 0 | 支付时间不能早于下单时间。 |
| DQ006 | 退款金额大于支付金额检查 | `dwd_trade_refund_detail` | PASS | 0 | 退款金额不能超过成功支付金额。 |
| DQ007 | 维表关联缺失检查 | `dwd_trade_order_detail` | PASS | 0 | 交易明细中的用户、商品、店铺必须能关联到维表。 |
| DQ008 | 每日分区为空检查 | `dwd_trade_order_detail` | PASS | 0 | 指定日期范围内每日应有交易分区。 |
| DQ009 | 用户行为事件类型非法检查 | `ods_user_events` | PASS | 0 | 事件类型必须属于 view/search/cart/favorite/order/pay。 |
| DQ010 | 库存流水数量异常检查 | `dwd_inventory_change_detail` | PASS | 0 | 库存流水需满足 before + change = after，且数量不能异常放大。 |
| DQ011 | 支付主键重复检查 | `dwd_trade_payment_detail` | PASS | 0 | 支付流水 payment_id 不应重复。 |
| DQ012 | 退款关键字段为空检查 | `dwd_trade_refund_detail` | PASS | 0 | 退款明细关键字段不能为空。 |

## 解读

该报告用于离线批处理完成后的基础质量验收。若出现 FAIL，应优先排查源数据生成、DWD 清洗逻辑和维表装载是否一致。

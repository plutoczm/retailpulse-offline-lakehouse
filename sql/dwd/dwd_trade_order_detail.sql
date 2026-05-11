-- DWD 交易订单明细：订单明细粒度，一行代表一个 order_item_id。

SELECT
  oi.order_item_id,
  o.order_id,
  o.user_id,
  o.shop_id,
  oi.product_id,
  oi.category_id,
  p.category_name,
  p.brand,
  oi.sku_id,
  oi.quantity,
  oi.sale_price,
  oi.item_amount,
  o.total_amount,
  o.discount_amount,
  o.payable_amount,
  lower(o.order_status) AS order_status,
  to_timestamp(o.order_time) AS order_time,
  o.province,
  o.city,
  o.dt
FROM ods_order_items oi
JOIN ods_orders o ON oi.order_id = o.order_id
LEFT JOIN ods_products p ON oi.product_id = p.product_id
WHERE oi.order_item_id IS NOT NULL
  AND o.order_id IS NOT NULL
  AND oi.quantity > 0
  AND oi.item_amount >= 0
  AND o.payable_amount >= 0;


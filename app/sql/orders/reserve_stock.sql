UPDATE products
SET prod_balance = prod_balance - %(count)s
WHERE prod_id = %(prod_id)s
  AND prod_balance >= %(count)s

INSERT INTO orders (user_id)
VALUES (%(user_id)s)
RETURNING order_id

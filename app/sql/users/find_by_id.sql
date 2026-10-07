SELECT id, login, role, contract_num
FROM users
WHERE id = %(user_id)s
  AND is_active

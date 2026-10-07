SELECT id, login, password_hash, role, contract_num, is_active
FROM users
WHERE login = %(login)s

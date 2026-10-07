SELECT account_num, balance
FROM accounts
WHERE contract_num = %(contract_num)s
ORDER BY account_num

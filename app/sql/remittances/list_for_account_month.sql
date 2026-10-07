SELECT amount, receiver_account_id, sender_account_id, remittance_moment
FROM remittances
WHERE remittance_moment >= %(period_start)s
  AND remittance_moment <  %(period_end)s
  AND (sender_account_id = %(account_num)s OR receiver_account_id = %(account_num)s)
ORDER BY remittance_moment DESC

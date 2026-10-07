-- Inserts the remittance only if the sender account belongs to the client (zero rows otherwise).
-- The balance is applied, and the balance rule enforced, by the on_transfer trigger.
INSERT INTO remittances (amount, sender_account_id, receiver_account_id)
SELECT %(amount)s, a.account_num, %(receiver)s
FROM accounts a
WHERE a.account_num = %(sender)s
  AND a.contract_num = %(contract_num)s

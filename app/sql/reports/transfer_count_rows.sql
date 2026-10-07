SELECT account_num, transfer_count AS value
FROM transfer_count_report
WHERE report_date = %(period)s
ORDER BY account_num

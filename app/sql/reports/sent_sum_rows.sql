SELECT account_num, sent_sum AS value
FROM sent_report
WHERE report_date = %(period)s
ORDER BY account_num

-- Removes every object created by db/schema.sql and tests/hooks.sql so the test suite can
-- rebuild the schema from scratch. Used by tests/conftest.py only.
DROP TABLE IF EXISTS order_details, orders, products, sent_report, transfer_count_report,
                     remittances, accounts, users, clients CASCADE;
DROP FUNCTION IF EXISTS forbid_remittance_change() CASCADE;
DROP FUNCTION IF EXISTS lock_remittance_accounts() CASCADE;
DROP FUNCTION IF EXISTS apply_remittance() CASCADE;
DROP FUNCTION IF EXISTS test_hooks() CASCADE;
DROP FUNCTION IF EXISTS hash_password(text);
DROP PROCEDURE IF EXISTS create_sent_report(date);
DROP PROCEDURE IF EXISTS create_transfer_count_report(date);
DROP DOMAIN IF EXISTS account_number, money_amount;
DROP TYPE IF EXISTS user_role;

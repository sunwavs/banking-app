-- =============================================================================
-- RIS sandbox data
--
-- Synthetic data for local development and demos. Every value is fictional.
-- Run after db/schema.sql:
--     psql -v ON_ERROR_STOP=1 -d Bank -f db/schema.sql -f db/seed.sql
--
-- Demo credentials (sandbox only; every user has the same password, which is
-- stored as a bcrypt hash created by hash_password()):
--
--     login       password           role
--     client1     sandbox-password   external (contract 1001)
--     client2     sandbox-password   external (contract 1002)
--     client3     sandbox-password   external (contract 1003)
--     manager1    sandbox-password   manager
--     analyst1    sandbox-password   analyst
--     operator1   sandbox-password   operator
--
-- Remittances are dated January and February 2024 (UTC), so reports can be generated
-- for 2024-01 and 2024-02.
-- =============================================================================

BEGIN;

INSERT INTO clients (contract_num, last_name, address, birthday, phone_num, reg_date) VALUES
    ('1001', 'Client One',   '1 Example Street', '1990-01-01', '000-000-0001', '2020-01-01'),
    ('1002', 'Client Two',   '2 Example Street', '1991-02-02', '000-000-0002', '2020-01-01'),
    ('1003', 'Client Three', '3 Example Street', '1992-03-03', '000-000-0003', '2020-01-01');

INSERT INTO users (login, password_hash, role, contract_num) VALUES
    ('client1',   hash_password('sandbox-password'), 'external', '1001'),
    ('client2',   hash_password('sandbox-password'), 'external', '1002'),
    ('client3',   hash_password('sandbox-password'), 'external', '1003'),
    ('manager1',  hash_password('sandbox-password'), 'manager',  NULL),
    ('analyst1',  hash_password('sandbox-password'), 'analyst',  NULL),
    ('operator1', hash_password('sandbox-password'), 'operator', NULL);

-- Opening balances. The remittances below are applied by the on_transfer trigger, so the
-- final balances are the opening balances adjusted by the history.
INSERT INTO accounts (account_num, balance, last_change, contract_num) VALUES
    ('10000001', 5000.00, '2024-01-01 00:00:00+00', '1001'),
    ('10000002', 1500.00, '2024-01-01 00:00:00+00', '1001'),
    ('20000001', 8000.00, '2024-01-01 00:00:00+00', '1002'),
    ('30000001',  300.00, '2024-01-01 00:00:00+00', '1003');

INSERT INTO remittances (amount, remittance_moment, sender_account_id, receiver_account_id) VALUES
    (250.00, '2024-01-10 10:00:00+00', '10000001', '20000001'),
    (100.00, '2024-01-15 14:30:00+00', '20000001', '10000001'),
    ( 40.50, '2024-01-22 09:15:00+00', '10000001', '30000001'),
    (500.00, '2024-02-03 11:00:00+00', '20000001', '30000001'),
    ( 75.25, '2024-02-14 16:45:00+00', '10000002', '10000001'),
    (120.00, '2024-02-20 12:00:00+00', '10000001', '20000001');

INSERT INTO products (prod_name, prod_price, prod_balance) VALUES
    ('Sample product A', 100.00, 100),
    ('Sample product B', 250.00,  50),
    ('Sample product C',  75.50, 200);

COMMIT;

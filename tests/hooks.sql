-- Test-only trigger. It is installed on top of the production schema (db/schema.sql) and
-- never changes the production on_transfer trigger.
--
-- AFTER triggers fire in name order, so zz_test_hooks runs after on_transfer has already
-- updated the balances and still holds the account row locks. A remittance of exactly 600
-- is delayed at that point (locks held, transaction uncommitted), which widens the race
-- window and makes concurrency tests reproducible.
CREATE FUNCTION test_hooks() RETURNS trigger
    LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.amount = 600 THEN
        PERFORM pg_sleep(0.4);
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER zz_test_hooks
    AFTER INSERT ON remittances
    FOR EACH ROW EXECUTE FUNCTION test_hooks();

-- Enable balance tracking for all existing instances
UPDATE bot_instances SET balance_enabled = true WHERE balance_enabled = false OR balance_enabled IS NULL;

-- Show results
SELECT name, balance_enabled, user_id FROM bot_instances ORDER BY name;
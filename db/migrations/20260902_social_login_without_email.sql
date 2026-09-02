-- Run once in Railway MySQL after deploying the matching application code.
-- MySQL permits multiple NULL values in a UNIQUE email column.
ALTER TABLE users
    MODIFY COLUMN email VARCHAR(255) NULL;

ALTER TABLE social_accounts
    ADD CONSTRAINT uq_social_accounts_provider_user
    UNIQUE (provider, provider_user_id);

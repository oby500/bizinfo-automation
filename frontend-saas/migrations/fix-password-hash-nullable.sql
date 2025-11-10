-- Make password_hash column nullable for social login users
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;

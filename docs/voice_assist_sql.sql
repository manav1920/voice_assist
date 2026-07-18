CREATE TABLE users (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    supabase_user_id CHAR(36) NOT NULL UNIQUE,

    first_name VARCHAR(100) NOT NULL,

    last_name VARCHAR(100),

    email VARCHAR(255) NOT NULL UNIQUE,

    phone_number VARCHAR(20) UNIQUE,

    profile_picture VARCHAR(500),

    is_active BOOLEAN DEFAULT TRUE,

    onboarding_completed BOOLEAN DEFAULT FALSE,

    last_login TIMESTAMP NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP

);

-- If you already ran the CREATE TABLE above on an earlier version and
-- have real data in it, don't re-run CREATE TABLE - use this instead:
--
-- ALTER TABLE users
--     ADD COLUMN profile_picture VARCHAR(500) AFTER phone_number,
--     ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE AFTER is_active;
CREATE TABLE conversations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE

);
CREATE TABLE messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id BIGINT NOT NULL,
    role ENUM(
        'user',
        'assistant',
        'system'
    ) NOT NULL,

    message LONGTEXT NOT NULL,
    model VARCHAR(100),
    token_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (conversation_id)
        REFERENCES conversations(id)
        ON DELETE CASCADE

);
CREATE TABLE memory (

    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    user_id BIGINT NOT NULL,

    category VARCHAR(100) NOT NULL,

    key_name VARCHAR(255) NOT NULL,

    value TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_memory_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_user_memory
        UNIQUE (user_id, key_name)

);
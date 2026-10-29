CREATE DATABASE IF NOT EXISTS recipe_kb
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE recipe_kb;

CREATE TABLE IF NOT EXISTS households (
    household_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    household_name VARCHAR(100) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (household_id),
    UNIQUE KEY uq_household_name (household_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS roommates (
    roommate_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    household_id BIGINT UNSIGNED NOT NULL,
    display_name VARCHAR(80) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (roommate_id),
    UNIQUE KEY uq_household_roommate (household_id, display_name),
    CONSTRAINT fk_roommates_household FOREIGN KEY (household_id)
        REFERENCES households (household_id) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS roommate_preferences (
    preference_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    roommate_id BIGINT UNSIGNED NOT NULL,
    preference_type ENUM('like', 'dislike', 'allergy', 'intolerance', 'dietary') NOT NULL,
    preference_value VARCHAR(100) NOT NULL,
    strict BOOLEAN NOT NULL DEFAULT FALSE,
    notes VARCHAR(255) NULL,
    PRIMARY KEY (preference_id),
    UNIQUE KEY uq_roommate_preference (roommate_id, preference_type, preference_value),
    CONSTRAINT fk_preferences_roommate FOREIGN KEY (roommate_id)
        REFERENCES roommates (roommate_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS pantry_items (
    pantry_item_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    household_id BIGINT UNSIGNED NOT NULL,
    ingredient_name VARCHAR(100) NOT NULL,
    quantity DECIMAL(10, 3) NULL,
    unit VARCHAR(30) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (pantry_item_id),
    UNIQUE KEY uq_household_pantry_ingredient (household_id, ingredient_name),
    CONSTRAINT fk_pantry_household FOREIGN KEY (household_id)
        REFERENCES households (household_id) ON DELETE CASCADE,
    CONSTRAINT chk_pantry_quantity CHECK (quantity IS NULL OR quantity >= 0)
) ENGINE=InnoDB;


CREATE TABLE IF NOT EXISTS recipe_requests (
    request_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    household_id BIGINT UNSIGNED NOT NULL,
    user_request TEXT NULL,
    budget DECIMAL(10, 2) NULL,
    servings_requested SMALLINT UNSIGNED NULL,
    constraints_snapshot JSON NOT NULL,
    recipe_source ENUM('api', 'llm', 'api_and_llm') NULL,
    source_reference VARCHAR(1000) NULL,
    result_recipe JSON NULL,
    validation_result ENUM('pending', 'accepted', 'rejected', 'no_match', 'failed')
        NOT NULL DEFAULT 'pending',
    validation_notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (request_id),
    KEY idx_requests_household_date (household_id, created_at),
    CONSTRAINT fk_requests_household FOREIGN KEY (household_id)
        REFERENCES households (household_id) ON DELETE CASCADE,
    CONSTRAINT chk_request_budget CHECK (budget IS NULL OR budget >= 0),
    CONSTRAINT chk_request_servings CHECK (servings_requested IS NULL OR servings_requested > 0)
) ENGINE=InnoDB;


INSERT IGNORE INTO households (household_name) VALUES ('Demo household');
INSERT IGNORE INTO roommates (household_id, display_name)
SELECT household_id, 'Roommate 1' FROM households WHERE household_name = 'Demo household';
INSERT IGNORE INTO roommates (household_id, display_name)
SELECT household_id, 'Roommate 2' FROM households WHERE household_name = 'Demo household';

-- Demo constraints and pantry contents so the Python example has data to display.
INSERT IGNORE INTO roommate_preferences
    (roommate_id, preference_type, preference_value, strict)
SELECT roommate_id, 'dietary', 'vegetarian', TRUE
FROM roommates
WHERE display_name = 'Roommate 2'
  AND household_id = (SELECT household_id FROM households WHERE household_name = 'Demo household');

INSERT IGNORE INTO pantry_items (household_id, ingredient_name)
SELECT household_id, pantry.ingredient_name
FROM households
CROSS JOIN (
    SELECT 'rice' AS ingredient_name UNION ALL SELECT 'broccoli'
    UNION ALL SELECT 'garlic' UNION ALL SELECT 'olive oil'
    UNION ALL SELECT 'eggs' UNION ALL SELECT 'pasta'
    UNION ALL SELECT 'tomatoes' UNION ALL SELECT 'spinach'
    UNION ALL SELECT 'cheese'
) AS pantry
WHERE household_name = 'Demo household';

-- Typical workflow:
-- 1. Read roommates + roommate_preferences + pantry_items for a household.
-- 2. Save the request and a constraints_snapshot in recipe_requests.
-- 3. Search a recipe API or call an LLM in the application.
-- 4. Validate candidates against every roommate's preferences/restrictions.
-- 5. Update result_recipe, recipe_source, validation_result, and validation_notes.

-- mirofish-pro enhanced mysql schema
--
-- this file mirrors the sqlalchemy orm models in:
--   backend/app/models/ingestion.py
--   backend/app/models/memory.py
--   backend/app/models/review.py
--
-- the application can also create these tables automatically through:
--   backend/app/db.py -> create_all_tables()
--
-- usage:
--   mysql -u root -p < docs/sql/schema_mysql.sql

CREATE DATABASE IF NOT EXISTS `mirofish`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `mirofish`;

CREATE TABLE IF NOT EXISTS `ingestion_task` (
  `id` int NOT NULL AUTO_INCREMENT,
  `task_id` varchar(64) NOT NULL,
  `keyword` varchar(255) DEFAULT NULL,
  `task_type` varchar(64) NOT NULL,
  `status` varchar(32) NOT NULL,
  `error_message` text,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_ingestion_task_task_id` (`task_id`),
  KEY `idx_ingestion_task_type` (`task_type`),
  KEY `idx_ingestion_task_status` (`status`),
  KEY `idx_ingestion_task_created_at` (`created_at`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `memory_item` (
  `id` int NOT NULL AUTO_INCREMENT,
  `source` varchar(255) DEFAULT NULL,
  `source_type` varchar(64) DEFAULT NULL,
  `url` varchar(1024) DEFAULT NULL,
  `title` varchar(512) DEFAULT NULL,
  `raw_text` text,
  `clean_text` text,
  `summary` text,
  `publish_time` datetime DEFAULT NULL,
  `content_hash` varchar(64) DEFAULT NULL,
  `importance_score` float NOT NULL,
  `credibility_score` float NOT NULL,
  `memory_type` varchar(64) NOT NULL,
  `is_embedded` tinyint(1) NOT NULL,
  `is_written_to_zep` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_memory_item_content_hash` (`content_hash`),
  KEY `idx_memory_item_type_time` (`memory_type`, `publish_time`),
  KEY `idx_memory_item_created_at` (`created_at`),
  KEY `idx_memory_item_source_type` (`source_type`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `memory_evidence` (
  `id` int NOT NULL AUTO_INCREMENT,
  `memory_id` int NOT NULL,
  `claim` text,
  `evidence_text` text,
  `evidence_type` varchar(64) DEFAULT NULL,
  `source_url` varchar(1024) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_memory_evidence_type` (`evidence_type`),
  KEY `idx_memory_evidence_memory_id` (`memory_id`),
  CONSTRAINT `memory_evidence_ibfk_1`
    FOREIGN KEY (`memory_id`)
    REFERENCES `memory_item` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `review` (
  `id` int NOT NULL AUTO_INCREMENT,
  `claim` text NOT NULL,
  `supporting_evidence_json` text,
  `opposing_evidence_json` text,
  `neutral_evidence_json` text,
  `role_reviews_json` text,
  `confidence_score` float NOT NULL,
  `risk_notes_json` text,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_review_confidence` (`confidence_score`),
  KEY `idx_review_created_at` (`created_at`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;

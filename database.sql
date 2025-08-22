  -- MySQL-дамп для структуры базы данных hotel_service
  -- Версия: 8.0.42

  /*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
  /*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
  /*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
  /*!50503 SET NAMES utf8mb4 */;
  /*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
  /*!40103 SET TIME_ZONE='+00:00' */;
  /*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
  /*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
  /*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
  /*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

  --
  -- Структура для таблицы `users`
  --
  DROP TABLE IF EXISTS `users`;
  CREATE TABLE `users` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `first_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `patronymic` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `phone_number` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `status` enum('active','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `archived_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `phone_number` (`phone_number`)
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `employees`
  --
  DROP TABLE IF EXISTS `employees`;
  CREATE TABLE `employees` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `first_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `last_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
    `patronymic` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
    `role` enum('admin','reception','manager') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `username` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `salary` decimal(10,2) DEFAULT NULL,
    `status` enum('active','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `archived_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `username` (`username`)
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `room_types`
  --
  DROP TABLE IF EXISTS `room_types`;
  CREATE TABLE `room_types` (
    `id` int unsigned NOT NULL AUTO_INCREMENT,
    `code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `code` (`code`)
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `room_type_translations`
  --
  DROP TABLE IF EXISTS `room_type_translations`;
  CREATE TABLE `room_type_translations` (
    `room_type_id` int unsigned NOT NULL,
    `language_code` enum('ru','en','uz') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    PRIMARY KEY (`room_type_id`,`language_code`),
    CONSTRAINT `room_type_translations_ibfk_1` FOREIGN KEY (`room_type_id`) REFERENCES `room_types` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `rooms`
  --
  DROP TABLE IF EXISTS `rooms`;
  CREATE TABLE `rooms` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `room_number` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `room_type_id` int unsigned NOT NULL,
    `status` enum('available','occupied','maintenance') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'available',
    `current_price_per_night` decimal(10,2) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `room_type_id` (`room_type_id`),
    CONSTRAINT `rooms_ibfk_1` FOREIGN KEY (`room_type_id`) REFERENCES `room_types` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `bookings`
  --
  DROP TABLE IF EXISTS `bookings`;
  CREATE TABLE `bookings` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `user_id` bigint unsigned NOT NULL,
    `room_id` bigint unsigned NOT NULL,
    `employee_id` bigint unsigned NOT NULL,
    `price_per_night` decimal(10,2) NOT NULL,
    `check_in_date` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `check_out_date` datetime NOT NULL,
    `status` enum('confirmed','active','completed','cancelled') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'confirmed',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `user_id` (`user_id`),
    KEY `room_id` (`room_id`),
    KEY `employee_id` (`employee_id`),
    CONSTRAINT `bookings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `bookings_ibfk_2` FOREIGN KEY (`room_id`) REFERENCES `rooms` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `bookings_ibfk_3` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `chats`
  --
  DROP TABLE IF EXISTS `chats`;
  CREATE TABLE `chats` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `booking_id` bigint unsigned NOT NULL,
    `type` enum('AI','RECEPTION') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `status` enum('open','claimed','closed') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'open',
    `assigned_employee_id` bigint unsigned DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `fk_chats_booking` (`booking_id`),
    KEY `fk_chats_assigned_employee` (`assigned_employee_id`),
    CONSTRAINT `fk_chats_booking` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_chats_assigned_employee` FOREIGN KEY (`assigned_employee_id`) REFERENCES `employees` (`id`) ON DELETE SET NULL
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


  --
  -- Структура для таблицы `messages`
  --
  DROP TABLE IF EXISTS `messages`;
  CREATE TABLE `messages` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `chat_id` bigint unsigned NOT NULL,
    `sender_type` enum('user','employee','ai') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `sender_user_id` bigint unsigned DEFAULT NULL,
    `sender_employee_id` bigint unsigned DEFAULT NULL,
    `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `chat_id` (`chat_id`),
    KEY `sender_user_id` (`sender_user_id`),
    KEY `sender_employee_id` (`sender_employee_id`),
    CONSTRAINT `messages_ibfk_1` FOREIGN KEY (`chat_id`) REFERENCES `chats` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `messages_ibfk_2` FOREIGN KEY (`sender_user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `messages_ibfk_3` FOREIGN KEY (`sender_employee_id`) REFERENCES `employees` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


  --
  -- Структура для таблицы `services`
  --
  DROP TABLE IF EXISTS `services`;
  CREATE TABLE `services` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `price` decimal(10,2) NOT NULL,
    `status` enum('available','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'available',
    `archived_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`id`)
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `service_translations`
  --
  DROP TABLE IF EXISTS `service_translations`;
  CREATE TABLE `service_translations` (
    `service_id` bigint unsigned NOT NULL,
    `language_code` enum('ru','en','uz') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
    `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
    PRIMARY KEY (`service_id`,`language_code`),
    CONSTRAINT `service_translations_ibfk_1` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Структура для таблицы `service_requests`
  --
  DROP TABLE IF EXISTS `service_requests`;
  CREATE TABLE `service_requests` (
    `id` bigint unsigned NOT NULL AUTO_INCREMENT,
    `booking_id` bigint unsigned NOT NULL,
    `service_id` bigint unsigned NOT NULL,
    `price` decimal(10,2) NOT NULL,
    `assigned_employee_id` bigint unsigned DEFAULT NULL,
    `status` enum('requested','in_progress','completed','cancelled') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'requested',
    `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `service_id` (`service_id`),
    KEY `assigned_employee_id` (`assigned_employee_id`),
    KEY `idx_booking_id` (`booking_id`),
    CONSTRAINT `fk_service_requests_booking` FOREIGN KEY (`booking_id`) REFERENCES `bookings` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `service_requests_ibfk_2` FOREIGN KEY (`service_id`) REFERENCES `services` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT `service_requests_ibfk_3` FOREIGN KEY (`assigned_employee_id`) REFERENCES `employees` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
  ) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

  --
  -- Триггер для таблицы `employees`
  --
  DROP TRIGGER IF EXISTS `set_archived_at_on_status_change`;
  DELIMITER ;;
  CREATE TRIGGER `set_archived_at_on_status_change` BEFORE UPDATE ON `employees` FOR EACH ROW BEGIN
      IF NEW.status = 'archived' AND OLD.status != 'archived' THEN
          SET NEW.archived_at = NOW();
      END IF;
      IF NEW.status = 'active' AND OLD.status != 'active' THEN
          SET NEW.archived_at = NULL;
      END IF;
  END ;;
  DELIMITER ;


  /*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
  /*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
  /*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
  /*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
  /*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
  /*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
  /*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
  /*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
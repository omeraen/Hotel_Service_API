INSERT INTO `room_types` (`id`, `code`) VALUES
(1, 'standard'),
(2, 'deluxe'),
(3, 'suite');


INSERT INTO `room_type_translations` (`room_type_id`, `language_code`, `name`) VALUES
(1, 'ru', 'Стандарт'), (1, 'en', 'Standard'), (1, 'uz', 'Standart'),
(2, 'ru', 'Люкс'), (2, 'en', 'Deluxe'), (2, 'uz', 'Lyuks'),
(3, 'ru', 'Апартаменты'), (3, 'en', 'Suite'), (3, 'uz', 'Apartament');


INSERT INTO `employees` (`id`, `first_name`, `last_name`, `role`, `username`, `password_hash`, `status`) VALUES
(
    1,
    'Main', 
    'Admin', 
    'admin', 
    'admin',
    '$2b$12$jYkn60cfGTdPgDJn1CVQAuxzDli4jyf1ym7T7spGEBV5zJ9jEJ0xy', 
    'active'
),
(
    2,
    'Worker', 
    'Reception', 
    'reception', 
    'reception', 
    '$2b$12$6MzyuW9aklWULzgA856OWuPr3v0G8YVbQ4CM8eUcNjm6J824uFunm',
    'active'
);

INSERT INTO `rooms` (`room_number`, `room_type_id`, `status`, `current_price_per_night`) VALUES
('1', 1, 'available', 5000.00), 
('2', 1, 'available', 5000.00), 
('3', 1, 'available', 5000.00),
('4', 1, 'available', 5000.00), 
('5', 1, 'available', 5000.00), 
('6', 1, 'available', 5500.00),
('7', 1, 'available', 5500.00), 
('8', 1, 'available', 5500.00), 
('9', 1, 'available', 5500.00),
('10', 1, 'available', 5500.00), 
('11', 1, 'available', 6000.00), 
('12', 1, 'available', 6000.00),
('13', 1, 'available', 6000.00), 
('14', 1, 'available', 6000.00), 
('15', 1, 'available', 6000.00),
('16', 1, 'available', 10000.00), 
('17', 1, 'available', 10000.00), 
('18', 1, 'available', 10000.00),
('19', 1, 'available', 10000.00), 
('20', 1, 'available', 10000.00), 
('21', 1, 'available', 12000.00),
('22', 1, 'available', 12000.00), 
('23', 1, 'available', 12000.00), 
('24', 1, 'available', 12000.00),
('25', 1, 'available', 12000.00),
('26', 1, 'available', 20000.00), 
('27', 1, 'available', 20000.00), 
('28', 1, 'available', 20000.00),
('29', 1, 'available', 20000.00), 
('30', 1, 'available', 20000.00);

-- INSERT INTO `services` (`id`, `price`, `status`) VALUES
-- (1, 1500.00, 'available'),
-- (2, 500.00, 'available');

-- INSERT INTO `service_translations` (`service_id`, `language_code`, `name`, `description`) VALUES
-- (1, 'ru', 'Завтрак в номер', 'Свежий завтрак, доставленный прямо в вашу комнату.'),
-- (1, 'en', 'Breakfast in room', 'A fresh breakfast delivered directly to your room.'),
-- (1, 'uz', 'Xonaga nonushta', 'Yangi nonushta to\'g\'ridan-to\'g\'ri xonangizga yetkazib beriladi.'),
-- (2, 'ru', 'Парковка', 'Гарантированное парковочное место на охраняемой стоянке отеля.'),
-- (2, 'en', 'Parking', 'A guaranteed parking spot in the hotel\'s secure parking lot.'),
-- (2, 'uz', 'Avtoturargoh', 'Mehmonxonaning qo\'riqlanadigan avtoturargohida kafolatlangan to\'xtash joyi.');
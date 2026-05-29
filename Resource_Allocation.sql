CREATE DATABASE support_ai;

USE DATABASE support_ai;

CREATE SCHEMA ticketing;


CREATE OR REPLACE TABLE tickets (
    subject STRING,
    body STRING,
    answer STRING,
    type STRING,
    queue STRING,
    priority STRING,
    language STRING,
    business_type STRING,
    tag_1 STRING,
    tag_2 STRING,
    tag_3 STRING,
    tag_4 STRING,
    tag_5 STRING,
    tag_6 STRING,
    tag_7 STRING,
    tag_8 STRING,
    tag_9 STRING
);

select * from tickets;


CREATE OR REPLACE TABLE support_engineers (
    engineer_id INT,
    name STRING,
    timezone STRING,
    language STRING,
    skill STRING,
    current_load INT,
    shift_start TIME,
    shift_end TIME,
    max_tickets INT
);

INSERT INTO support_engineers (
    engineer_id,
    name,
    timezone,
    language,
    skill,
    current_load,
    shift_start,
    shift_end,
    max_tickets
)
VALUES
(1, 'Rahul Sharma', 'Asia/Kolkata', 'en', 'AWS', 3, '09:00', '18:00', 10),

(2, 'Maria Garcia', 'Europe/Madrid', 'es', 'Incident', 2, '08:00', '17:00', 8),

(3, 'Lucas Silva', 'America/Sao_Paulo', 'pt', 'Software', 5, '10:00', '19:00', 12),

(4, 'Anna Muller', 'Europe/Berlin', 'de', 'Hardware', 1, '07:00', '16:00', 7),

(5, 'John Smith', 'America/New_York', 'en', 'Cloud Services', 4, '09:00', '18:00', 10),

(6, 'Mei Lin', 'Asia/Singapore', 'en', 'Technical Support', 2, '08:00', '17:00', 9),

(7, 'Carlos Rivera', 'America/Mexico_City', 'es', 'Customer Service', 3, '09:00', '18:00', 8),

(8, 'Sophie Laurent', 'Europe/Paris', 'fr', 'Hardware', 1, '08:00', '17:00', 7),

(9, 'Hiro Tanaka', 'Asia/Tokyo', 'en', 'Software', 4, '09:00', '18:00', 11),

(10, 'Fatima Khan', 'Asia/Dubai', 'en', 'Incident', 2, '07:00', '16:00', 9);



-- Basic Allocation Query
SELECT
    e.name,
    e.language,
    e.skill,
    e.current_load
FROM support_engineers e
WHERE
    LOWER(e.language) = LOWER('es')
    AND LOWER(e.skill) = LOWER('Incident')
ORDER BY e.current_load ASC
LIMIT 1;

--STEP 7 — Dynamic Allocation Query
SELECT
    t.subject,
    t.language,
    t.queue,
    e.name AS assigned_engineer,
    e.timezone,
    e.current_load
FROM tickets t
JOIN support_engineers e
ON LOWER(t.language) = LOWER(e.language)
WHERE LOWER(e.skill) LIKE '%' || LOWER(t.queue) || '%'
ORDER BY e.current_load ASC
LIMIT 10;

-- Classify tickets by priority using AI_CLASSIFY
SELECT
    subject,
    body,
    AI_CLASSIFY(
        subject || ': ' || body,
        ['urgent', 'high', 'medium', 'low']
    ):labels[0]::STRING AS predicted_priority
FROM tickets
LIMIT 10;

-- Classify tickets by queue/skill for routing
SELECT
    subject,
    body,
    AI_CLASSIFY(
        subject || ': ' || body,
        ['AWS', 'Incident', 'Software', 'Hardware', 'Cloud Services', 'Technical Support', 'Customer Service']
    ):labels[0]::STRING AS predicted_queue
FROM tickets
LIMIT 10;

-- Auto-route tickets to engineers using AI classification
SELECT
    t.subject,
    t.language,
    AI_CLASSIFY(
        t.subject || ': ' || t.body,
        ['AWS', 'Incident', 'Software', 'Hardware', 'Cloud Services', 'Technical Support', 'Customer Service']
    ):labels[0]::STRING AS predicted_queue,
    e.name AS assigned_engineer,
    e.current_load
FROM tickets t
JOIN support_engineers e
    ON LOWER(t.language) = LOWER(e.language)
WHERE LOWER(e.skill) = LOWER(
    AI_CLASSIFY(
        t.subject || ': ' || t.body,
        ['AWS', 'Incident', 'Software', 'Hardware', 'Cloud Services', 'Technical Support', 'Customer Service']
    ):labels[0]::STRING
)
ORDER BY e.current_load ASC
LIMIT 10;


SELECT SNOWFLAKE.CORTEX.COMPLETE(
'mistral-large',
'Explain why Maria Garcia is the best engineer for a high priority Spanish incident ticket'
);


SELECT
subject,
SNOWFLAKE.CORTEX.SUMMARIZE(body)
FROM tickets
LIMIT 5;

SELECT
subject,
SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
body,
['Incident','Request','Complaint']
)
FROM tickets
LIMIT 5;




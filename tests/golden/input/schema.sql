CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  name TEXT
);

CREATE PROCEDURE add_user(IN p_name TEXT)
BEGIN
  INSERT INTO users(name) VALUES (p_name);
END;

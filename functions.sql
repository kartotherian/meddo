-- These are standard stylesheet-independent functions meddo needs
CREATE OR REPLACE FUNCTION z (float)
  RETURNS INTEGER
AS $$
SELECT
    CASE
      WHEN $1 > 600000000 OR $1 = 0 THEN NULL
      ELSE CAST (ROUND(LOG(559082264.028/$1)/LOG(2.0)) AS INTEGER)
    END;
$$ LANGUAGE SQL IMMUTABLE STRICT;
-- These are standard stylesheet-independent functions meddo needs
CREATE OR REPLACE FUNCTION z (float)
  RETURNS INTEGER
AS $$
SELECT
    CASE
      WHEN $1 > 600000000 OR $1 = 0 THEN NULL
      ELSE CAST (pg_catalog.ROUND(pg_catalog.LOG(559082264.028/$1)/pg_catalog.LOG(2.0)) AS INTEGER)
    END;
$$ LANGUAGE SQL IMMUTABLE STRICT;

CREATE OR REPLACE FUNCTION node_id ( bigint )
  RETURNS BIGINT
AS $$
SELECT $1 + 1000000000;
$$ LANGUAGE SQL IMMUTABLE STRICT;

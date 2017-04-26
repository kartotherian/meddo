-- These are suggested indexes for meddo which speed up rendering with a full
-- planet database.
-- This file is generated with ./scripts/indexes.py

CREATE INDEX roads_low
  ON roads USING GIST (way)
  WHERE class >= 'tertiary';
CREATE INDEX admin_area_low
  ON admin_area USING GIST (way)
  WHERE level <= 4;
CREATE INDEX place_polygon_low
  ON place_polygon USING GIST (way)
  WHERE rank >= 'town';
CREATE INDEX place_point_low
  ON place_point USING GIST (way)
  WHERE rank >= 'town';

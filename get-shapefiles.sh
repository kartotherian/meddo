#!/usr/bin/env bash

set -e

UNZIP_OPTS=-qqun

if [ "${1}" == "create" ]; then
  SHP2PGSQL_OPERATION="-c"
  TRANSFORMATION=""
else
  SHP2PGSQL_OPERATION="-a"
  TRANSFORMATION='/^BEGIN;$/aTRUNCATE ocean_polygons;'
fi

mkdir -p data/

echo 'downloading water-polygons-split-3857...'
curl -z "data/water-polygons-split-3857.zip" -L -o "data/water-polygons-split-3857.zip" "http://data.openstreetmapdata.com/water-polygons-split-3857.zip"

unzip $UNZIP_OPTS data/water-polygons-split-3857.zip \
  water-polygons-split-3857/water_polygons.{shp,shx,prj,dbf,cpg} -d data/

shp2pgsql ${SHP2PGSQL_OPERATION} -g geom data/water-polygons-split-3857/water_polygons.shp ocean_polygons | sed "${TRANSFORMATION}" | psql -v "ON_ERROR_STOP=1" -Xq -d ct

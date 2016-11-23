# meddo

Data source for Wikipedia maps from OSM data

## Install

This style requires an osm2pgsql database loaded with [https://github.com/ClearTables/ClearTables](https://github.com/ClearTables/ClearTables) and ocean data.

### Requirements

* ClearTables v0.0.1
  The version required is subject to **rapid** change during development
* Mapnik 3.0.0 or later
* Software that can interpret YAML style definitions like Kosmtik or Mapbox Studio Classic
* osm2pgsql 0.90.1 or later with Lua support. Early C++ versions > 0.86.0 may still work with some bugs or missing data.
* PostgreSQL 9.1 or later. 9.4 or later is recommended as earlier versions are not adequately tested with the style.
* PostGIS 2.0 or later. 2.3 or later is recommended as earlier versions are not adequately tested with the style.

### Load the data with ClearTables

See the [ClearTables documentation for details](https://github.com/ClearTables/ClearTables#usage) and load into the database `ct`.

```sh
git clone -b v0.0.1 git://github.com/ClearTables/ClearTables.git
pushd ClearTables
make
createdb ct
psql -d ct -c 'CREATE EXTENSION postgis; CREATE EXTENSION hstore;'
cat sql/types/*.sql | psql -1Xq -d ct
osm2pgsql -d ct --number-processes 3 --output multi --style cleartables.json ~/path/to/extract
cat sql/post/*.sql | psql -1Xq -d ct
popd
```

Other osm2pgsql flags for performance or updates can be added, and will be necessary for large imports. See the osm2pgsql documentation for more details.
Flags that might be needed include
- `--slim`
- `--cache`
- `--flat-nodes`

Slim mode is not required by this style, so ``--slim --drop`` can be safely used if updates are not required.

If PostgreSQL [`max_connections`](http://www.postgresql.org/docs/9.3/static/runtime-config-connection.html#RUNTIME-CONFIG-CONNECTION-SETTINGS)
is increased from the default, `--number-processes` can be increased. If `--number-processes` is omitted, osm2pgsql will
attempt to use as many processes as hardware threads.

### Load coastline data

Meddo uses data from OSMCoastline, hosted on [OpenStreetMapData](http://openstreetmapdata.com/). The data used is

* Mercator projected [water polygons](http://openstreetmapdata.com/data/water-polygons)

*Script used to load TBD*

### Install required functions

Meddo requires some standard stylesheet-independent functions

```sh
psql -d ct -f functions.sql
```

## Usage

### Development

A suitable design program like Kosmtik or Mapbox Studio Classic is needed. If Kosmtik is installed, `kosmtik serve data.yml` will start Kosmtik, and the Data Inspector can be used. For Mapbox Studio, the entire repository is a tm2source project.

### Production

It might be necessary to compile the project to Mapnik XML for production, which can be done in many ways. One way is `kosmtik export data.yml --format xml --output meddo.xml`

## Schema

*TBD.*

## Why "meddo"?

[Meddo](https://en.wikipedia.org/wiki/Marshall_Islands_stick_chart#Meddo_charts) is a type of [Polynesian stick chart](https://en.wikipedia.org/wiki/Marshall_Islands_stick_chart) which contains only a section of the island chain, and meddo creates vector tiles from a larger database. It's also based on the same language as "wiki".

## License

The code is licensed under the [MIT License](LICENSE). If used as directed, use [ODbL licensed OpenStreetMap data](https://www.openstreetmap.org/copyright).

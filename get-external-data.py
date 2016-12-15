#!/usr/bin/env python3

# modules for config reading
import yaml
import os
import re
import argparse
import shutil

# modules for getting data
import zipfile
import requests
import io

# modules for converting and postgres loading
import subprocess
import psycopg2

# import logging
# import http.client as http_client
# http_client.HTTPConnection.debuglevel = 1
# 
# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger("requests.packages.urllib3")
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

def database_setup(conn, temp_schema, schema, metadata_table):
  with conn.cursor() as cur:
      cur.execute('''CREATE SCHEMA IF NOT EXISTS {temp_schema};'''.format(temp_schema=temp_schema))
      cur.execute('''CREATE TABLE IF NOT EXISTS "{schema}"."{metadata_table}" (name text primary key, last_modified text);'''
                    .format(schema=schema, metadata_table=metadata_table))
  conn.commit()
def table_index(conn, name, temp_schema):
  with conn.cursor() as cur:
    # ogr creates a ogc_fid column we don't need
    cur.execute('''ALTER TABLE "{temp_schema}"."{name}" DROP COLUMN ogc_fid;'''.format(name=name, temp_schema=temp_schema))

    # sorting static tables helps performance and reduces size from the column drop above
    # see osm2pgsql for why this particular geohash invocation
    cur.execute('''CREATE INDEX "{name}_geohash"
                    ON "{temp_schema}"."{name}"
                    (ST_GeoHash(ST_Transform(ST_Envelope(way),4326),10) COLLATE "C")'''
                  .format(name=name, temp_schema=temp_schema))
    cur.execute('''CLUSTER "{temp_schema}"."{name}" USING "{name}_geohash"'''.format(name=name, temp_schema=temp_schema))
    cur.execute('''DROP INDEX "{temp_schema}"."{name}_geohash"'''.format(name=name, temp_schema=temp_schema))

    # Standard geom index
    cur.execute('''CREATE INDEX ON "{temp_schema}"."{name}" USING GIST (way) WITH (fillfactor=100)'''.format(name=name, temp_schema=config["settings"]["temp_schema"]))
    cur.execute('''ANALYZE "{temp_schema}"."{name}"'''.format(name=name, temp_schema=config["settings"]["temp_schema"]))
  conn.commit()

def table_replace(conn, name, metadata_table, temp_schema, schema, new_last_modified):
  with conn.cursor() as cur:
    cur.execute('''BEGIN;''')
    cur.execute('''DROP TABLE IF EXISTS "{schema}"."{name}"'''.format(name=name, schema=schema))
    cur.execute('''ALTER TABLE "{temp_schema}"."{name}" SET SCHEMA "{schema}"'''
      .format(name=name, temp_schema=temp_schema, schema=schema))

    # We checked if the metadata table had this table way up above
    cur.execute('''SELECT 1 FROM "{schema}"."{metadata_table}" WHERE name = %s'''.format(schema=schema, metadata_table=metadata_table), [name])
    if cur.rowcount == 0:
      cur.execute('''INSERT INTO "{schema}"."{metadata_table}" (name, last_modified) VALUES (%s, %s)'''.format(schema=schema, metadata_table=metadata_table),
                    [name, new_last_modified])
    else:
      cur.execute('''UPDATE "{schema}"."{metadata_table}" SET last_modified = %s WHERE name = %s'''.format(schema=schema, metadata_table=metadata_table),
                    [new_last_modified, name])
  conn.commit()

if __name__ == '__main__':
  # parse options
  parser = argparse.ArgumentParser(description="Load external data into a database")
  
  parser.add_argument("-f", "--force", action="store_true", help="Download new data, even if not required")
  
  parser.add_argument("-d", "--database", action="store", help="Override database name to connect to")
  parser.add_argument("-H", "--host", action="store", help="Override database server host or socket directory")
  parser.add_argument("-p", "--port", action="store", help="Override database server port")
  parser.add_argument("-U", "--username", action="store", help="Override database user name")
  
  opts = parser.parse_args()
  with open('external-data.yml') as config_file:
    config = yaml.safe_load(config_file)
    os.makedirs(config["settings"]["data_dir"], exist_ok=True)

    database = opts.database or config["settings"].get("database")
    host = opts.host or config["settings"].get("host")
    port = opts.port or config["settings"].get("port")
    user = opts.username or config["settings"].get("username")
    with requests.Session() as s, \
         psycopg2.connect(database=database,
                          host=host,
                          port=port,
                          user=user) as conn:

      s.headers.update({'User-Agent': 'get-external-data.py/meddo'})
      
      # DB setup
      database_setup(conn, config["settings"]["temp_schema"], config["settings"]["schema"], config["settings"]["metadata_table"])

      for name, source in config["sources"].items():
        # Don't attempt to handle strange names
        # you don't want them when writing a style with all the quoting headaches
        if not re.match('''^[a-zA-Z0-9_]+$''', name):
          raise RuntimeError("Only ASCII alphanumeric table names supported")

        workingdir = os.path.join(config["settings"]["data_dir"], name)
        # Clean up anything left over from an aborted run
        shutil.rmtree(workingdir, ignore_errors=True)

        os.makedirs(workingdir, exist_ok=True)

        with conn.cursor() as cur:
          cur.execute('''DROP TABLE IF EXISTS "{}"."{}"'''.format(config["settings"]["temp_schema"],name))
          # should lock the row for update
          cur.execute('''SELECT last_modified FROM "{schema}"."{metadata_table}" WHERE name = %s'''.format_map(config["settings"]), [name])
          results = cur.fetchone()
          if results is not None:
            last_modified = results[0]
          else:
            last_modified = None
        conn.commit()

        if not opts.force:
          headers = {'If-Modified-Since': last_modified}
        else:
          headers = {}

        download = s.get(source["url"], headers=headers)
        download.raise_for_status()

        if (download.status_code == 200):
          if "Last-Modified" in download.headers:
            new_last_modified = download.headers["Last-Modified"]
          else:
            new_last_modified = None
          if "archive" in source and source["archive"]["format"] == "zip":
            zip = zipfile.ZipFile(io.BytesIO(download.content))
            for member in source["archive"]["files"]:
              zip.extract(member, workingdir)

          ogrpg = "PG:dbname={}".format(database)

          if port is not None:
            ogrpg = ogrpg + " port={}".format(port)
          if user is not None:
            ogrpg = ogrpg + " user={}".format(user)
          if host is not None:
            ogrpg = ogrpg + " host={}".format(host)

          ogrcommand = ["ogr2ogr",
                        '-f', 'PostgreSQL',
                        '-lco', 'GEOMETRY_NAME=way',
                        '-lco', 'SPATIAL_INDEX=FALSE',
                        '-lco', 'EXTRACT_SCHEMA_FROM_LAYER_NAME=YES',
                        '-nln', "{}.{}".format(config["settings"]["temp_schema"], name),
                        ogrpg, os.path.join(workingdir, source["file"])]
          print ("running {}".format(subprocess.list2cmdline(ogrcommand)))

          # need to catch errors here
          try:
            ogr2ogr = subprocess.run(ogrcommand, stderr=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True, check=True)
            # Cleanup
            shutil.rmtree(workingdir, ignore_errors=True)
          except subprocess.CalledProcessError as e:
            print ("ogr2ogr returned {} with layer {}".format(e.returncode, name))
            print ("Command line was {}".format(subprocess.list2cmdline(e.cmd)))
            print ("Output was\n{}".format(e.output))
            raise RuntimeError("Unable to load table {}".format(name))

          table_index(conn, name, config["settings"]["temp_schema"])
          table_replace(conn, name, config["settings"]["metadata_table"], config["settings"]["temp_schema"], config["settings"]["schema"], new_last_modified)
        else:
          print("Table {} did not require updating".format(name))

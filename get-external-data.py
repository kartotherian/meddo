#!/usr/bin/env python3

# modules for config reading
import yaml
import os
import re
import argparse

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

if __name__ == '__main__':
  # parse options
  parser = argparse.ArgumentParser(description="Load external data into a database")
  
  parser.add_argument("-f", "--force", action="store_true", help="Download new data, even if not required")
  
  parser.add_argument("-d", "--database", action="store", help="Override database name to connect to")
  parser.add_argument("-H", "--host", action="store", help="Override database server host or socket directory")
  parser.add_argument("-p", "--port", action="store", help="Override database server port")
  parser.add_argument("-U", "--username", action="store", help="Override database user name")
  
  opts = parser.parse_args()
  print (opts)
  with open('external-data.yml') as config_file:
    config = yaml.safe_load(config_file)
    os.makedirs(config["settings"]["data_dir"], exist_ok=True)

    with requests.Session() as s, \
         psycopg2.connect(database=opts.database or config["settings"].get("database"),
                          host=opts.host or config["settings"].get("host"),
                          port=opts.port or config["settings"].get("port"),
                          user=opts.username or config["settings"].get("username")) as conn:

      s.headers.update({'User-Agent': 'get-external-data.py/meddo'})
      
      # DB setup
      with conn.cursor() as cur:
          cur.execute('''CREATE SCHEMA IF NOT EXISTS {temp_schema};'''.format_map(config["settings"]))
          cur.execute('''CREATE TABLE IF NOT EXISTS "{schema}"."{metadata_table}" (name text primary key, last_modified text);'''.format_map(config["settings"]))
      conn.commit()
      
      
      for name, source in config["sources"].items():
        # Don't attempt to handle strange names
        # you don't want them when writing a style with all the quoting headaches
        if not re.match('''^[a-zA-Z0-9_]+$''', name):
          raise RuntimeError("Only ASCII alphanumeric table names supported")

        workingdir = os.path.join(config["settings"]["data_dir"], name)
        os.makedirs(workingdir, exist_ok=True)

        print(source)
        with conn.cursor() as cur:
          # should lock the row for update
          cur.execute('''SELECT last_modified FROM "{schema}"."{metadata_table}" WHERE name = %s'''.format_map(config["settings"]), [name])
          results = cur.fetchone()
          if results is not None:
            last_modified = results[0]
          else:
            last_modified = None

        conn.commit()

        headers = {'If-Modified-Since': last_modified}
        print(headers)
        download = s.get(source["url"], headers=headers)
        print(download.status_code)
        print(download.headers)

        download.raise_for_status()
        if (download.status_code == 200 or opts.force):
          if "Last-Modified" in download.headers:
            new_last_modified = download.headers["Last-Modified"]
          else:
            new_last_modified = None
          if "archive" in source and source["archive"]["format"] == "zip":
            zip = zipfile.ZipFile(io.BytesIO(download.content))
            print(zip.namelist())
            for member in source["archive"]["files"]:
              zip.extract(member, workingdir)
        else:
          print("Table {} did not require updating".format(name))
        
        # http://docs.python-requests.org/en/master/user/quickstart/#raw-response-content for saving a file
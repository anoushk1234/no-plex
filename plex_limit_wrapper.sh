#! /bin/sh
exec 200>/tmp/plex_limit.lock
flock -n 200 || exit 1

/usr/bin/python3 /path/to/your/folder/plex-limit-state.py

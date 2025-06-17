# No Plex
This is a repo of scripts that do automation in my life for various apps or home stuff.


Currently plex doesnt have an apple screen time like feature so I built plex-limit-state.py
which tracks how much plex youre watching and kills streams if u exceed.

There are existing solutions like JBOPS but they dont do it like
apple screen time where if u exceed the limit while watching the movie, screen time
will stop the app where as JBOPS wont.

Requirements:
- sqlite
- tautulli
- python

I have used systemd to run it every 5s.
/etc/systemd/system/plex-limit.timer
/etc/systemd/system/plex-limit.service

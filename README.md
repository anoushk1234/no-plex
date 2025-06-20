# no-plex

`no-plex` is a daemon that monitors Plex sessions via the Tautulli API and automatically terminates streams based on configurable limits similar to Apple's Screen Time. It helps you enforce intentional media usage by restricting watch time per session, per day, and across specific hours so you can reduce passive consumption and gain focus.

Unlike existing solutions (e.g. JBOPS), it actively monitors stream duration and forcefully terminates sessions once limits are exceeded — even mid-playback.

## Features
 
- Session enforcement:
  - Daily total watch time limit (e.g., 60 minutes)
  - Per-session watch limit (e.g., 30 minutes max per session)
- Time-of-day blocking (e.g., restrict streaming between 10:30 PM and 1:00 PM)
- SQLite-based session tracking so sessions are tracked even while watching unlike JBOPS.
- Includes one off day( Sunday )
- Systemd + timer-based execution every 5 seconds so it works even with reboots.

## Requirements

- Plex Media Server
- [Tautulli](https://github.com/Tautulli/Tautulli) (API access enabled)
- Python 3.9+
- Linux system with `systemd`
- `flock`, `iptables`, `sqlite3` (all standard on most distros)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/anoushk1234/no-plex.git
cd no-plex
chmod +x plex-limit-state.py plex_limit_wrapper.sh
```

### 2. Configure Environment

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set:

- `TAUTULLI_URL`: your local or remote Tautulli API URL (e.g. `http://127.0.0.1:8181`)
- `TAUTULLI_API_KEY`: your Tautulli API key
- `KILL_MESSAGE`: Optional, The message shown when your stream is killed.
- `MAX_TOTAL_MINUTES`: total watch time allowed per day
- `MAX_SESSION_DURATION_MINUTES`: maximum allowed per-session duration
- `ENABLE_BEDTIME`: Optional to block plex during sleep time

These values are loaded automatically by `plex-limit-state.py`.

## Configure systemd

### 1. Edit `plex_limit_wrapper.sh`

Update the path:

```bash
/usr/bin/python3 /absolute/path/to/no-plex/plex-limit-state.py
```

Make it executable:

```bash
chmod +x plex_limit_wrapper.sh
```

### 2. Install the systemd service

Update `ExecStart` in `plex-limit.service` to point to the absolute path of `plex_limit_wrapper.sh`.

```ini
ExecStart=/home/youruser/no-plex/plex_limit_wrapper.sh
```

Then:

```bash
sudo cp plex-limit.service /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl enable plex-limit.service
```

### 3. Configure the timer

The timer is already configured to run every 5 seconds:

```ini
[Timer]
OnBootSec=2min
OnUnitActiveSec=5s
AccuracySec=1s
Persistent=false
```

Install:

```bash
sudo cp plex-limit.timer /etc/systemd/system/
sudo systemctl daemon-reexec
sudo systemctl enable plex-limit.timer
sudo systemctl start plex-limit.timer
```

## Optional: Bedtime Limit
If you want to turn off Plex usage during certain times set:
```.env
ENABLE_BEDTIME=1
```

The default time is 10:30 PM to 1:00pm but you can change it here:
```py
def is_blocked_time():
    now = datetime.now().time()
    return now >= dtime(22, 30) or now < dtime(13, 0) # Change time here
```

## Debugging

- Log file:  
  `plex_session_tracker.log` (in the script directory)

- SQLite database for sessions:  
  `plex_session_tracker.db` (also local)

These files are created automatically.

## Cleanup and Session Accuracy

At 23:59 daily, old session data is purged to allow accurate tracking the next day. Session duration is measured and stored even if playback is interrupted or restarted. 

The script correctly handles cases where Plex reuses the same session ID or media `rating_key` by using composite keys and time delta validation.

## License

MIT License. See `LICENSE` file for details.


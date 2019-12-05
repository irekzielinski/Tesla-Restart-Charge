# Tesla-Restart-Charge
Script to auto-restart charging at night. This is to fix issue with charging stuck at 16amp when more is available.

See this thread for more details:
https://www.speakev.com/threads/home-charging-amperage.145403/post-2748951

To get going:
* install this library: https://github.com/gglockner/teslajson
* download tesla-bump-charge2.py and modify it with your tesla account credentails
* run the script in crontab, some time before sheduled charge time set in your car (at least 15 minutes ahead)

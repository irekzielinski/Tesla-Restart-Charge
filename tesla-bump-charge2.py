import teslajson
import time
import json
import sys
from datetime import datetime

#NOTE: Script installed in crontab to run on 0:30 local time (too early in the summer, but that's OK)

class Unbuffered(object):
    nl = True
    
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        if data == 'n':
            self.stream.write(data)
            self.nl = True
        elif self.nl:
            self.stream.write('%s> %s' % (datetime.now().strftime("%d %H:%M:%S"), data))
            self.nl = False
        else:
            self.stream.write(data)
            
        self.stream.flush()
    def writelines(self, datas):
        self.stream.write('%s> ', datetime.now().strftime("%d %H:%M:%S"))
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

t_log = "YOUR TESLA LOGIN"
t_pass = "YOUR TESLA PASSWORD"
ahead_sec = 11*60 #start script 11 minutes before car scheduled charge
#sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)

def lprint(s):
    print('%s> %s' % (datetime.now().strftime("%d %H:%M:%S"), s))
    sys.stdout.flush()

def wake_car(v):
    wakeState = v.wake_up()["response"]

    for x in range(4):
        if wakeState["state"] == "online":
            lprint( "Car is online" )
            break
    
        lprint( "Car not awake, sleeping for 30s" )
        time.sleep(30)
        wakeState = v.wake_up()["response"]

    if wakeState["state"] != "online":
        sys.exit("exit: Unable to contact the car")


def get_car_ct():
    #if you have CT clamp- put your code here, or leave 0
    return 0

def wait_90s_for_20_amps(v):
    for x in range(30):
        time.sleep(3)
        cs = v.data_request('charge_state')
        cRate = float(cs["charge_rate"]) #charge rate can be lower than current - due to battery heater?
        current = int(cs["charger_actual_current"])
        volt = int(cs["charger_voltage"])
        pilot = int(cs["charger_pilot_current"])
        cReq = int(cs["charge_current_request"])
        min_to_full = int(cs["minutes_to_full_charge"])
        ct = get_car_ct()
        if x == 5 and cs["battery_heater_on"]:
            lprint("**** Battery Heater is ON ****")
        #set for 25amp or 5750w
        if current > 20 or ct > 5000:
            lprint("Current  OK: {0}amp @ {1}V | ct:{2}w | req:{3}/max:{4}/charge-rate:{5} | time-to-full:{6}".format(current, volt, ct, cReq, pilot, cRate, min_to_full))
            return True
        else:
            lprint("Current LOW: {0}amp @ {1}V | ct:{2}w | req:{3}/max:{4}/charge-rate:{5} | time-to-full:{6}".format(current, volt, ct, cReq, pilot, cRate, min_to_full))

        #if after 10 iterations, we still have a low requested rate, we will abort early so restart can happen
        if x > 7 and cReq < 20:
            lprint("Requested charge rate is {0} of max {1}amp available - no point waiting any more".format(cReq, pilot))
            break
    return False

def monitor_charge_for_2m(v):
    for x in range(6*2):
        time.sleep(10)
        cs = v.data_request('charge_state')
        cRate = float(cs["charge_rate"])
        current = int(cs["charger_actual_current"])
        volt = int(cs["charger_voltage"])
        min_to_full = int(cs["minutes_to_full_charge"])
        ct = get_car_ct()
        lprint("Charge rate at: {0}amp | {1}V | CT: {2}w | Actual current: {3}amp | time-to-full: {4}".format(cRate, volt, ct, current, min_to_full))

lprint("Checking if start-charge is scheduled")

#getting scheduled charge time and wake up 10 minutes before hand
c = teslajson.Connection(t_log, t_pass)
v = c.vehicles[0]
wake_car(v)
cs = v.data_request('charge_state')
start_time = cs["scheduled_charging_start_time"]

if start_time is None:
    sys.exit("exit: No scheduled charge or not connected")

epoch_now = int(time.time())
time_to_go = start_time - epoch_now
lprint("Seconds before scheduled charge: {0}".format(time_to_go))

if time_to_go < ahead_sec:
    sys.exit("exit: not enough time before scheduled charge - min 10min required")

time_to_sleep = time_to_go - ahead_sec
lprint("Sleeping for {0} seconds before starting charge".format(time_to_sleep))

time.sleep(time_to_sleep)

lprint("Sleep complete - connecting to Tesla to start the charge")
c = teslajson.Connection(t_log, t_pass)
v = c.vehicles[0]
wake_car(v)

#Check if connected and NOT charging:
cs = v.data_request('charge_state')
bat_soc = int(cs["usable_battery_level"])
bat_max = int(cs["charge_limit_soc"])
lprint("SOC: {0} up to: {1}".format(bat_soc, bat_max))

if bat_soc >= bat_max or bat_max - bat_soc < 10:
    sys.exit("exit: SOC high enough, no charge needed")

if cs["charging_state"] == "Charging":
    sys.exit("exit: Car is already charging")
if cs["charging_state"] == "Disconnected":
    sys.exit("exit: Car is not connected")
    
time.sleep(5)
lprint ("Starting charge")
res = v.command('charge_start')

if res["response"]["result"] == True:
    lprint ("Charge started OK")
else:
    lprint ("Charge start failed. Reason: {0}".format(res["response"]["reason"]))
    sys.exit("exit: Cant start charge")
    
#check if charge speed is OK:
for x in range(3):
    if wait_90s_for_20_amps(v):
        monitor_charge_for_2m(v)
        #finaly print current raw data
        cs = v.data_request('charge_state')
        print(json.dumps(cs, indent=2, sort_keys=False))
        sys.exit(0)
    else:
        lprint("Charge rate is NOT OK - restarting")
        v.command('charge_stop')
        time.sleep(10)
        v.command('charge_start')


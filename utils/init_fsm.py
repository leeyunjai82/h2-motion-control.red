from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient
from unitree_sdk2py.core.channel import ChannelFactoryInitialize
import time
import sys

def setfsmid(n):
    print(f"[setfsmid-START]: id({n})")
    res = loco_client.SetFsmId(n)
    print(f"[setfsmid-END]: Result({res})")

if len(sys.argv) < 2 or sys.argv[1] not in ("stand", "sit", "bal", "no-bal"):
    print("Usage: python init_fsm.py [stand|sit]")
    sys.exit(1)

mode = sys.argv[1]

ChannelFactoryInitialize(0)
loco_client = LocoClient()
loco_client.Init()
loco_client.SetTimeout(10.0)

# H2 FSM ID: 0=ZeroTorque, 1=Damp, 2=Squat, 3=Sit, 4=StandUp, 601=Start(balance)
# (G1의 501 대신 H2는 601 사용)
if mode == "stand":
    setfsmid(1)
    time.sleep(5)
    setfsmid(4)
    time.sleep(10)
    setfsmid(601)
elif mode == "sit":
    time.sleep(3)
    setfsmid(3)
elif mode == "bal":
    time.sleep(3)
    setfsmid(601)
elif mode == "no-bal":
    time.sleep(3)
    setfsmid(4)

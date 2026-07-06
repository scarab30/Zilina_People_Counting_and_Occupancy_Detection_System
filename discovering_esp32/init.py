import time
from machine import Pin

led = Pin(21, Pin.OUT)
led.value(0)
time.sleep(3)
led.value(1)

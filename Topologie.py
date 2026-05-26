#!/opt/copilot-env/bin/python3
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info
import time

SCENARIO = {
"latence_ms" : 0,
"perte_pct" : 0,
"bande_kbps" : 0,
"mobilite" : False
}

def appliquer_degradation(station, iface):
	lat = SCENARIO["latence_ms"]
	loss = SCENARIO["perte_pct"]
	bw = SCENARIO["bande_kbps"]
	if lat > 0 and loss > 0:
		station.cmd(f"tc qdisc add dev {iface} root netem delay {lat}ms loss {loss}%")
	elif lat > 0:
		station.cmd(f"tc qdisc add dev {iface} root netem delay {lat}ms")
	elif loss > 0:
		station.cmd(f"tc qdisc add dev {iface} root netem loss {loss}%")
	elif bw > 0:
		station.cmd(f"tc qdisc add dev {iface} root tbf rate {bw}kbit burst 32kbit latency
400ms")

def run():
	setLogLevel('info')
	net = Mininet_wifi(link=wmediumd, wmediumd_mode=interference)

	info("*** CrÃ©ation des stations\n")
	truck = net.addStation('truck', ip='10.0.0.1/8', position='10,50,0')
	car = net.addStation('car', ip='10.0.0.2/8', position='50,50,0')

	info("*** CrÃ©ation du point d'accÃ ̈s\n")
	ap1 = net.addAccessPoint('ap1', ssid='copilot-net', mode='g',
						channel='1', position='30,50,0', range=30)
	if SCENARIO["mobilite"]:
		ap2 = net.addAccessPoint('ap2', ssid='copilot-net', mode='g',
					channel='6', position='70,50,0', range=60)

	net.startMobility(time=0)
	net.addController('c0')
	net.configureWifiNodes()
	net.addLink(truck, ap1)
	net.addLink(car, ap1)

	net.mobility(truck, 'start', time=1, position='10,50,0')
	net.mobility(truck, 'stop', time=20, position='80,50,0')
	net.startMobility(time=0)



	info("*** DÃ©marrage\n")
	net.build()
	net.start()
	time.sleep(2)

	appliquer_degradation(truck, 'truck-wlan0')

	net.plotGraph(max_x=100, max_y=100)
	CLI(net)
	net.stop()

if __name__ == '__main__':
run()

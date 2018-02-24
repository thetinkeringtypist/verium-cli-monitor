#!/usr/bin/env python3
#
#! Author: Bezeredi, Evan D.
#
#! Script that replies with miner info in a readable format for requesters.
#  Run as a daemon after both cpuminers start.
#
#! For use with Fireworm71's Verium Miner, API Version 1.1
#
#! Configured to monitor two running instances of cpuminer, one on port 4048
#  and another on port 4049. This script consolodates info from both miners
#  and replies to any requests from the monitor. The cpuminers need to have
#  already have started. Add a line in your rc.local to run this script in the
#  background after your cpuminers.
import zmq
import socket as pysocket
import sys
import signal
import time


#! Setup localhost socket information
host = pysocket.gethostname()
port_3way = 4048
port_1way = 4049
buffer_size = 4096
socket_3way = None
socket_1way = None


#! Setup ZMQ socket
context = zmq.Context()
zmqsocket = context.socket(zmq.REP)


#! Create signal handlers
def signal_handler(signal, frame):
	context.destroy()
	socket_3way.shutdown(2)
	socket_1way.shutdown(2)
	socket_3way.close()
	socket_1way.close()
	sys.exit()


def process_zmqmsg():
	while True:
		cmd = zmqsocket.recv_string()

		#! Establish socket connections with the miners
		socket_3way = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_STREAM)
		socket_1way = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_STREAM)
		socket_3way.connect((host, port_3way))
		socket_1way.connect((host, port_1way))

		#! Send summary command
		socket_3way.send(cmd.encode())
		socket_1way.send(cmd.encode())

		#! Get data from the miners
		data_3way = socket_3way.recv(buffer_size).decode().split(";")
		data_1way = socket_1way.recv(buffer_size).decode().split(";")

		#! Close sockets
		socket_3way.shutdown(2)
		socket_1way.shutdown(2)
		socket_3way.close()
		socket_1way.close()

		#! CPUs in use
		cpus_3way = int(data_3way[4].split("=")[1])
		cpus_1way = int(data_1way[4].split("=")[1])
		cpus = cpus_3way + cpus_1way

		#! Hashes per minute
		khps_3way = float(data_3way[5].split("=")[1])
		khps_1way = float(data_1way[5].split("=")[1])
		hpm = (khps_3way + khps_1way) * 1000 * 60
	
		#! Number of solved blocks
		solved_3way = int(data_3way[6].split("=")[1])
		solved_1way = int(data_1way[6].split("=")[1])
		solved_blocks = solved_3way + solved_1way

		#! Accepted shares
		accepted_3way = int(data_3way[7].split("=")[1])
		accepted_1way = int(data_1way[7].split("=")[1])
		accepted_shares = accepted_3way + accepted_1way

		#! Rejected Shares
		rejected_3way = int(data_3way[8].split("=")[1])
		rejected_1way = int(data_1way[8].split("=")[1])
		rejected_shares = rejected_3way + rejected_1way
	
		#! Difficulties
		diff_3way = float(data_3way[10].split("=")[1])
		diff_1way = float(data_1way[10].split("=")[1])
		difficulty = diff_3way if diff_3way >= diff_1way else diff_1way

		#! CPU Tempterature
		temp_3way = float(data_3way[11].split("=")[1])
		temp_1way = float(data_1way[11].split("=")[1])
		cpu_temp = temp_3way if temp_3way >= temp_1way else temp_1way

		#! Uptime
		uptime_3way = int(data_3way[14].split("=")[1])
		uptime_1way = int(data_1way[14].split("=")[1])
		uptime = uptime_3way if uptime_3way >= uptime_1way else uptime_1way

		reply = "host=%s,cpus=%d,hpm=%f,solved_blocks=%d,accepted_shares=%d,rejected_shares=%d,difficulty=%f,cpu_temp=%f,uptime=%d" % (host, cpus, hpm, solved_blocks, accepted_shares, rejected_shares, difficulty, cpu_temp, uptime)

		#! Send reply to request
		zmqsocket.send_string(reply)
	return
	

#! Program entrance point
def main():
	#! Initialize
	zmqsocket.bind("tcp://*:5048")
	signal.signal(signal.SIGTERM, signal_handler)

	#! Create thread and start
	time.sleep(2)
	process_zmqmsg()
	return

if __name__ == "__main__":
	main()

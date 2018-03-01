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
#  and another on port 4049. This script consolodates info from each miner
#  and replies to any requests from the monitor. The cpuminers need to have
#  already have started. Add a line in your rc.local to run this script in the
#  background after your cpuminers.
import zmq
import socket as pysocket
import signal
import time


#! Setup localhost socket information
host = pysocket.gethostname()
buffer_size = 4096
sockets = []
ports = [4048, 4049]   #! NOTE: Change port numbers to those in use by your miners
summary_points = []
thread_points = []


#! Setup ZMQ socket
context = zmq.Context()
zmqsocket = context.socket(zmq.REP)


#! Create signal handlers
def signal_handler(signal, frame):
	context.destroy()
	for socket in sockets:
		socket.close()
	exit()


#! Process message from monitor
def process_zmqmsg():
	while True:
		#! Receive command from monitor
		cmd = zmqsocket.recv_string()

		#! Send command to miner
		if cmd == "summary":
			zmqsocket.send_string(get_summary_string())
			continue

		if cmd == "threads":
			zmqsocket.send_string(get_thread_string())

	return
	

#! Get summary data from miners
def get_summary_string():
	summary_points.clear() #! Clear out all stale summary data

	for port in ports:
		socket = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_STREAM)
		socket.connect((host, port))

		#! Get data from the miners
		socket.send("summary".encode())
		recvstr = socket.recv(buffer_size).decode()
		parse_summarystr(recvstr)
		
		socket.close()
	
	#! Consolodate information
#	host     = summary_points[0][0]
	name     = summary_points[0][1]
	version  = summary_points[0][2]
	api      = summary_points[0][3]
	algo     = summary_points[0][4]
	cpus     = sum(i for _,_,_,_,_,i,_,_,_,_,_,_,_,_,_,_,_ in summary_points)
	khps     = sum(i for _,_,_,_,_,_,i,_,_,_,_,_,_,_,_,_,_ in summary_points)
	solved   = sum(i for _,_,_,_,_,_,_,i,_,_,_,_,_,_,_,_,_ in summary_points)
	accepted = sum(i for _,_,_,_,_,_,_,_,i,_,_,_,_,_,_,_,_ in summary_points)
	rejected = sum(i for _,_,_,_,_,_,_,_,_,i,_,_,_,_,_,_,_ in summary_points)
	accpm    = sum(i for _,_,_,_,_,_,_,_,_,_,i,_,_,_,_,_,_ in summary_points)
	diff     = max(i for _,_,_,_,_,_,_,_,_,_,_,i,_,_,_,_,_ in summary_points)
	cpu_temp = max(i for _,_,_,_,_,_,_,_,_,_,_,_,i,_,_,_,_ in summary_points)
	cpu_fan  = max(i for _,_,_,_,_,_,_,_,_,_,_,_,_,i,_,_,_ in summary_points)
	cpu_freq = max(i for _,_,_,_,_,_,_,_,_,_,_,_,_,_,i,_,_ in summary_points)
	uptime   = max(i for _,_,_,_,_,_,_,_,_,_,_,_,_,_,_,i,_ in summary_points)
	time_sec = max(i for _,_,_,_,_,_,_,_,_,_,_,_,_,_,_,_,i in summary_points)

	#! Build the response string
	datastr  = "HOST={0};NAME={1};VER={2};".format(host, name, version)
	datastr += "API={0};ALGO={1};CPUS={2};".format(api, algo, cpus)
	datastr += "KHS={0};SOLV={1};ACC={2};".format(khps, solved, accepted)
	datastr += "REJ={0};ACCMN={1};DIFF={2};".format(rejected, accpm, diff)
	datastr += "TEMP={0};FAN={1};FREQ={2};".format(cpu_temp, cpu_fan, cpu_freq)
	datastr += "UPTIME={0};TS={1}".format(uptime, time_sec)

	return datastr


#! Parse the thread output from the miner
def parse_summarystr(recvstr):
	datastr = recvstr.rsplit('|')[0]
	summary_data_list = datastr.split(';')
	name     =       summary_data_list[ 0].split('=')[1]
	version  =       summary_data_list[ 1].split('=')[1]
	api      =       summary_data_list[ 2].split('=')[1]
	algo     =       summary_data_list[ 3].split('=')[1]
	cpus     = int(  summary_data_list[ 4].split('=')[1])
	khps     = float(summary_data_list[ 5].split('=')[1])
	solved   = int(  summary_data_list[ 6].split('=')[1])
	accepted = int(  summary_data_list[ 7].split('=')[1])
	rejected = int(  summary_data_list[ 8].split('=')[1])
	accpm    = float(summary_data_list[ 9].split('=')[1])
	diff     = float(summary_data_list[10].split('=')[1])
	cpu_temp = float(summary_data_list[11].split('=')[1])
	cpu_fan  = int(  summary_data_list[12].split('=')[1])
	cpu_freq = int(  summary_data_list[13].split('=')[1])
	uptime   = int(  summary_data_list[14].split('=')[1])
	time_sec = int(  summary_data_list[15].split('=')[1])

	#! Construct data point
	summary_point = (
		host, name, version,
		api, algo, cpus,
		khps, solved, accepted,
		rejected, accpm, diff,
		cpu_temp, cpu_fan, cpu_freq,
		uptime, time_sec)

	summary_points.append(summary_point)

	return


#! Get thread data from miners
def get_thread_string():
	for cpu_list in thread_points:
		cpu_list.clear()
	thread_points.clear() #! Clear out all stale summary data

	for port in ports:
		socket = pysocket.socket(pysocket.AF_INET, pysocket.SOCK_STREAM)
		socket.connect((host, port))

		#! Get data from the miners
		socket.send("threads".encode())
		recvstr = socket.recv(buffer_size).decode()
		parse_threadstr(recvstr)
		
		socket.close()
	
	#! Correct CPU numbers
	i = 0
	for cpu_info in thread_points:
		cpu_info[0] = i
		i += 1

	#! Build the response string
	datastr = "HOST={0}|".format(host)
	for thread_info in thread_points:
		datastr += "CPU={0};KHS={1}|".format(thread_info[0], thread_info[1])

	return datastr


#! Parse the thread output from the miner
def parse_threadstr(recvstr):
	thread_data_list = recvstr.split('|')
	for thread_data in thread_data_list:
		cpu_info = thread_data.split(';')
		cpu_num = int(cpuinfo[0].split('=')[1])
		khps    = float(cpuinfo[1].split('=')[1])
		thread_points.append((cpu_num, khps))


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

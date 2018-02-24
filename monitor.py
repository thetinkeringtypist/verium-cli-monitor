#!/usr/bin/env python3
#
#! Author: Bezeredi, Evan D.
#
#! CLI Monitor to display cpuminer information for each worker on the LAN
#
#! NOTE: Requires a list of hostnames on the LAN in /home/<username>/.chosts
#        Also requires miner-apid.py to run on each worker.
#
#! I have this script running on my LAN controller so that finding each machine
#  on the LAN is not a problem
import zmq
import time
import sys
import signal
import threading
import curses
from curses import wrapper
from pathlib import Path


#! Thread variables
threads = []
kill_threads = threading.Event()

#! ZMQ variables
context = zmq.Context()
zmqsockets = []


#! Display varaibles
input_thread = threading.Thread()
stdscr = curses.initscr()
hosts = []
statstrs = []
cpus_list = []
hashrates = []
share_percents = []
solved_blocks_list = []
difficulties = []
cpu_temps = []


#! Initialize display variables
def init_display():
	curses.noecho()
	curses.cbreak()
	stdscr.keypad(True)
	stdscr.nodelay(True)
	curses.curs_set(0)
	stdscr.clear()
	for host in hosts:
		string = "{0:<8}   ----.--- H/m   ---.--%   ------   -.-------- │ ----  ---.-°C".format(host)
		statstrs.append(string)

	return


#! Initialize value lists
def init_lists():
	for host in hosts:
		cpus_list.append(0)
		hashrates.append(0.0)
		share_percents.append(0.0)
		solved_blocks_list.append(0)
		difficulties.append(0)
		cpu_temps.append(0.0)
	return


#! Initialize zmqsockets
def init_zmqsockets():
	context = zmq.Context()
	for host in hosts:
		s = context.socket(zmq.REQ)
		s.connect("tcp://%s:5048" % host)
		zmqsockets.append(s)
	return


#! Create signal handler
def signal_handler(signal, frame):
	kill_program()


#! Kill program
def kill_program():
	#! Kill Threads
	kill_threads.set()
	for t in threads:
		t.join()
	
	#! Kill curses stuff
	curses.nocbreak()
	stdscr.keypad(False)
	curses.echo()
	curses.endwin()
	#! Kill ZMQ stuff

	for zmqsocket in zmqsockets:
		zmqsocket.close()
	context.term()

	sys.exit()


#! Process messages from a zmqsocket
def process_zmqmsg(stop_event, zmqsocket, host):
	socket = zmqsocket
	timeout = 0
	
	while not stop_event.is_set():
		time.sleep(0.5)

		socket.send_string("summary")
		msg = socket.recv_string()
		parse_zmqmsg(msg)
	return


#! Parse message received from server
def parse_zmqmsg(msg):
	items = msg.split(",")

	#! Get the index of the host
	host = items[0].split('=')[1]
	index = hosts.index(host)

	#! Get values
	cpus = int(items[1].split('=')[1])
	hpm = float(items[2].split('=')[1])
	solved_blocks = int(items[3].split('=')[1])
	accepted_shares = int(items[4].split('=')[1])
	rejected_shares = int(items[5].split('=')[1])
	total_shares = accepted_shares + rejected_shares
	share_percent = float(accepted_shares / (total_shares if total_shares != 0 else 1) * 100.00)
	difficulty = float(items[6].split('=')[1])
	cpu_temp = float(items[7].split('=')[1])

	#! Set values in their respective lists
	cpus_list[index] = cpus
	hashrates[index] = hpm
	share_percents[index] = share_percent
	solved_blocks_list[index] = solved_blocks
	difficulties[index] = difficulty
	cpu_temps[index] = cpu_temp

	#! Build the display string entry
	string = "{0:<8}   {1:>8.3f} H/m   {2:>6.2f}%   {3:>6}   {4:<10} │ {5:>4}  {6:>5.1f}°C".format(host, hpm, share_percent, solved_blocks, difficulty, cpus, cpu_temp)
	statstrs[index] = string
	return


#! Main function
def main(stdscr):
	kill_threads.clear()

	#! Create list of hosts
	hosts_file = open("{0}/.chosts".format(Path.home()),'r')
	for line in hosts_file:
		hosts.append(line.rstrip())
	hosts_file.close()

	#! Initialize
	init_display()
	init_lists()
	init_zmqsockets()
	signal.signal(signal.SIGINT, signal_handler)

	#! Create threads and start
	for zmqsocket in zmqsockets:
		host = hosts[zmqsockets.index(zmqsocket)]
		t = threading.Thread(target=process_zmqmsg, args=(kill_threads, zmqsocket, host,))
		threads.append(t)
		t.start()

	stdscr.addstr(0,0,      "  ┌──────────┬──────────────┬─────────┬────────┬────────────┬───────────────┐")
	stdscr.addstr(1,0,      "  │ Hostname │   Hashrate   │ Share % │ Blocks │ Difficulty │ CPUs    Temp  │")
	stdscr.addstr(2,0,      "┌─┼──────────┴──────────────┴─────────┴────────┴────────────┼───────────────┤")
	while True:
		i = 3
		for string in statstrs:
			stdscr.addstr(i,0,"│ │ {0} │".format(string))
			stdscr.clrtoeol()
			i += 1

		#! Calculate Totals
		total_hashrate = sum(hashrates)
		total_share_percent = sum(share_percents)
		total_solved_blocks = sum(solved_blocks_list)
		total_cpus = sum(cpus_list)

		#! Calculate Averages
		avg_hashrate = total_hashrate / len(hashrates)
		avg_share_percent = total_share_percent / len(share_percents)
		avg_solved_blocks = total_solved_blocks / len(solved_blocks_list)
		avg_difficulty = sum(difficulties) / len(difficulties)
		avg_cpus = total_cpus / len(cpus_list)
		avg_cpu_temp = sum(cpu_temps) / len(cpu_temps)

		avg_string = "Average {0:>11.3f} H/m    {1:>5.2f}%   {2:>6}   {3:<10f} │ {4:>4}  {5:>5.1f}°C".format(avg_hashrate,avg_share_percent,avg_solved_blocks,avg_difficulty,avg_cpus,avg_cpu_temp)

		total_string = "Total   {0:>11.3f} H/m   ---.--%   {1:>6}   -.-------- │ {2:>4}  ---.-°C".format(total_hashrate,total_solved_blocks,total_cpus)
		stdscr.addstr(i,0,   "├─┼─────────────────────────────────────────────────────────┼───────────────┤")
		stdscr.addstr(i+1,0, "│ │ {0} │".format(avg_string))
		stdscr.addstr(i+2,0, "│ │ {0} │".format(total_string))
		stdscr.addstr(i+3,0, "└─┴─────────────────────────────────────────────────────────┴───────────────┘")

		c = stdscr.getch()  #! Calls stdscr.refresh()
		if c == ord('q'):
			break
		time.sleep(0.5)
	kill_program()
	return


#! Run the program
if __name__ == "__main__":
	wrapper(main)

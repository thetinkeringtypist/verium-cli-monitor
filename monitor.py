#!/usr/bin/env python3
#
#! Author: Bezeredi, Evan D.
#
#! CLI Monitor to display cpuminer information for each worker on the LAN
#
#! NOTE: Requires a list of hostnames/IPs on the LAN in
#        /home/<username>/.chosts
#
#!       Also requires miner-apid.py to running on each worker.
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
stdscr = curses.initscr()
hosts = []
statstrs = []
statinfo_list = []
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
	stdscr.nodelay(True) #! Nonblocking user input
	curses.curs_set(0)
	stdscr.clear()

	for host in hosts:
		#! Only (offline, host) since no value will be accessed 
		#  other than these if the host is offline
		statinfo_list.append((False, host))
		statstrs.append("")

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
		s.setsockopt(zmq.SNDTIMEO, 5000)
		s.setsockopt(zmq.RCVTIMEO, 5000)
		s.setsockopt(zmq.LINGER, 1000)
		zmqsockets.append(s)
	return


#! Interrupt signal handler
def signal_handler(signal, frame):
	kill_program()


#! Kill program
def kill_program():
	#! Kill curses stuff
	curses.nocbreak()
	stdscr.keypad(False)
	curses.echo()
	curses.endwin()
	
	#! Kill Threads
	kill_threads.set()
	print("Killing threads...")
	for t in threads:
		t.join()

	#! Kill ZMQ stuff
	for zmqsocket in zmqsockets:
		zmqsocket.close()
	context.term()

	sys.exit()
	return


#! Process messages from a zmqsocket
def process_zmqmsg(zmqsocket, host):
	while not kill_threads.is_set():
		time.sleep(1)

		try:
			zmqsocket.send_string("summary")
			msg = zmqsocket.recv_string()
			parse_zmqmsg(host,msg)
		except zmq.error.ZMQError as e:
			set_host_offline(host)
#			TODO: Figure out how to show host both
#			      go offline and come online
#			set_host_offline(host)
		
	return


#! Change display to reflect that the host is offline
def set_host_offline(host):
	index = hosts.index(host)
	statinfo_list[index] = (False, host)
	return


#! Parse message received from server
def parse_zmqmsg(host, msg):
	items = msg.split(",")

	#! Get the index of the host
#	host = items[0].split('=')[1]
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
	#! (online, host, hpm, percent, blocks, difficulty, cpus, temp)
	statinfo_list[index] = (True, host, hpm, share_percent, solved_blocks, difficulty, cpus, cpu_temp)
	return


#! Calc totals and averages
def get_totals_avgs():
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

	avg_str = "Average        {0:>11.3f} H/m    {1:>5.2f}%   {2:>6}   {3:<10f} │ {4:>4.2f}   {5:>5.1f}°C".format(avg_hashrate,avg_share_percent,avg_solved_blocks,avg_difficulty,avg_cpus,avg_cpu_temp)
	total_str = "Total          {0:>11.3f} H/m   ---.--%   {1:>6}   -.-------- │ {2:>4}   ---.-°C".format(total_hashrate,total_solved_blocks,total_cpus)

	return (total_str, avg_str)
	

#! The display and user input loop
def run_display_user_input():
	hl_host = 2
	hosts_len = len(hosts)

	#! Print header information
	stdscr.addstr(0,0,      "  ┌─────────────────┬──────────────┬─────────┬────────┬────────────┬──────┬─────────┐")
	stdscr.addstr(1,0,      "  │   Hostname/IP   │ Hashrate H/m │ Share % │ Blocks │ Difficulty │ CPUs │ Temp °C │")
	stdscr.addstr(2,0,      "┌─┼─────────────────┴──────────────┴─────────┴────────┴────────────┼──────┴─────────┤")

	while True:
		#! Get user input
		c = stdscr.getch()  #! Calls stdscr.refresh()
		if c == curses.KEY_DOWN:
			hl_host += 1 if hl_host <= hosts_len else 0
		elif c == curses.KEY_UP:
			hl_host -= 1 if hl_host > 2 else 0
		elif c == ord('q'):
			break
		else:
			pass

		write_to_scr(hl_host)

		#! Negligable refresh lag while
		#  keeping CPU usage down
		#  (for arrowing up and down)
		#! I want to use a keyboard event
		#  listener, but I can't find an
		#  implementation that works over
		#  ssh
		time.sleep(0.03)

	return


#! Write strings to the screen
def write_to_scr(hl_host):
	#! Screen info
	(term_height,term_width) = stdscr.getmaxyx()
	
	i = 3
	for statinfo in statinfo_list:
		#! Highlight host
		hl = (True if i == (hl_host + 1) else False)

		apply_formatting(i, statinfo, hl)
		i += 1
		
		
#	for string in statstrs:
#		#! Print host strings
#		if i == (hl_host + 1): #! Start of display offset
#			stdscr.addstr(i,0,"│>│")
#			stdscr.addstr(" {0} ".format(string), curses.A_REVERSE)
#			stdscr.addstr("│")
#		else:
#			stdscr.addstr(i,0,"│ │ {0} │".format(string))
#
#		stdscr.clrtoeol()
#		i += 1

	#! Print empty lines to fill the terminal
	for b in range(i,term_height):
		stdscr.addstr(b,0,          "│ │                                                                │                │")

	#! Calculate totals and averages
	(total_str,avg_str) = get_totals_avgs()
	stdscr.addstr(term_height-4,0, "├─┼────────────────────────────────────────────────────────────────┼────────────────┤")
	stdscr.addstr(term_height-3,0, "│ │ {0} │".format(avg_str))
	stdscr.addstr(term_height-2,0, "│ │ {0} │".format(total_str))
	stdscr.addstr(term_height-1,0, "└─┴────────────────────────────────────────────────────────────────┴────────────────┘")

	return


#! Applies formatting and coloring for written lines
def apply_formatting(line, statinfo, hl,):
	hl_prefix = "│>│"
	prefix =   "│ │"

	#! Host online, highlighted
	if statinfo[0] == True and hl == True:
		#! Three spaces between each. Space, bar, space between diff and cpus
		stdscr.addstr(line, 0, hl_prefix)
		stdscr.addstr(" {0:<15}".format(statinfo[1]), curses.A_REVERSE)      #! Hostname/IP
		stdscr.addstr("   ", curses.A_REVERSE)
		stdscr.addstr("{0:>8.3f} H/m".format(statinfo[2]), curses.A_REVERSE) #! HPM
		stdscr.addstr("   ", curses.A_REVERSE)
		stdscr.addstr("{0:>6.2f}%".format(statinfo[3]), curses.A_REVERSE)   #! Share %
		stdscr.addstr("   ", curses.A_REVERSE)
		stdscr.addstr("{0:>6}".format(statinfo[4]), curses.A_REVERSE)        #! Solved Blocks
		stdscr.addstr("   ", curses.A_REVERSE)
		stdscr.addstr("{0:<10} ".format(statinfo[5]), curses.A_REVERSE)       #! Difficulty
		stdscr.addstr("│", curses.A_REVERSE)
		stdscr.addstr(" {0:>4}".format(statinfo[6]), curses.A_REVERSE)        #! CPUs
		stdscr.addstr("   ", curses.A_REVERSE)
		stdscr.addstr("{0:>5.1f}°C ".format(statinfo[7]), curses.A_REVERSE)   #! CPU Temp

	#! Host online, not highlighted
	elif statinfo[0] == True and hl == False:
		stdscr.addstr(line, 0, prefix)
		stdscr.addstr(" {0:<15}".format(statinfo[1]))      #! Hostname/IP
		stdscr.addstr("   ")
		stdscr.addstr("{0:>8.3f} H/m".format(statinfo[2])) #! HPM
		stdscr.addstr("   ")
		stdscr.addstr("{0:>6.2f}%".format(statinfo[3]))   #! Share %
		stdscr.addstr("   ")
		stdscr.addstr("{0:>6}".format(statinfo[4]))        #! Solved Blocks
		stdscr.addstr("   ")
		stdscr.addstr("{0:<10} ".format(statinfo[5]))       #! Difficulty
		stdscr.addstr("│")
		stdscr.addstr(" {0:>4}".format(statinfo[6]))        #! CPUs
		stdscr.addstr("   ")
		stdscr.addstr("{0:>5.1f}°C ".format(statinfo[7]))  #! CPU Temp
		
	#! Host offline, highlighted
	elif statinfo[0] == False and hl == True:
		stdscr.addstr(line, 0, hl_prefix)
		stdscr.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------   -.-------- │ ----   ---.-°C ".format(statinfo[1]), curses.A_REVERSE)

	#! host offline, non-highlighted
	else:
		stdscr.addstr(line, 0, prefix)
		stdscr.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------   -.-------- │ ----   ---.-°C ".format(statinfo[1]))
		
	
	#! End of Line
	stdscr.addstr("│")
	stdscr.clrtoeol()

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
		t = threading.Thread(target=process_zmqmsg, args=(zmqsocket, host,))
		threads.append(t)
		t.start()

	#! Run display and user input loop
	run_display_user_input()

	#! Kill the program
	kill_program()
	return


#! Run the program
if __name__ == "__main__":
	wrapper(main)

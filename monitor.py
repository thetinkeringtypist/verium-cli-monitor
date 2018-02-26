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
windows = []
hosts = []
statinfo_list = []


#! Initialize display variables
def init_display():
	(term_height, term_width) = stdscr.getmaxyx()

	for host in hosts:
		#! Only (offline, host) since no value will be accessed 
		#  other than these if the host is offline
		statinfo_list.append((False, host))

	#! Header window (index 0)
	windows.append(curses.newwin(3, term_width, 0, 0))

	#! Hosts window (pad) (index 1)
	if len(hosts) < (term_height - 7): #! Header and footer
		windows.append(curses.newpad(term_height - 7, term_width))
	else:
		windows.append(curses.newpad(len(hosts), term_width))
		
	#! Footer window (index 2)
	windows.append(curses.newwin(4, term_width, term_height - 4, 0))

	curses.noecho()
	curses.cbreak()
	windows[1].keypad(True)
	windows[1].nodelay(True) #! Nonblocking user input
	curses.curs_set(0)
	stdscr.clear()
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
	print("Waiting for threads...")
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

	#! Build the display string entry
	#! (online, host, hpm, percent, blocks, difficulty, cpus, temp)
	statinfo_list[index] = (True, host, hpm, share_percent, solved_blocks, difficulty, cpus, cpu_temp)
	return


#! Calc totals and averages
def get_totals_avgs():
	total_hashrate = 0.0
	total_solved_blocks = 0
	total_cpus = 0
	online_hosts = list(filter(lambda info: info[0] == True, statinfo_list))
	length = len(online_hosts) if len(online_hosts) > 0 else 1

	#! Calculate totals
	total_hashrate      = sum(i for _,_,i,_,_,_,_,_ in online_hosts)
	total_solved_blocks = sum(i for _,_,_,_,i,_,_,_ in online_hosts)
	total_cpus          = sum(i for _,_,_,_,_,_,i,_ in online_hosts)

	#! Calculate averages
	avg_hashrate = total_hashrate / length
	avg_share_percent   = sum(i for _,_,_,i,_,_,_,_ in online_hosts) / length
	avg_solved_blocks   = total_solved_blocks / length
	avg_difficulty      = sum(i for _,_,_,_,_,i,_,_ in online_hosts) / length
	avg_cpus            = total_cpus / length
	avg_cpu_temp        = sum(i for _,_,_,_,_,_,_,i in online_hosts) / length

	avg_str = "Average {0:>18.3f} H/m   {1:>6.2f}%   {2:>6}   {3:<10f} │ {4:>4.2f}   {5:>5.1f}°C".format(avg_hashrate,avg_share_percent,avg_solved_blocks,avg_difficulty,avg_cpus,avg_cpu_temp)
	total_str = "Total   {0:>18.3f} H/m   ---.--%   {1:>6}   -.-------- │ {2:>4}   ---.-°C".format(total_hashrate,total_solved_blocks,total_cpus)

	return (total_str, avg_str)
	

#! The display and user input loop
def run_display_user_input():
	#! Window info
	header_win = windows[0]
	hosts_win = windows[1]
	footer_win = windows[2]
	(term_height, term_width) = stdscr.getmaxyx()
	(hosts_height, _) = hosts_win.getmaxyx()
	(footer_height, _) = footer_win.getmaxyx()

	hosts_len = len(hosts)
	hl_host = 0

	#! Print header information
	header_win.addstr(0,0,      "  ┌─────────────────┬──────────────┬─────────┬────────┬────────────┬──────┬─────────┐")
	header_win.clrtoeol()
	header_win.addstr(1,0,      "  │   Hostname/IP   │ Hashrate H/m │ Share % │ Blocks │ Difficulty │ CPUs │ Temp °C │")
	header_win.clrtoeol()
	header_win.addstr(2,0,      "┌─┼─────────────────┴──────────────┴─────────┴────────┴────────────┼──────┴─────────┤")
	header_win.clrtoeol()
	header_win.refresh()

	while True:
		(start_y,start_x, stop_y,stop_x) = write_to_scr(hl_host)

		#! Get user input
		c = hosts_win.getch()  #! Calls stdscr.refresh()
		if c == curses.KEY_DOWN:
			hl_host += 1 if hl_host < (hosts_len -1) else 0
		elif c == curses.KEY_UP:
			hl_host -= 1 if hl_host > 0 else 0
		elif c == ord('q'):
			break
		else:
			pass

		hosts_win.refresh( 0,0, 3,0, (term_height - footer_height - 1),term_width)
		footer_win.refresh()

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
	hosts_win = windows[1]
	footer_win = windows[2]
	(hosts_height, _) = hosts_win.getmaxyx()
	
	i = 0
	for statinfo in statinfo_list:
		#! Highlight host
		hl = (True if i == hl_host else False)
		apply_formatting(i, statinfo, hl)
		i += 1
		
	#! Print empty lines to fill the terminal
	for b in range(i, hosts_height):
		hosts_win.addstr(b,0,"│ │                                                                │                │")
		hosts_win.clrtoeol()

	#! Calculate totals and averages
	(total_str,avg_str) = get_totals_avgs()
	footer_win.addstr(0,0, "├─┼────────────────────────────────────────────────────────────────┼────────────────┤")
	footer_win.clrtoeol()
	footer_win.addstr(1,0, "│ │ {0} │".format(avg_str))
	footer_win.clrtoeol()
	footer_win.addstr(2,0, "│ │ {0} │".format(total_str))
	footer_win.clrtoeol()
	footer_win.addstr(3,0, "└─┴────────────────────────────────────────────────────────────────┴────────────────┘")
	footer_win.clrtoeol()

	return (0,0,0,0)


#! Applies formatting and coloring for written lines
def apply_formatting(line, statinfo, hl,):
	hosts_win = windows[1]

	hl_prefix = "│>│"
	prefix =    "│ │"

	#! Host online, highlighted
	if statinfo[0] == True and hl == True:
		hosts_win.addstr(line, 0, hl_prefix)
		#! Three spaces between each. Space, bar, space between diff and cpus
		hosts_win.addstr(" {0:<15}   ".format(statinfo[1]), curses.A_REVERSE)
		hosts_win.addstr("{0:>8.3f} H/m".format(statinfo[2]), curses.A_REVERSE) #! HPM
		hosts_win.addstr("   ", curses.A_REVERSE)
		hosts_win.addstr("{0:>6.2f}%".format(statinfo[3]), curses.A_REVERSE)   #! Share %
		hosts_win.addstr("   {0:>6}   {1:<10} │ {2:>4}   ".format(statinfo[4], statinfo[5], statinfo[6]), curses.A_REVERSE)
		hosts_win.addstr("{0:>5.1f}°C ".format(statinfo[7]), curses.A_REVERSE)  #! CPU Temp

	#! Host online, not highlighted
	elif statinfo[0] == True and hl == False:
		hosts_win.addstr(line, 0, prefix)
		hosts_win.addstr(" {0:<15}   ".format(statinfo[1]))
		hosts_win.addstr("{0:>8.3f} H/m".format(statinfo[2])) #! HPM
		hosts_win.addstr("   ")
		hosts_win.addstr("{0:>6.2f}%".format(statinfo[3]))   #! Share %
		hosts_win.addstr("   {0:>6}   {1:<10} │ {2:>4}   ".format(statinfo[4], statinfo[5], statinfo[6]))
		hosts_win.addstr("{0:>5.1f}°C ".format(statinfo[7]))  #! CPU Temp
		
	#! Host offline, highlighted
	elif statinfo[0] == False and hl == True:
		hosts_win.addstr(line, 0, hl_prefix)
		hosts_win.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------   -.-------- │ ----   ---.-°C ".format(statinfo[1]), curses.A_REVERSE)

	#! host offline, non-highlighted
	else:
		hosts_win.addstr(line, 0, prefix)
		hosts_win.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------   -.-------- │ ----   ---.-°C ".format(statinfo[1]))
		
	
	#! End of Line
	hosts_win.addstr("│")
	hosts_win.clrtoeol()

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

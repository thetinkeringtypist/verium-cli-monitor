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
import signal
import threading
import curses
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

	if curses.has_colors():
		curses.start_color()
		curses.use_default_colors()
		init_colors()
		windows[0].attrset(curses.color_pair(7))
		windows[1].attrset(curses.color_pair(7))
		windows[2].attrset(curses.color_pair(7))


	curses.noecho()
	curses.cbreak()
	windows[1].keypad(True)
	windows[1].nodelay(True) #! Nonblocking user input
	curses.curs_set(0)
	stdscr.clear()
	return


#! Define custom colors
def init_colors():
	curses.init_pair(7, 255, -1)


#! Initialize zmqsockets
def init_zmqsockets():
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
	#! Kill Threads
	kill_threads.set()
	print("Waiting for background threads...")
	for t in threads:
		t.join()

	#! Kill ZMQ stuff
	for zmqsocket in zmqsockets:
		zmqsocket.close()
	context.term()

	exit()
	return


#! Process messages from a zmqsocket
def process_zmqmsg(host):
	while not kill_threads.is_set():
		time.sleep(1)
		zmqsocket = zmqsockets[hosts.index(host)]

		try:
			zmqsocket.send_string("summary")
			msg = zmqsocket.recv_string()
			parse_summary_msg(host,msg)
		except zmq.error.ZMQError as e:
			set_host_offline(host)
			zmq_reconnect(zmqsocket, host)
		
	return


#! Change display to reflect that the host is offline
def set_host_offline(host):
	index = hosts.index(host)
	statinfo_list[index] = (False, host)
	return


#! Reconnect the zmqsocket
def zmq_reconnect(zmqsocket, host):
	#! Disconnect existing socket
	index = hosts.index(host)
	zmqsocket.disconnect("tcp://%s:5048" % host)
	zmqsockets[index] = None
	
	#! Reconnect the existing socket
	new_zmqsocket = context.socket(zmq.REQ)
	new_zmqsocket.connect("tcp://%s:5048" % host)
	new_zmqsocket.setsockopt(zmq.SNDTIMEO, 5000)  #! Arbitrary number of seconds
	new_zmqsocket.setsockopt(zmq.RCVTIMEO, 5000)  #! Arbitrary number of seconds
	new_zmqsocket.setsockopt(zmq.LINGER, 1000)    #! Arbitrary number of seconds

	zmqsockets[index] = new_zmqsocket
	return


#! Parse message received from server
def parse_summary_msg(host, msg):
	data_points = msg.split(";")

	#! Get the index of the host
	index = hosts.index(host)

	#! Get values
#	host     = data_points[0].split('=')[1]
	name     = data_points[1].split('=')[1]
	version  = data_points[2].split('=')[1]
	api      = data_points[3].split('=')[1]
	algo     = data_points[4].split('=')[1]
	cpus     = int(data_points[5].split('=')[1])
	khps     = float(data_points[6].split('=')[1])
	solved   = int(data_points[7].split('=')[1])
	accepted = int(data_points[8].split('=')[1])
	rejected = int(data_points[9].split('=')[1])
	accpm    = float(data_points[10].split('=')[1])
	diff     = float(data_points[11].split('=')[1])
	cpu_temp = float(data_points[12].split('=')[1])
	cpu_fan  = int(data_points[13].split('=')[1])
	cpu_freq = int(data_points[14].split('=')[1])
	uptime   = int(data_points[14].split('=')[1])   #! Uptime is in seconds
	time_sec = int(data_points[16].split('=')[1])   #! Time is in seconds

	#! Calculate hpm
	hpm     = khps * 1000 * 60
	total = accepted + rejected if accepted + rejected > 0 else 1
	percent = accepted / (total) * 100

	#! Build the display string entry
	#! (online, host, hpm, percent, blocks, difficulty, cpus, temp)
	statinfo_list[index] = (
		True, host, hpm, percent, solved, diff, cpus, cpu_temp)
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

	#! Formulate Average String
	avg_str = ("Average {0:>18.3f} H/m   {1:>6.2f}%   {2:>6}    {3:<8f}  "
		"│ {4:>4.2f}   {5:>5.1f}°C".format(
		avg_hashrate,avg_share_percent,avg_solved_blocks,
		avg_difficulty,avg_cpus,avg_cpu_temp))
	
	#! Formulate Average String
	total_str = ("Total   {0:>18.3f} H/m   ---.--%   {1:>6}    -.------  "
		"│ {2:>4}   ---.-°C".format(
		total_hashrate,total_solved_blocks,total_cpus))

	return (total_str, avg_str)
	

#! The display and user input loop
def run_display_user_input():
	#! Window info
	header_win = windows[0]
	hosts_win = windows[1]
	footer_win = windows[2]
	(term_height, term_width) = stdscr.getmaxyx()
	(header_height, _) = header_win.getmaxyx()
	(hosts_height, _) = hosts_win.getmaxyx()
	(footer_height, _) = footer_win.getmaxyx()

	hosts_scroll_max = term_height - header_height - footer_height - 1
	footer_start = term_height - footer_height - 1
	hosts_len = len(hosts)
	hl_host = 0
	start_y = 0

	#! Print header information
	header_win.addstr(0,0,      "  ┌─────────────────┬──────────────┬─────────┬────────┬────────────┬──────┬─────────┐")
	header_win.clrtoeol()
	header_win.addstr(1,0,      "  │   Hostname/IP   │ Hashrate H/m │ Share % │ Blocks │ Difficulty │ CPUs │ Temp °C │")
	header_win.clrtoeol()
	header_win.addstr(2,0,      "┌─┼─────────────────┴──────────────┴─────────┴────────┴────────────┼──────┴─────────┤")
	header_win.clrtoeol()
	header_win.refresh()

	while True:
		#! Write hosts to screen and frame the scroll window
		write_to_scr(hl_host)

		#! Get user input
		c = hosts_win.getch()  #! Calls stdscr.refresh()
		if c == curses.KEY_DOWN:
			if hl_host < (hosts_height - 1) and hl_host < (hosts_len - 1):
				hl_host += 1
			if start_y <= (hl_host - hosts_scroll_max - 1):
				start_y += 1 
		elif c == curses.KEY_UP:
			if hl_host > 0:
				hl_host -= 1 
			if hl_host < start_y and start_y > 0:
				start_y -= 1
		elif c == curses.KEY_HOME:
			hl_host = 0
			start_y = 0
		elif c == curses.KEY_END:
			hl_host = hosts_height - 1
			start_y = hl_host - hosts_scroll_max
		elif c == ord('q') or c == 27:
			#! Either q or ESC to quit
			break
		else:
			pass #! Leave everything as is

		hosts_win.refresh( start_y,0, 3,0, footer_start,term_width)
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

	return


#! Applies formatting and coloring for written lines
def apply_formatting(line, statinfo, hl):
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
		hosts_win.addstr("   {0:>6}    {1:<8}  │ {2:>4}   ".format(
			statinfo[4], statinfo[5], statinfo[6]), curses.A_REVERSE)
		hosts_win.addstr("{0:>5.1f}°C ".format(statinfo[7]), curses.A_REVERSE)  #! CPU Temp

	#! Host online, not highlighted
	elif statinfo[0] == True and hl == False:
		hosts_win.addstr(line, 0, prefix)
		hosts_win.addstr(" {0:<15}   ".format(statinfo[1]))
		hosts_win.addstr("{0:>8.3f} H/m".format(statinfo[2])) #! HPM
		hosts_win.addstr("   ")
		hosts_win.addstr("{0:>6.2f}%".format(statinfo[3]))   #! Share %
		hosts_win.addstr("   {0:>6}    {1:<8}  │ {2:>4}   ".format(
			statinfo[4], statinfo[5], statinfo[6]))
		hosts_win.addstr("{0:>5.1f}°C ".format(statinfo[7]))  #! CPU Temp
		
	#! Host offline, highlighted
	elif statinfo[0] == False and hl == True:
		hosts_win.addstr(line, 0, hl_prefix)
		hosts_win.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------    -.------  │ ----   ---.-°C ".format(statinfo[1]), curses.A_REVERSE)

	#! host offline, non-highlighted
	else:
		hosts_win.addstr(line, 0, prefix)
		hosts_win.addstr(" {0:<15}    ----.-- H/m   ---.--%   ------    -.------  │ ----   ---.-°C ".format(statinfo[1]))
		
	
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
		t = threading.Thread(target=process_zmqmsg, args=(host,))
		threads.append(t)
		t.start()

	#! Run display and user input loop
	run_display_user_input()

	#! Kill the program
	return


#! Run the program
if __name__ == "__main__":
	curses.wrapper(main)
	kill_program()

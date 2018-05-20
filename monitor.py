#!/usr/bin/env python3
#
# Author: Bezeredi, Evan D.
#
# CLI Monitor to display cpuminer information for each worker on the LAN
#
#! NOTE: Requires a list of hostnames/IPs on the LAN in
#        /home/<username>/.chosts; it is created if it does not exist.
#
#       Also requires miner-apid.py to running on each worker.
#
# I have this script running on my LAN controller so that finding each machine
#  on the LAN is not a problem
import socket as pysocket
import sys
import time
import signal
import threading
import curses
from pathlib import Path
from socket import *

ports = [4048,4049] #! NOTE: Change port numbers to those in use by your miners
pool_mining = True  #! NOTE: Change to False if solo mining

# Location of miner hosts file
hosts_file_str = "{0}/.chosts".format(Path.home())

# Socket connection timeout
TIMEOUT = 5000   # 5000 miliseconds (5 seconds)

# Thread variables
threads = []
kill_threads = threading.Event()

# Display varaibles
stdscr = None
header_win = None
hosts_win = None
footer_win = None
hosts = {}
hosts_display = []
host_count = 0


# Initialize display variables
def init_display():
	global stdscr, header_win, hosts_win, footer_win

	stdscr = curses.initscr()
	term_width = 102 # Arbitrary number for how wide the display is
	term_height = curses.LINES

	for host in hosts.keys():
		# Only (offline, host) since no value will be accessed 
		# other than these if the host is offline
		hosts[host] = (False, host)

	# Header window
	header_win = curses.newpad(3, term_width)

	# Hosts window
	if host_count < (term_height - 7): # Header and footer
		hosts_win = curses.newpad(term_height - 7, term_width)
	else:
		hosts_win = curses.newpad(host_count, term_width)
		
	# Footer window
	footer_win = curses.newpad(4, term_width)

	if curses.has_colors():
		curses.start_color()
		curses.use_default_colors()
		init_colors()
		header_win.attrset(curses.color_pair(0))
		hosts_win.attrset(curses.color_pair(0))
		footer_win.attrset(curses.color_pair(0))

	curses.noecho()
	curses.cbreak()
	hosts_win.keypad(True)
	hosts_win.nodelay(True) #! Nonblocking user input
	curses.curs_set(0)
	stdscr.clear()
	return


# Define custom colors
def init_colors():
	for i in range(0, curses.COLORS):
		curses.init_pair(i + 1, i, -1)
	return


# Interrupt signal handler
def signal_handler(signal, frame):
	kill_program()


# Kill program
def kill_program():
	# Kill Threads
	kill_threads.set()
	print("Waiting for background threads...")
	for t in threads:
		t.join()

	exit()
	return


# Process messages from a zmqsocket
def process_worker_msg(hostname, thread_data):
	global TIMEOUT
	thread_data.miner_results = []
	thread_data.host = hostname
	thread_data.socket = None

	miner_results = thread_data.miner_results
	host = thread_data.host
	while not kill_threads.is_set():
		miner_results.clear()
		time.sleep(1)

		# For each possible port in use
		for port in ports:
			# Treat connection timeouts differently
			try:
				thread_data.socket = pysocket.create_connection((host,port), timeout=5)
			except:
				continue

			try:
				socket = thread_data.socket

				# Request miner information
				socket.settimeout(TIMEOUT)
				socket.send("summary".encode())

				# Receive miner information
				socket.settimeout(TIMEOUT)
				thread_data.msg = socket.recv(4096).decode()
				miner_results.append(parse_summary_msg(host,thread_data.msg))
			except timeout as e:
				pass
			except:
				pass
			finally:
				socket.close()

		combine_results(host, miner_results)
	return


# Change display to reflect that the host is offline
def set_host_offline(host):
	hosts[host] = (False, host)
	return


# Parse message received from server
def parse_summary_msg(host, msg):
	data_points = msg.split('|')[0].split(';')

	# Get values
	name     = data_points[0].split('=')[1]
	version  = data_points[1].split('=')[1]
	api      = data_points[2].split('=')[1]
	algo     = data_points[3].split('=')[1]
	cpus     = int(data_points[4].split('=')[1])
	khps     = float(data_points[5].split('=')[1])
	solved   = int(data_points[6].split('=')[1])
	accepted = int(data_points[7].split('=')[1])
	rejected = int(data_points[8].split('=')[1])
	accpm    = float(data_points[9].split('=')[1])
	diff     = float(data_points[10].split('=')[1])
	cpu_temp = float(data_points[11].split('=')[1])
	cpu_fan  = int(data_points[12].split('=')[1])
	cpu_freq = int(data_points[13].split('=')[1])
	uptime   = int(data_points[14].split('=')[1])   # Uptime is in seconds
	time_sec = int(data_points[15].split('=')[1])   # Time is in seconds

	# Calculate hpm
	hpm     = khps * 1000 * 60
	total = accepted + rejected if accepted + rejected > 0 else 1
	percent = accepted / (total) * 100

	# Build the display string entry
	# (online, host, hpm, percent, blocks, difficulty, cpus, temp)
	return (True, host, hpm, percent, accpm, solved, diff, cpus, cpu_temp)


# Combine results from each miner status
def combine_results(host, miner_results):
	count = len(miner_results)

	# Edge cases
	if count == 0:
		set_host_offline(host)
		return
	if count == 1:
		hosts[host] = miner_results[0]
		return

	# Combine results from all miners on a worker
	hpm = 0
	solved = 0
	percent = 0.0
	accpm = 0.0
	cpus = 0
	diff = 0.0
	cpu_temp = 0.0
	for result in miner_results:
		hpm += result[2]
		percent += result[3]
		accpm += result[4]
		solved += result[5]
		cpus += result[7]

		if result[6] > diff:
			diff = result[6]
		if result[8] > cpu_temp:
			cpu_temp = result[8]

	# Build the display string entry
	percent /= count if count > 0 else 1  # Normalize percent
	hosts[host] = (
		miner_results[0][0], host, hpm, percent, accpm, solved, diff, cpus, cpu_temp)
	return


# Calc totals and averages
def get_totals_avgs():
	online_hosts = list(filter(lambda statinfo: statinfo[0] == True, hosts.values()))
	length = len(online_hosts) if len(online_hosts) > 0 else 1

	# Calculate totals
	total_hashrate      = sum(i for _,_,i,_,_,_,_,_,_ in online_hosts)
	total_acceptrate    = sum(i for _,_,_,_,i,_,_,_,_ in online_hosts)
	total_solved_blocks = sum(i for _,_,_,_,_,i,_,_,_ in online_hosts)
	total_cpus          = sum(i for _,_,_,_,_,_,_,i,_ in online_hosts)

	# Calculate averages
	avg_hashrate        = total_hashrate / length
	avg_share_percent   = sum(i for _,_,_,i,_,_,_,_,_ in online_hosts) / length
	avg_acceptrate      = total_acceptrate / length
	avg_solved_blocks   = total_solved_blocks / length
	avg_difficulty      = sum(i for _,_,_,_,_,_,i,_,_ in online_hosts) / length
	avg_cpus            = total_cpus / length
	avg_cpu_temp        = sum(i for _,_,_,_,_,_,_,_,i in online_hosts) / length

	# Formulate Average String
	if pool_mining:
		avg_str = ("Average {0:>19.3f} H/m   {1:>6.2f}%   {2:>8.3f} S/m    "
			"{3:<8f}  │ {4:>4.1f}   {5:>5.1f}°C".format(avg_hashrate,
			avg_share_percent,avg_acceptrate,avg_difficulty,avg_cpus,avg_cpu_temp))
	else:
		avg_str = ("Average {0:>19.3f} H/m   {1:>6}    "
			"{2:<8f}  │ {3:>4.1f}   {4:>5.1f}°C".format(avg_hashrate,
			avg_solved_blocks,avg_difficulty,avg_cpus,avg_cpu_temp))

	
	# Formulate Total String
	if pool_mining:
		total_str = ("Total   {0:>19.3f} H/m   ---.--%   {1:>8.3f} S/m    "
			"-.------  │ {2:>4}   ---.-°C".format(
			total_hashrate,total_acceptrate,total_cpus))
	else:
		total_str = ("Total   {0:>19.3f} H/m   {1:>6}    "
			"-.------  │ {2:>4}   ---.-°C".format(total_hashrate,
			total_solved_blocks,total_cpus))


	return (total_str, avg_str)
	

# The display and user input loop
def run_display_user_input(display_width, hl_host):
	# Window info
	global header_win, hosts_win, footer_win
	term_height = curses.LINES
	(header_height, _) = header_win.getmaxyx()
	(hosts_height, _) = hosts_win.getmaxyx()
	(footer_height, _) = footer_win.getmaxyx()

	hosts_scroll_max = term_height - header_height - footer_height - 1
	footer_start = term_height - footer_height - 1
	header_stop = header_height - 1
	start_y = 0
	quitting = False

	# Print header information
	try:
		print_column_headers()
		header_win.noutrefresh(0,0, 0,0, header_stop,display_width)
	except curses.error as e:
		pass

	while True:
		# Write hosts to screen and frame the scroll window
		write_to_scr(hl_host)

		# Get user input
		c = hosts_win.getch()  # Calls stdscr.refresh()
		if c == curses.KEY_DOWN:
			if hl_host < (hosts_height - 1) and hl_host < (host_count - 1):
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
			# Either q or ESC to quit
			quitting = True
			curses.doupdate()
			break
		elif c == curses.KEY_RESIZE:
			quitting = False
			curses.update_lines_cols()
			curses.doupdate()
			break
		else:
			pass # Leave everything as is

		try:
			hosts_win.noutrefresh( start_y,0, 3,0, footer_start,display_width)
			footer_win.noutrefresh( 0,0, footer_start + 1,0, term_height - 1,display_width)
			curses.doupdate()
		except curses.error as e:
			pass

		# Negligable refresh lag while keeping CPU usage down (for arrowing up
		# and down). I want to use a keyboard event listener, but I haven't found
		# an implementation that works over ssh without the use of X11.
		time.sleep(0.03)

	return (quitting, hl_host)


# Write strings to the screen
def write_to_scr(hl_host):
	global hosts_win, footer_win
	(hosts_height, _) = hosts_win.getmaxyx()
	
	for i, host in enumerate(hosts_display):
		# Highlight host
		hl = (i == hl_host)
		apply_formatting(i, hosts[host], hl)
		
	# Print empty lines to fill the terminal
	for b in range(i, hosts_height):
		print_empty_entry(b)

	# Calculate totals and averages
	(total_str,avg_str) = get_totals_avgs()
	print_column_footers(avg_str,total_str)
	return


def print_empty_entry(line):
	if pool_mining:
		hosts_win.addstr(line,0,"│ │                                      "
			"                                 │                │")
	else:
		hosts_win.addstr(line,0,"│ │                                      "
			"                 │                │")
	hosts_win.clrtoeol()
	return


# Write column headers to the screen
def print_column_headers():
	global header_win

	if pool_mining:
		header_win.addstr(0,0,      "  ┌─────────────────┬───────────────┬─────"
			"────┬──────────────┬────────────┬──────┬─────────┐")
		header_win.clrtoeol()
		header_win.addstr(1,0,      "  │   Hostname/IP   │  Hashrate H/m │ Shar"
			"e % │ Accepted S/m │ Difficulty │ CPUs │ Temp °C │")
		header_win.clrtoeol()
		header_win.addstr(2,0,      "┌─┼─────────────────┴───────────────┴─────"
			"────┴──────────────┴────────────┼──────┴─────────┤")
	else:
		header_win.addstr(0,0,      "  ┌─────────────────┬───────────────┬"
			"────────┬────────────┬──────┬─────────┐")
		header_win.clrtoeol()
		header_win.addstr(1,0,      "  │   Hostname/IP   │  Hashrate H/m │"
			" Blocks │ Difficulty │ CPUs │ Temp °C │")
		header_win.clrtoeol()
		header_win.addstr(2,0,      "┌─┼─────────────────┴───────────────┴"
			"────────┴────────────┼──────┴─────────┤")
	header_win.clrtoeol()
	return


# Write column footers to the screen
def print_column_footers(avg_str, total_str):
	global footer_win
	if pool_mining:
		footer_win.addstr(0,0, "├─┼──────────────────────────────────────"
			"─────────────────────────────────┼────────────────┤")
		footer_win.clrtoeol()
		footer_win.addstr(1,0, "│ │ {0} │".format(avg_str))
		footer_win.clrtoeol()
		footer_win.addstr(2,0, "│ │ {0} │".format(total_str))
		footer_win.clrtoeol()
		footer_win.addstr(3,0,"└─┴───────────────────────────────────────"
			"────────────────────────────────┴────────────────┘")
	else:
		footer_win.addstr(0,0, "├─┼────────────────────────────────"
			"───────────────────────┼────────────────┤")
		footer_win.clrtoeol()
		footer_win.addstr(1,0, "│ │ {0} │".format(avg_str))
		footer_win.clrtoeol()
		footer_win.addstr(2,0, "│ │ {0} │".format(total_str))
		footer_win.clrtoeol()
		footer_win.addstr(3,0,"└─┴─────────────────────────────────"
			"──────────────────────┴────────────────┘")
	footer_win.clrtoeol()
	return


# Applies formatting and coloring for written lines
def apply_formatting(line, statinfo, hl):
	global hosts_win
	prefix = "│>│" if hl else "│ │"

	# Online vs. Offline
	if statinfo[0]:
		hoststr =  "{0:<15}".format(statinfo[1])
		hashstr =  "{0:>9.3f} H/m".format(statinfo[2])
		sharestr = "{0:>6.2f}%   {1:8.3f} S/m".format(statinfo[3], statinfo[4])
		blockstr = "{0:>6}".format(statinfo[5])
		diffstr =  "{0:<8}".format(statinfo[6])
		cpustr =   "{0:>4}   {1:>5.1f}°C".format(statinfo[7], statinfo[8])
	else:
		hoststr =  "{0:<15}".format(statinfo[1])
		hashstr =  "-----.--- H/m"
		sharestr = "---.--%   ----.--- S/m"
		blockstr = "------"
		diffstr =  "-.------"
		cpustr =   "----   ---.-°C"

	hosts_win.addstr(line, 0, prefix)

	# Turn on highlighting
	if hl:
		hosts_win.attron(curses.A_REVERSE)

	# Print share information if pool mining, block info otherwise
	if pool_mining:
		hosts_win.addstr(" {0}   {1}   {2}    {3}  │ {4} ".format(
			hoststr, hashstr, sharestr, diffstr, cpustr))
	else:
		hosts_win.addstr(" {0}   {1}   {2}    {3}  │ {4} ".format(
			hoststr, hashstr, blockstr, diffstr, cpustr))

	# Turn off highlighting
	hosts_win.attroff(curses.A_REVERSE)

	hosts_win.addch("│")
	hosts_win.clrtoeol()
	return


# Parse command line options
def parse_options():
	global pool_mining
	# Check commandline arguments
	if len(sys.argv) > 1:
		if sys.argv[1] == "--pool" or sys.argv[1] == "-p":
			pool_mining = True
		elif sys.argv[1] == "--solo" or sys.argv[1] == "-s":
			pool_mining = False
		elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
			print("Usage: {0} [OPTIONS]".format(sys.argv[0]))
			print("Display information about your verium miners.")
			print("")
			print("Available options:")
			print("  -p, --pool     Display information as if you were pool mining (default)")
			print("  -s, --solo     Display information as if you were solo mining")
			print("  -h, --help     Print this help and exit")
			print("")
			print("Available controls:")
			print("  Arrow Up       Move up your list of miners")
			print("  Arrow Down     Move down your list of miners")
			print("  Home Key       Go to the first miner in the list of miners")
			print("  End Key        Go to the last miner in the list of miners")
			print("  q, ESC         Quit")
			print("  Ctrl-C         Quit")
			print("")
			print("Relevant files:")
			print("  $HOME/.chosts  The file that contains the list of your miners.")
			print("                 Supports hostname or IP address. One per line.")
			print("                 Example:")
			print("                   192.168.1.2")
			print("                   miner2")
			print("  /etc/hosts     The system file that contains a list of known")
			print("                 hosts. Add your miner IP address AND hostname")
			print("                 to this file if you are not using DNS. One per line.")
			print("                 Example:")
			print("                   192.168.1.2  miner1")
			print("                   192.168.1.3  miner2")
			print("Other notes:")
			print("  If a host is offline when you exit out of this monitor, it")
			print("  may take a few seconds to return to a command line. The")
			print("  socket is trying to connect to that offline host and needs")
			print("  to timeout before that thread will terminate.")
			exit()
		else:
			pass
	return
	

# Main function
def main(stdscr):
	global host_count

	# Create list of hosts
	Path(hosts_file_str).touch(exist_ok=True)
	hosts_file = open(hosts_file_str,'r')
	for line in hosts_file:
		hostname = line.rstrip()
		hosts[hostname] = (False, hostname)
		hosts_display.append(hostname)
	hosts_file.close()
	host_count = len(hosts)

	# Initialize
	init_display()
	signal.signal(signal.SIGINT, signal_handler)

	# Create threads and start
	thread_data = threading.local()
	kill_threads.clear()
	for host in hosts.keys():
		t = threading.Thread(target=process_worker_msg, args=(host,thread_data,))
		threads.append(t)
		t.name = host
		t.start()

	# Run display and user input loop
	hl_host = 0
	while True:
		(quitting, hl_host) = run_display_user_input(curses.COLS - 1, hl_host)

		if quitting:
			break

	# Kill the program
	return


# Run the program
if __name__ == "__main__":
	parse_options()
	curses.wrapper(main)
	kill_program()

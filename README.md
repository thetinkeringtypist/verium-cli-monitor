Verium CLI Monitoring
=====================
To have Verium Miners running is one thing, to be able to monitor them in
real-time is another. This can be done through web-based monitors or via this
CLI monitor.


![alt text](https://github.com/bezeredi/verium-cli-monitor/blob/master/cli-monitor.png "CLI Monitor Preview")


### How To Install & Use
This monitor currently supports `cpuminer` API version 1.1. This means that it
should work with the following CPU miners:
 * [Fireworm71's veriumMiner](https://github.com/fireworm71/veriumMiner)
 * [effectsToCause's veriumMiner](https://github.com/fireworm71/veriumMiner)
 * [tpruvot's cpuminer-multi](https://github.com/tpruvot/cpuminer-multi)

There are two parts to this setup:
 * The Monitor (`monitor.py`): the display through which you will see the status of your monitors, and
 * The monitor API daemon (`miner-apid.py`): the agent that will provide miner statistics when requested by the monitor


Firstly, it should be noted that the `miner-apid.py` script is preconfigured for
a setup that uses two `cpuminer` instances: one using port 4048 and one using
port 4049. If you are using any other number of miners, just change the port
numbers in `miner-apid.py` BEFORE you copy `miner-apid.py` to each of your
miner machines. Also note that `miner-apid.py` uses port 5048 for communication
with the monitor.


1) Install `python3`, `pip3`, `libzmq5`, and `pyzmq` on each mining machine AND
the machine that `monitor.py` will run on:
```bash
sudo apt-get install python3 python3-pip libzmq5
sudo -H pip3 install --upgrade pip
sudo -H pip3 install pyzmq
```

2) Copy `miner-apid.py` to each machine running a miner on your LAN.
`miner-apid.py` needs to start after your miner instances start. Since most
people run their miners via `/etc/rc.local`, add this line to the end of your
`/etc/rc.local` file:
```bash
/path/to/script/miner-apid.py >> /path/to/logfile.log 2>&1 &
```

This way if `miner-apid.py` crashes, you can see the error.

3) Now, you can restart your mining machine and you should be able to see it
running via `ps`, `top`, `htop`, `pgrep`, etc:
```bash
pgrep -f miner-apid.py
```

4) Copy `monitor.py` to a machine on your LAN that can reach all of your mining
machines (for me, that was on my LAN controller). Create a file called
`.chosts` in your user's home directory and add the IP of each mining machine
on your LAN (hostnames can be used if you are running DNS or have them
enumerated in your `/etc/hosts` file)

5) Run `./monitor.py` and you should see statistics coming from each of your
mining machines


### License
Free to use, just give credit where it's due.

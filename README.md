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


1) Copy `monitor.py` to a computer on your network that can reach all of your
miners. For me, this was my LAN controller.

2) Make sure each `cpuminer` is configured with the correct `api-bind` address:
```bash
cpuminer [options] --api-bind "0.0.0.0:<port-number>"
```

3) Change the line in `monitor.py` to include any port in use by a miner on
your network:
```python
#! monitor.py
ports = [4048, 4049]   #! NOTE: Change port numbers to those in use by your miners
```

4) Install `python3`:
```bash
sudo apt-get install python3
```

5) Create a file called `.chosts` in your home directory. On each line, place
the IP address of a worker on your network (hostnames can be used if you are
using DNS or have them enumerated in `/etc/hosts`):

```bash
cat /home/<username>/.chosts
miner1
miner2

cat /etc/hosts
192.168.1.2   miner1
192.168.1.3   miner2
```

6) Run `./monitor.py` and you should see statistics coming from each of your
mining machines


### Monitor Controls
 * Arrow Up, Arrow Down - Up and down
 * Home, End - First worker, last worker
 * q, ESC - Quit


### Example Network Diagram
An example network diagram can be found [here](https://github.com/bezeredi/verium-cli-monitor/blob/master/example-diagram.txt).


### License & Donations
Credit to [rbthomp](https://github.com/rbthomp) for demonstrating that ZMQ is
not necessary for this tool.

Free to use, just give credit where it's due. If this software helped you out,
consider a small donation.

VRC/VRM: VBwPRc7gmmqgJTsiB6LqsStVk2nxgRoyjh

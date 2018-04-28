Verium CLI Monitoring
=====================
Monitor your Verium miners in real-time with this CLI monitor! Great for a small to moderate number of miners, like SBC setups!


![Preview of the CLI Monitor with Pool Mining Enabled](https://github.com/bezeredi/verium-cli-monitor/blob/master/cli-monitor.png "CLI Monitor Preview")


#### Supported `cpuminers`
This monitor currently supports `cpuminer` API version 1.1. This means that it
should work with the following CPU miners:
 * [Fireworm71's veriumMiner](https://github.com/fireworm71/veriumMiner)
 * [effectsToCause's veriumMiner](https://github.com/fireworm71/veriumMiner)
 * [tpruvot's cpuminer-multi](https://github.com/tpruvot/cpuminer-multi)

**Be aware**, not all cpuminer implementations report accurate information about themselves.


#### Configure, Install, and Run
1) Make sure each `cpuminer` is configured with the correct `api-bind` address:
```bash
cpuminer [options] --api-bind "0.0.0.0:<port-number>"
```

2) Copy `monitor.py` to a computer on your network that can reach all of your
miners. For me, this was my LAN controller.

3) Change the lines in `monitor.py` to include any port in use by a miner on
your network and if you are pool mining or solo mining:
```python
#! monitor.py
ports = [4048, 4049]   #! NOTE: Change port numbers to those in use by your miners
pool_mining = True     #! NOTE: Change to False if solo mining
```

4) Install `python3`:
```bash
sudo apt-get install python3
```

5) The monitor creates a file called `.chosts` in your home directory. On each
line of that file, place the IP address of a worker on your network (hostnames
can be used if you are using DNS or have them enumerated in `/etc/hosts`):

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


#### Monitor Controls
 * Arrow Up, Arrow Down - Up and down
 * Home, End - First worker, last worker
 * q, ESC - Quit

#### Monitor Options
 * `-p`, `--pool`     Display information as if you were pool mining (default)
 * `-s`, `--solo`     Display information as if you were solo mining
 * `-h`, `--help`     Print the help and exit


#### Example Network Diagram
An example network diagram can be found [here](https://github.com/bezeredi/verium-cli-monitor/blob/master/example-diagram.txt).


#### License & Donations
Credit to [rbthomp](https://github.com/rbthomp) for demonstrating that ZMQ is
not necessary for this tool.

Free to use, just give credit where it's due. If this software helped you out,
consider a small donation.

VRC/VRM: VBwPRc7gmmqgJTsiB6LqsStVk2nxgRoyjh

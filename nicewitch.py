#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Cross-platform algorithm switcher for NiceHash
# It does the same job as NicehashMinerLegacy swithcing between algorithms and miners

# History:
#   Special thanks to Ryan Young (rayoung@utexas.edu, https://github.com/YoRyan) for his idea and part of the code from excavator-driver.py
#   2018-02-19: initial version

__license__ = "GNU GENERAL PUBLIC LICENSE v3.0"

import time
import shlex
import subprocess
import operator
import json
import socket
import sys
import requests
from subprocess import Popen
from time import sleep

# User wallet, worker and region settings
WALLET_ADDR = '37ajn6fULSTfR3HuLdmw9RVPyiJXVrYcQf'
WORKER_NAME = 'rig1'
USER = WALLET_ADDR + '.' + WORKER_NAME 
REGION = 'eu'  # eu, usa, hk, jp, in, br

# Path to the directory with mining software
PATH = '/home/$USER/.local/bin'

# Copy & Paste here numbers from benchmark of your miner converted to base unit, H/s
#   H/s   ->  [YOURBECHMARK]
#   kH/s  ->  [YOURBECHMARK]e3 
#   MH/s  ->  [YOURBECHMARK]e6
#   GH/s  ->  [YOURBECHMARK]e9
# if you want to switch off some algorithm just put 0 into the value, or comment it out

MINER = {
    'lyra2rev2': f"{PATH}/ccminer -a lyra2v2 -o stratum+tcp://lyra2rev2.{REGION}.nicehash.com:3347 -u {USER} -p x",
    'neoscrypt': f"{PATH}/ccminer -a neoscrypt -o stratum+tcp://neoscrypt.{REGION}.nicehash.com:3341 -u {USER} -p x",
    'equihash': f"{PATH}/bminer -uri stratum://{USER}:x@equihash.{REGION}.nicehash.com:3357",
    'daggerhashimoto': f"{PATH}/ethminer -SP 2 -U -S daggerhashimoto.{REGION}.nicehash.com:3353 -O {USER} --cuda-parallel-hash 4",
    'daggerhashimoto_pascal': f"{PATH}/claymore/ethdcrminer64 -epool stratum+tcp://daggerhashimoto.{REGION}.nicehash.com:3353 -ewal {USER} -epsw x -esm 3 -allpools 1 -estale 0 -dpool stratum+tcp://pascal.{REGION}.nicehash.com:3358 -dwal {USER} -dcoin pasc -mport 0"
}

BENCHMARKS = {
    # 'keccak': 1685397e11,
    # 'nist5': 122.084e6,
    # 'neoscrypt': 3100e3,
    'lyra2rev2': 156e6,
    'daggerhashimoto': 113.0e6,
    # 'decred': 7493288e3,
    # 'cryptonight': 0,
    # 'lbry': 741.751e6,
    'equihash': 2000,
    # 'pascal': 0,
    # 'sia': 3393433e3,
    'daggerhashimoto_pascal': [82.35e6, 822.5e6],
    'daggerhashimoto_decred': [81.280e6, 812.2e6]
    # 'daggerhashimoto_sia': [82.5e6, 825e6],
    # 'daggerhashimoto_keccak': [77.2e6, 770.5e6]
}

PROFIT_SWITCH_THRESHOLD = 0.1
UPDATE_INTERVAL = 60

EXCAVATOR_TIMEOUT = 10

# HERE BE DRAGONS


def main():

    current_algo_rate = 0
    current_algo_name = ""

    while True:
        try:
            best_algo_name, best_algo_rate = best_algo()
            print(f"[+] best = {best_algo_name}")
            print(f"[+] current = {current_algo_name}")
            if current_algo_rate == 0:
                current_algo_rate = best_algo_rate
                current_algo_name = best_algo_name
                print(f"[+] new_current = {current_algo_name}")
                p = choose_miner(current_algo_name)
                print(f"[+] PID {p.pid}")
            elif current_algo_name != best_algo_name and (best_algo_rate/current_algo_rate >= 1.0 + PROFIT_SWITCH_THRESHOLD):
                p.kill()
                p.wait()
                current_algo_rate = best_algo_rate
                current_algo_name = best_algo_name
                print(f"[*] new_current = {current_algo_name}")
                p = choose_miner(current_algo_name)
                print(f"[*] PID {p.pid}")            
        
            time.sleep(UPDATE_INTERVAL)
    
        except KeyboardInterrupt:
            print("\n\n[*] User requested An Interrupt")
            print("[*] Application Exiting ...")
            sys.exit(0)


def nicehash_multialgo_info():

    # Retrieves pay rates and connection ports for every algorithm from the NiceHash API.
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get('https://api.nicehash.com/api?method=simplemultialgo.info', headers=headers, timeout=20)
    except:
        if check_connection() == False:
            print('[-] No Internet Connection, waiting 5 min before reconnect attempt')
            time.sleep(UPDATE_INTERVAL * 5)
        else:
            print('[-] NiceHash server is not responding, waiting 60 sec before new attempt')
            time.sleep(UPDATE_INTERVAL)
            return nicehash_multialgo_info()
    rates = json.loads(r.text) 
    paying = {}
    ports = {}
    for algo in rates['result']['simplemultialgo']:
        name = algo['name']
        paying[name] = float(algo['paying'])
        ports[name] = int(algo['port'])
    return paying, ports


def payrate(paying, algo, speed):
    return paying[algo] * speed * (24 * 60 * 60) * 1e-11


def best_algo():  # Calculating max payout and return the name of the algorithm with the best profit for given benchmarks 
    paying, ports = nicehash_multialgo_info()
    b = BENCHMARKS
    payrates = {}
    for algo in b.keys():
        if '_' in algo:
            payrates[algo] = (sum([payrate(paying, multi_algo, b[algo][i]) for i, multi_algo in enumerate(algo.split('_'))]))
        else:
            payrates[algo] = (payrate(paying, algo, b[algo]))
    algo_name = max(payrates.items(), key=operator.itemgetter(1))[0]
    algo_rate = max(payrates.values())
    return algo_name, algo_rate


def check_connection():  # Checking internet state
    try:
        host = socket.gethostbyname("yandex.ru")
        s = socket.create_connection((host, 80), 2)
        return True
    except:
        pass
    return False


def choose_miner(algo):
    m = MINER
    args = shlex.split(m[algo])
    return subprocess.Popen(args)


if __name__ == '__main__':
    main()


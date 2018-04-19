#!/usr/bin/env python
"""
CM Phase 2 command
"""
import time
import zmq
import argparse
from CMMsg import CMMsg

def main():

    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=int, choices=range(0, 8), default=0, help='platform (default 0)')
    args = parser.parse_args()

    # Prepare our context and DEALER socket
    ctx = zmq.Context()
    cmd = ctx.socket(zmq.DEALER)
    cmd.linger = 0
    cmd.RCVTIMEO = 5000 # in milliseconds
    cmd.connect("tcp://%s:%d" % (CMMsg.host(), CMMsg.router_port(args.p)))

    # Initiate partition kill
    cmd.send(CMMsg.STARTKILL)
    while True:
        try:
            cmmsg = CMMsg.recv(cmd)
        except Exception as ex:
            print(ex)
            return

        if cmmsg.key == CMMsg.KILLSTARTED:
            print ("I: Received KILLSTARTED")
            break          # Done
        else:
            print ("W: Received key <%s>" % cmmsg.key.decode())
            continue

#   print ("Done")

if __name__ == '__main__':
    main()
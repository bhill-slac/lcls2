import argparse
import zmq
import time


port   = 55560                  # Default value
zmqSrv = 'psdev7b'

parser = argparse.ArgumentParser(description='Monitor data printer')

parser.add_argument('-P', '--port',     type=int, help='Port number [%d]' % port)
parser.add_argument('-p', '--platform', type=int, choices=range(0, 8), default=0, help='Platform number')
parser.add_argument('-Z', '--zmqSrv',   help='ZMQ server [%s]' % zmqSrv)

args = parser.parse_args()

if args.port is None:
    port += 2 * args.platform
else:
    port = args.port

if args.zmqSrv is not None:
    zmqSrv = args.zmqSrv

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect('tcp://%s:%d' % (zmqSrv, port))
socket.setsockopt(zmq.SUBSCRIBE, b'')
print('Listening to: %s:%d' % (zmqSrv, port))

try:
    while True:
        hostname, metrics = socket.recv_json()
        #print(hostname, metrics)

        # shift timestamp from UTC to current timezone and convert to milliseconds
        ##metrics['time'] = [(t - time.altzone)*1000 for t in metrics['time']]

        line = (hostname.split('.')[0]) + ":"
        for k in metrics:
            if k == 'time':
                line +=  " %4s" % (k) + " %7s" % (str(metrics[k][0]))
            else:
                line += "  %11s" % (k) + " %9s" % (str(metrics[k][0]))
        print (line)
except KeyboardInterrupt:
    print()


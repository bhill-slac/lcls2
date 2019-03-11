import os
import time
import copy
import socket
from datetime import datetime, timezone
import zmq
from transitions import Machine, MachineError, State
import argparse
import logging
import threading

PORT_BASE = 29980
POSIX_TIME_AT_EPICS_EPOCH = 631152000

class MonitorThread (threading.Thread):

    # callback function
    callback = None
    # an event that tells the thread to stop
    stopper = None

    def __init__(self, callback, stopper, host, platform):
        threading.Thread.__init__(self)
        self.callback = callback
        self.stopper = stopper
        # initialize zmq socket
        self.context = zmq.Context(1)
        self.front_sub = self.context.socket(zmq.SUB)
        self.front_sub.connect('tcp://%s:%d' % (host, front_pub_port(platform)))
        self.front_sub.setsockopt(zmq.SUBSCRIBE, b'')
        self.front_sub.RCVTIMEO = 250     # in milliseconds

    def run(self):
        logging.debug('MonitorThread starting')

        # as long as stopper event is not set, read messages
        # from front_sub socket and pass them to callback function.
        while not self.stopper.is_set():
            try:
                msg = self.front_sub.recv_json()
            except zmq.error.Again:
                pass    # socket timeout
            else:
                self.callback(msg)

        logging.debug('MonitorThread exiting')

class DaqControl:
    'Base class for controlling data acquisition'

    # transitionId is a subset of the TransitionId.hh enum
    transitionId = {
        'Unknown'           : 0,
        'Reset'             : 1,
        'Configure'         : 2,
        'Unconfigure'       : 3,
        'Enable'            : 4,
        'Disable'           : 5,
        'ConfigUpdate'      : 6,
        'BeginRecord'       : 7,
        'EndRecord'         : 8,
        'L1Accept'          : 12,
    }

    transitions = ['plat', 'alloc', 'dealloc',
                   'connect', 'disconnect',
                   'configure', 'unconfigure',
                   'beginrecord', 'endrecord',
                   'enable', 'disable',
                   'configupdate', 'reset']

    states = [
        'reset',
        'unallocated',
        'allocated',
        'connected',
        'paused',
        'running'
    ]

    def __init__(self, *, host, platform, timeout):
        self.host = host
        self.platform = platform
        self.timeout = timeout

        # initialize zmq socket
        self.context = zmq.Context(1)
        self.front_req = self.context.socket(zmq.REQ)
        self.front_req.linger = 0
        self.front_req.RCVTIMEO = timeout # in milliseconds
        self.front_req.connect('tcp://%s:%d' % (host, front_rep_port(platform)))

    #
    # DaqControl.getState - get current state
    #
    def getState(self):
        retval = 'error'
        try:
            msg = create_msg('getstate')
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            print('getState() Exception: %s' % ex)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')
        else:
            try:
                retval = reply['header']['key']
            except KeyError:
                pass

        return retval

    #
    # DaqControl.getPlatform - get platform
    #
    def getPlatform(self):
        retval = {}
        try:
            msg = create_msg('getstate')
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            print('getPlatform() Exception: %s' % ex)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')
        else:
            try:
                retval = reply['body']
            except KeyError:
                pass

        return retval

    #
    # DaqControl.selectPlatform - select platform
    #
    def selectPlatform(self, body):
        retval = {}
        try:
            msg = create_msg('selectplatform', body=body)
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            print('selectPlatform(): %s' % ex)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')
        else:
            try:
                retval = reply['body']
            except KeyError:
                pass

        return retval

    #
    # DaqControl.getStatus - get status
    #
    def getStatus(self):
        r1 = r2 = 'error'
        try:
            msg = create_msg('getstatus')
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            print('getStatus() Exception: %s' % ex)
        except KeyboardInterrupt:
            print('KeyboardInterrupt')
        else:
            try:
                r1 = reply['body']['transition']
                r2 = reply['body']['state']
            except KeyError:
                pass

        return (r1, r2)

    #
    # DaqControl.setState - change the state
    #
    def setState(self, state):
        errorMessage = None
        try:
            msg = create_msg('setstate.' + state)
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            errorMessage = 'setState() Exception: %s' % ex
        else:
            try:
                errorMessage = reply['body']['error']
            except KeyError:
                pass

        return errorMessage

    #
    # DaqControl.setTransition - trigger a transition
    #
    def setTransition(self, transition):
        errorMessage = None
        try:
            msg = create_msg(transition)
            self.front_req.send_json(msg)
            reply = self.front_req.recv_json()
        except Exception as ex:
            errorMessage = 'setTransition() Exception: %s' % ex
        else:
            try:
                errorMessage = reply['body']['error']
            except KeyError:
                pass

        return errorMessage

next_dict = {
    'reset' :       { 'unallocated' : 'plat',
                      'allocated' :   'plat',
                      'connected' :   'plat',
                      'paused' :      'plat',
                      'running' :     'plat' },

    'unallocated' : { 'reset' :       'reset',
                      'allocated' :   'alloc',
                      'connected' :   'alloc',
                      'paused' :      'alloc',
                      'running' :     'alloc' },

    'allocated' :   { 'reset' :       'dealloc',
                      'unallocated' : 'dealloc',
                      'connected' :   'connect',
                      'paused' :      'connect',
                      'running' :     'connect' },

    'connected' :   { 'reset' :       'disconnect',
                      'unallocated' : 'disconnect',
                      'allocated' :   'disconnect',
                      'paused' :      'configure',
                      'running' :     'configure' },

    'paused' :      { 'reset' :       'unconfigure',
                      'unallocated' : 'unconfigure',
                      'allocated' :   'unconfigure',
                      'connected' :   'unconfigure',
                      'running' :     'enable' },

    'running' :     { 'reset' :       'disable',
                      'unallocated' : 'disable',
                      'allocated' :   'disable',
                      'connected' :   'disable',
                      'paused' :      'disable' }
}

def timestampStr():
    current = datetime.now(timezone.utc)
    nsec = 1000 * current.microsecond
    sec = int(current.timestamp()) - POSIX_TIME_AT_EPICS_EPOCH
    return '%010d-%09d' % (sec, nsec)

def create_msg(key, msg_id=None, sender_id=None, body={}):
    if msg_id is None:
        msg_id = timestampStr()
    msg = {'header': {
               'key': key,
               'msg_id': msg_id,
               'sender_id': sender_id},
           'body': body}
    return msg


def back_pull_port(platform):
    return PORT_BASE + platform

def back_pub_port(platform):
    return PORT_BASE + platform + 10

def front_rep_port(platform):
    return PORT_BASE + platform + 20

def front_pub_port(platform):
    return PORT_BASE + platform + 30


def wait_for_answers(socket, wait_time, msg_id):
    """
    Wait and return all messages from socket that match msg_id
    Parameters
    ----------
    socket: zmq socket
    wait_time: int, wait time in milliseconds
    msg_id: int, expected msg_id of received messages
    """
    remaining = wait_time
    start = time.time()
    while socket.poll(remaining) == zmq.POLLIN:
        try:
            msg = socket.recv_json()
        except Exception as ex:
            logging.error('recv_json(): %s' % ex)
            continue
        else:
            logging.debug('recv_json(): %s' % msg)

        if msg['header']['msg_id'] == msg_id:
            yield msg
        else:
            logging.error('unexpected msg_id: got %s but expected %s' %
                          (msg['header']['msg_id'], msg_id))
        remaining = max(0, int(wait_time - 1000*(time.time() - start)))


def confirm_response(socket, wait_time, msg_id, ids):
    logging.debug('confirm_response(): ids = %s' % ids)
    msgs = []
    for msg in wait_for_answers(socket, wait_time, msg_id):
        if msg['header']['sender_id'] in ids:
            msgs.append(msg)
            ids.remove(msg['header']['sender_id'])
            logging.debug('confirm_response(): removed %s from ids' % msg['header']['sender_id'])
        else:
            logging.debug('confirm_response(): %s not in ids' % msg['header']['sender_id'])
        if len(ids) == 0:
            break
    for ii in ids:
        logging.debug('id %s did not respond' % ii)
    return len(ids), msgs


class CollectionManager():
    def __init__(self, platform):
        self.context = zmq.Context(1)
        self.back_pull = self.context.socket(zmq.PULL)
        self.back_pub = self.context.socket(zmq.PUB)
        self.front_rep = self.context.socket(zmq.REP)
        self.front_pub = self.context.socket(zmq.PUB)
        self.back_pull.bind('tcp://*:%d' % back_pull_port(platform))
        self.back_pub.bind('tcp://*:%d' % back_pub_port(platform))
        self.front_rep.bind('tcp://*:%d' % front_rep_port(platform))
        self.front_pub.bind('tcp://*:%d' % front_pub_port(platform))
        self.cmstate = {}
        self.ids = set()
        self.handle_request = {
            'selectplatform': self.handle_selectplatform,
            'getstate': self.handle_getstate,
            'getstatus': self.handle_getstatus
        }
        self.lastTransition = 'reset'

        self.collectMachine = Machine(self, DaqControl.states, initial='reset', after_state_change='report_status')

        self.collectMachine.add_transition('reset', '*', 'reset',
                                           conditions='condition_reset')
        self.collectMachine.add_transition('plat', ['reset', 'unallocated'], 'unallocated',
                                           conditions='condition_plat')
        self.collectMachine.add_transition('alloc', 'unallocated', 'allocated',
                                           conditions='condition_alloc')
        self.collectMachine.add_transition('dealloc', 'allocated', 'unallocated',
                                           conditions='condition_dealloc')
        self.collectMachine.add_transition('connect', 'allocated', 'connected',
                                           conditions='condition_connect')
        self.collectMachine.add_transition('disconnect', 'connected', 'allocated',
                                           conditions='condition_disconnect')
        self.collectMachine.add_transition('configure', 'connected', 'paused',
                                           conditions='condition_configure')
        self.collectMachine.add_transition('unconfigure', 'paused', 'connected',
                                           conditions='condition_unconfigure')
        self.collectMachine.add_transition('beginrecord', 'running', 'running',
                                           conditions='condition_beginrecord')
        self.collectMachine.add_transition('endrecord', 'running', 'running',
                                           conditions='condition_endrecord')
        self.collectMachine.add_transition('enable', 'paused', 'running',
                                           conditions='condition_enable')
        self.collectMachine.add_transition('disable', 'running', 'paused',
                                           conditions='condition_disable')
        self.collectMachine.add_transition('configupdate', 'paused', 'paused',
                                           conditions='condition_configupdate')

        logging.info('Initial state = %s' % self.state)

        # start main loop
        self.run()

    def run(self):
        try:
            while True:
                answer = None
                try:
                    msg = self.front_rep.recv_json()
                    key = msg['header']['key']
                    body = msg['body']
                    if key.startswith('setstate.'):
                        # handle_setstate() sends reply internally
                        self.handle_setstate(key[9:])
                        answer = None
                    elif key in DaqControl.transitions:
                        # send 'ok' reply before calling handle_trigger()
                        self.front_rep.send_json(create_msg('ok'))
                        retval = self.handle_trigger(key, stateChange=False)
                        answer = None
                        try:
                            # send error message, if any, to front_pub socket
                            message = retval['body']['error']
                            self.front_pub.send_json(self.error_msg(message))
                        except KeyError:
                            pass
                    else:
                        answer = self.handle_request[key](body)
                except KeyError:
                    answer = create_msg('error')
                if answer is not None:
                    self.front_rep.send_json(answer)
        except KeyboardInterrupt:
            logging.info('KeyboardInterrupt')

    def handle_trigger(self, key, *, stateChange=True):
        logging.debug('handle_trigger(\'%s\', stateChange=\'%s\') in state \'%s\'' % (key, stateChange, self.state))
        stateBefore = self.state
        trigError = None
        try:
            self.trigger(key)
        except MachineError as ex:
            logging.debug('MachineError: %s' % ex)
            trigError = str(ex)
        else:
            # check for error: trigger failed to change the state
            if stateChange and (self.state == stateBefore):
                trigError = '%s failed to change state' % key

        if trigError is None:
            answer = create_msg(self.state, body=self.cmstate)
        else:
            errMsg = trigError.replace("\"", "")
            logging.error(errMsg)
            answer = create_msg(self.state, body={'error': errMsg})

        return answer

    def next_transition(self, oldstate, newstate):
        try:
            retval = next_dict[oldstate][newstate]
        except Exception as ex:
            logging.error('next_transition(\'%s\', \'%s\'): %s' % (oldstate, newstate, ex))
            retval = 'error'

        logging.debug('next_transition(\'%s\', \'%s\') returning \'%s\'' % (oldstate, newstate, retval))
        return retval

    def handle_setstate(self, newstate):
        logging.debug('handle_setstate(\'%s\') in state %s' % (newstate, self.state))
        stateBefore = self.state

        if newstate not in DaqControl.states:
            stateError = 'state \'%s\' not recognized' % newstate
            errMsg = stateError.replace("\"", "")
            logging.error(errMsg)
            answer = create_msg('error', body={'error': errMsg})
            # reply 'error'
            self.front_rep.send_json(answer)
        else:
            answer = create_msg('ok')
            # reply 'ok'
            self.front_rep.send_json(answer)
            while self.state != newstate:
                nextT = self.next_transition(self.state, newstate)
                if nextT == 'error':
                    errMsg = 'next_transition() error'
                    logging.error(errMsg)
                    answer = create_msg('error', body={'error': errMsg})
                    break
                else:
                    answer = self.handle_trigger(nextT, stateChange=True)
                    if 'error' in answer['body']:
                        logging.error(answer['body']['error'])
                        break

        return answer

    def error_msg(self, message):
        body = {'error': message}
        return create_msg('error', body=body)

    def status_msg(self):
        body = {'state': self.state, 'transition': self.lastTransition}
        return create_msg('status', body=body)

    def report_status(self):
        logging.debug('status: state=%s transition=%s' % (self.state, self.lastTransition))
        self.front_pub.send_json(self.status_msg())

    def condition_alloc(self):
        # FIXME select all procs for now
        ids = copy.copy(self.ids)
        msg = create_msg('alloc', body={'ids': list(ids)})
        self.back_pub.send_json(msg)

        # make sure all the clients respond to alloc message with their connection info
        ret, answers = confirm_response(self.back_pull, 1000, msg['header']['msg_id'], ids)
        if ret:
            message = '%d client did not respond to alloc' % ret
            logging.error(message)
            self.front_pub.send_json(self.error_msg(message))
            logging.debug('condition_alloc() returning False')
            return False
        for answer in answers:
            id = answer['header']['sender_id']
            for level, item in answer['body'].items():
                self.cmstate[level][id].update(item)

        # give number to drp nodes for the event builder
        if 'drp' in self.cmstate:
            for i, node in enumerate(self.cmstate['drp']):
                self.cmstate['drp'][node]['drp_id'] = i

        # give number to teb nodes for the event builder
        if 'teb' in self.cmstate:
            for i, node in enumerate(self.cmstate['teb']):
                self.cmstate['teb'][node]['teb_id'] = i

        # give number to meb nodes for the event builder
        if 'meb' in self.cmstate:
            for i, node in enumerate(self.cmstate['meb']):
                self.cmstate['meb'][node]['meb_id'] = i

        logging.debug('cmstate after alloc:\n%s' % self.cmstate)
        self.lastTransition = 'alloc'
        logging.debug('condition_alloc() returning True')
        return True

    def condition_dealloc(self):
        # TODO
        self.lastTransition = 'dealloc'
        logging.debug('condition_dealloc() returning True')
        return True

    def condition_connect(self):
        # FIXME select all procs for now
        ids = copy.copy(self.ids)
        msg = create_msg('connect', body=self.cmstate)
        self.back_pub.send_json(msg)

        ret, answers = confirm_response(self.back_pull, 5000, msg['header']['msg_id'], ids)
        if ret:
            logging.error('%d client did not respond to connect' % ret)
            logging.debug('condition_connect() returning False')
            return False
        else:
            self.lastTransition = 'connect'
            logging.debug('condition_connect() returning True')
            return True

    def condition_disconnect(self):
        # TODO
        self.lastTransition = 'disconnect'
        logging.debug('condition_disconnect() returning True')
        return True

    def handle_getstate(self, body):
        logging.debug('handle_getstate()')
        return create_msg(self.state, body=self.cmstate)

    # returns last transition plus current state 
    def handle_getstatus(self, body):
        logging.debug('handle_getstatus()')
        return self.status_msg()

    def handle_selectplatform(self, body):
        logging.debug('handle_selectplatform()')
        if self.state != 'unallocated':
            message = 'selectPlatform only permitted in unallocated state'
            logging.error(message)
            msg = self.error_msg(message)
            self.front_pub.send_json(msg)
            return msg

        try:
            for key1, val1 in body.items():
                for key2, val2 in val1.items():
                    self.cmstate[key1][int(key2)]['active'] = body[key1][key2]['active']

        except Exception as ex:
            msg = 'handle_selectplatform(): %s' % ex
            logging.error(msg)
            return self.error_msg(msg)

        return create_msg('ok')

    def on_enter_reset(self):
        self.cmstate.clear()
        self.ids.clear()
        return

    def condition_plat(self):
        self.cmstate.clear()
        self.ids.clear()
        msg = create_msg('plat')
        self.back_pub.send_json(msg)
        for answer in wait_for_answers(self.back_pull, 1000, msg['header']['msg_id']):
            for level, item in answer['body'].items():
                if level not in self.cmstate:
                    self.cmstate[level] = {}
                id = answer['header']['sender_id']
                self.cmstate[level][id] = item
                self.cmstate[level][id]['active'] = 1   # default to active
                self.ids.add(id)
        self.lastTransition = 'plat'
        # should a nonempty platform be required for successful transition?
        logging.debug('condition_plat() returning True')
        logging.debug('cmstate after plat:\n%s' % self.cmstate)
        return True

    def filter_level(self, prefix, ids):
        matches = set()
        for level, item in self.cmstate.items():
            if level.startswith(prefix):
                for ii in ids:
                    if ii in item:
                        matches.add(ii)
                        break
        return matches

    def condition_common(self, transition, timeout):
        retval = True
        ids = copy.copy(self.ids)
        msg = create_msg(transition)
        self.back_pub.send_json(msg)

        # only drp group (aka level) responds to configure and above
        ids = self.filter_level('drp', ids)

        if len(ids) == 0:
            logging.debug('condition_common() empty set of ids')
            return True

        # make sure all the clients respond to transition before timeout
        ret, answers = confirm_response(self.back_pull, timeout, msg['header']['msg_id'], ids)
        if ret:
            # Error
            retval = False
            message = '%d client did not respond to %s' % (ret, transition)
            logging.error(message)
            self.front_pub.send_json(self.error_msg(message))
        else:
            retval = True
            for answer in answers:
                try:
                    for node, err_msg in answer['body']['err_info'].items():
                        # Error
                        retval = False
                        message = '%s: %s' % (node, err_msg)
                        logging.error(message)
                        self.front_pub.send_json(self.error_msg(message))
                except KeyError:
                    pass
        return retval

    def condition_configure(self):
        retval = self.condition_common('configure', 1000)
        if retval:
            self.lastTransition = 'configure'
        logging.debug('condition_configure() returning %s' % retval)
        return retval

    def condition_unconfigure(self):
        retval = self.condition_common('unconfigure', 1000)
        if retval:
            self.lastTransition = 'unconfigure'
        logging.debug('condition_unconfigure() returning %s' % retval)
        return retval

    def condition_beginrecord(self):
        retval = self.condition_common('beginrecord', 1000)
        if retval:
            self.lastTransition = 'beginrecord'
        logging.debug('condition_beginecord() returning %s' % retval)
        return retval

    def condition_endrecord(self):
        retval = self.condition_common('endrecord', 1000)
        if retval:
            self.lastTransition = 'endrecord'
        logging.debug('condition_endrecord() returning %s' % retval)
        return retval

    def condition_enable(self):
        retval = self.condition_common('enable', 1000)
        if retval:
            self.lastTransition = 'enable'
        logging.debug('condition_enable() returning %s' % retval)
        return retval

    def condition_disable(self):
        retval = self.condition_common('disable', 1000)
        if retval:
            self.lastTransition = 'disable'
        logging.debug('condition_disable() returning %s' % retval)
        return retval

    def condition_reset(self):
        # is a reply to reset necessary?
        msg = create_msg('reset')
        self.back_pub.send_json(msg)
        self.lastTransition = 'reset'
        logging.debug('condition_reset() returning True')
        return True

class Client:
    def __init__(self, platform):
        self.context = zmq.Context(1)
        self.back_push = self.context.socket(zmq.PUSH)
        self.back_sub = self.context.socket(zmq.SUB)
        self.back_push.connect('tcp://localhost:%d' % back_pull_port(platform))
        self.back_sub.connect('tcp://localhost:%d' % back_pub_port(platform))
        self.back_sub.setsockopt(zmq.SUBSCRIBE, b'')
        handle_request = {
            'plat': self.handle_plat,
            'alloc': self.handle_alloc,
            'connect': self.handle_connect
        }
        while True:
            try:
                msg = self.back_sub.recv_json()
                key = msg['header']['key']
                handle_request[key](msg)
            except KeyError as ex:
                logging.debug('KeyError: %s' % ex)

            if key == 'connect':
                break

    def handle_plat(self, msg):
        logging.debug('Client handle_plat()')
        # time.sleep(1.5)
        hostname = socket.gethostname()
        pid = os.getpid()
        self.id = hash(hostname+str(pid))
        body = {'drp': {'proc_info': {
                        'host': hostname,
                        'pid': pid}}}
        reply = create_msg('plat', msg['header']['msg_id'], self.id, body=body)
        self.back_push.send_json(reply)

    def handle_alloc(self, msg):
        logging.debug('Client handle_alloc()')
        body = {'drp': {'connect_info': {'infiniband': '123.456.789'}}}
        reply = create_msg('alloc', msg['header']['msg_id'], self.id, body)
        self.back_push.send_json(reply)
        self.state = 'alloc'

    def handle_connect(self, msg):
        logging.debug('Client handle_connect()')
        if self.state == 'alloc':
            reply = create_msg('ok', msg['header']['msg_id'], self.id)
            self.back_push.send_json(reply)


def main():
    from multiprocessing import Process

    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=int, choices=range(0, 8), default=0, help='platform (default 0)')
    parser.add_argument('-a', action='store_true', help='autoconnect')
    parser.add_argument('-v', action='store_true', help='be verbose')
    args = parser.parse_args()
    platform = args.p

    if args.v:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

    def manager():
        manager = CollectionManager(platform)

    def client(i):
        c = Client(platform)

    procs = [Process(target=manager)]
    for i in range(2):
        # procs.append(Process(target=client, args=(i,)))
        pass

    for p in procs:
        p.start()
        pass

    if args.a:
        # Commands
        context = zmq.Context(1)
        front_req = context.socket(zmq.REQ)
        front_req.connect('tcp://localhost:%d' % front_rep_port(platform))
        time.sleep(0.5)

        msg = create_msg('plat')
        front_req.send_json(msg)
        print('Answer to plat:', front_req.recv_multipart())

        msg = create_msg('alloc')
        front_req.send_json(msg)
        print('Answer to alloc:', front_req.recv_multipart())

        msg = create_msg('connect')
        front_req.send_json(msg)
        print('Answer to connect:', front_req.recv_multipart())

    for p in procs:
        try:
            p.join()
        except KeyboardInterrupt:
            pass

class SignalHandler:
    stopper = None
    def __init__(self, stopper):
        self.stopper = stopper

    def __call__(self, signum, frame):
        # set the stopper event
        self.stopper.set()

if __name__ == '__main__':
    main()

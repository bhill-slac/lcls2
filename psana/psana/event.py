
#import detectors

from psana import dgram
from psana.psexp.packet_footer import PacketFooter


# TO DO
# 1) remove comments
# 2) pass detector class table from run > dgrammgr > event
# 3) hook up the detector class table


class DrpClassContainer(object):
    def __init__(self):
            pass

class Event():
    """
    Event holds list of dgrams
    """
    def __init__(self, dgrams, det_class_table, size=0):
        self._det_class_table = det_class_table
        if size:
            self._dgrams = [0] * size
            self._offsets = [0] * size
            self._size = size
        else:
            self._dgrams = dgrams
            self._offsets = [_d._offset for _d in self._dgrams]
            self._size = len(dgrams)
            self._complete()
        self._position = 0

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    # we believe this can be hidden with underscores when we eliminate py2 support
    def next(self):
        if self._position >= len(self._dgrams):
            raise StopIteration
        event = self._dgrams[self._position]
        self._position += 1
        return event

    def _replace(self, pos, d):
        assert pos < self._size
        self._dgrams[pos] = d

    def _to_bytes(self):
        event_bytes = bytearray()
        pf = PacketFooter(self._size)
        for i, d in enumerate(self._dgrams):
            event_bytes.extend(bytearray(d))
            pf.set_size(i, memoryview(bytearray(d)).shape[0])

        if event_bytes:
            event_bytes.extend(pf.footer)

        return event_bytes

    @classmethod
    def _from_bytes(cls, configs, event_bytes):
        dgrams = []
        if event_bytes:
            pf = PacketFooter(view=event_bytes)
            views = pf.split_packets()
            assert len(configs) == len(views)
            dgrams = [dgram.Dgram(config=configs[i], view=views[i]) \
                    for i in range(len(configs))]
        evt = cls(dgrams, {})
        return evt
    
    @property
    def _seconds(self):
        _high = (self._dgrams[0].seq.timestamp() >> 32) & 0xffffffff
        return _high
    
    @property
    def _nanoseconds(self):
        _low = self._dgrams[0].seq.timestamp() & 0xffffffff
        return _low

    def _run(self):
        return 0 # for psana1-cctbx compatibility

    def _instantiate_det_xface(self,to_instantiate):
        for class_identifier,(det_xface_obj,dgrams) in to_instantiate.items():
            DetectorClass = self._det_class_table[class_identifier]
            detector_instance = DetectorClass(dgrams)
            drp_class_name = class_identifier[1]
            setattr(det_xface_obj, drp_class_name, detector_instance)

    def _add_det_xface(self):
        """
        """

        to_instantiate = {}
        for evt_dgram in self._dgrams:
            for det_name, det in evt_dgram.__dict__.items():

                # this gives us the intermediate "det" level
                # in the detector interface
                if hasattr(self, det_name):
                    det_xface_obj = getattr(self, det_name)
                else:
                    det_xface_obj = DrpClassContainer()
                    setattr(self, det_name, det_xface_obj)                

                # now the final "dgram" level
                for drp_class_name, dgram in det.__dict__.items():
                    class_identifier = (det_name,drp_class_name)
                    # IF the final level detector interface object is NOT instantiated
                    # THEN create the dictionary entry
                    if class_identifier not in to_instantiate.keys():
                        if class_identifier in self._det_class_table.keys():
                            to_instantiate[class_identifier] = (det_xface_obj,[dgram])
                        else:
                            # detector interface implementation not found
                            pass
                    else:
                        to_instantiate[class_identifier][1].append(dgram)

        # now that all the dgram lists are complete, instantiate
        self._instantiate_det_xface(to_instantiate)
        return

    # this routine is called when all the dgrams have been inserted into
    # the event (e.g. by the eventbuilder calling _replace())
    def _complete(self):
        self._add_det_xface()

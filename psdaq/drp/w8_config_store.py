from psalg.configdb.typed_json import cdict
import psalg.configdb.configdb as cdb
import sys
import argparse
import IPython
import pyrogue as pr

def lookupValue(d,name):
    key = name.split('.',1)
    if key[0] in d:
        v = d[key[0]]
        if isinstance(v,dict):
            return lookupValue(v,key[1])
        elif isinstance(v,bool):
            return 1 if v else 0
        else:
            return v
    else:
        return None
            
class mcdict(cdict):
    def __init__(self, fn=None):
        super().__init__(self)

        self._yamld = {}
        if fn:
            print('Loading yaml...')
            self._yamld = pr.yamlToData(fName=fn)

    #  intercept the set call to replace value with yaml definition
    def init(self, prefix, name, value, type="INT32", override=False, append=False):
        v = lookupValue(self._yamld,name)
        if v:
            print('Replace {:}[{:}] with [{:}]'.format(name,value,v))  
            value = v
        self.set(prefix+'.'+name, value, type, override, append)
    
def write_to_daq_config_db(detname,fn=None):

    #database contains collections which are sets of documents (aka json objects).
    #each type of device has a collection.  The elements of that collection are configurations of that type of device.
    #e.g. there will be OPAL, EVR, and YUNGFRAU will be collections.  How they are configured will be a document contained within that collection
    #Each hutch is also a collection.  Documents contained within these collection have an index, alias, and list of devices with configuration IDs
    #How is the configuration of a state is described by the hutch and the alias found.  E.g. TMO and BEAM.  TMO is a collection.  
    #BEAM is an alias of some of the documents in that collection. The document with the matching alias and largest index is the current 
    #configuration for that hutch and alias.  
    #When a device is configured, the device has a unique name OPAL7.  Need to search through document for one that has an NAME called OPAL7.  This will have
    #have two fields "collection" and ID field (note how collection here is a field. ID points to a unique document).  This collection field and 
    #ID point to the actuall Mongo DB collection and document

    create = True
    dbname = 'configDB'     #this is the name of the database running on the server.  Only client care about this name.
    instrument = 'tst'      #

    mycdb = cdb.configdb('mcbrowne:psana@psdb-dev:9306', instrument, create, dbname)    #mycdb.client.drop_database('configDB_szTest') will drop the configDB_szTest database
    mycdb.add_alias("BEAM")
    mycdb.add_device_config('wave8')
    
    top = mcdict(fn)
    top.setInfo('wave8', detname, 'serial1234', 'No comment')
    top.setAlg('config', [0,0,1])

    top.set("firmwareVersion:RO"          , 0,'UINT32')
    top.set("firmwareBuild:RO"            ,'','CHARSTR')

    top.define_enum('baselineEnum', {'%d samples'%(2**key):key for key in range(1,8)})
    top.define_enum('quadrantEnum', {'Even':0, 'Odd':1})

    #  Split configuration into two sections { User and Expert }
    #  Expert configuration is the basis, and User configuration overrides 
    #  Expert variables map directly to Rogue variables

    top.set("user.raw.start_ns"            ,107692,'UINT32')   # [ns from timing fiducial]
    top.set("user.raw.nsamples"            ,100,'UINT32')   # [250 MHz ADC samples]
    for i in range(8):
        top.set("user.raw.enable[%d]"%i    ,  1,'UINT8')    # record channel
    top.set("user.raw.prescale"            ,  1,'UINT32')   # record 1 out of N events
    top.set("user.fex.baseline"            ,  1,'baselineEnum')  # [log2 of 250 MHz ADC samples]
    top.set("user.fex.start_ns"            ,107892,'UINT32')   # [ns from timing fiducial]
    top.set("user.fex.nsamples"            , 50,'UINT32')   # [250 MHz ADC samples]
    for i in range(4):
        top.set("user.fex.coeff[%d]"%i     , 1.,'DOUBLE')   # coefficient in X,Y,I calculation

    top.init("expert","Top.SystemRegs.AvccEn0"         ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.AvccEn1"         ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.Ap5V5En"         ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.Ap5V0En"         ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.A0p3V3En"        ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.A1p3V3En"        ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.Ap1V8En"         ,  1,'UINT8')
    top.init("expert","Top.SystemRegs.FpgaTmpCritLatch",  0,'UINT8')
    top.init("expert","Top.SystemRegs.AdcReset"        ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.AdcCtrl1"        ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.AdcCtrl2"        ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.TrigEn"          ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.timingRxUserRst" ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.timingTxUserRst" ,  0,'UINT8')
    top.init("expert","Top.SystemRegs.timingUseMiniTpg",  0,'UINT8')
    top.init("expert","Top.SystemRegs.TrigSrcSel"      ,  1,'UINT8')

    top.init("expert","Top.Integrators.TrigDelay"             ,    0,'UINT32')  # user config
    top.init("expert","Top.Integrators.IntegralSize"          ,    0,'UINT32')  # user config
    top.init("expert","Top.Integrators.BaselineSize"          ,    0,'UINT8')  # user config
    top.init("expert","Top.Integrators.QuadrantSel"           ,    0,'quadrantEnum')  # user config
    for i in range(4):
        top.init("expert","Top.Integrators.CorrCoefficientFloat64[%d]"%i, 1.0, 'DOUBLE')  # user config
    top.init("expert","Top.Integrators.CntRst"                ,    0,'UINT8')
    top.init("expert","Top.Integrators.ProcFifoPauseThreshold",  255,'UINT32')
    top.init("expert","Top.Integrators.IntFifoPauseThreshold" ,  255,'UINT32')

    for i in range(8):
        top.init("expert","Top.RawBuffers.BuffEn[%d]"%i  ,   0,'UINT32')  # user config?
    top.init("expert","Top.RawBuffers.BuffLen"           , 100,'UINT32')  # user config?
    top.init("expert","Top.RawBuffers.CntRst"            ,   0,'UINT8')
    top.init("expert","Top.RawBuffers.FifoPauseThreshold", 100,'UINT32')
    top.init("expert","Top.RawBuffers.TrigPrescale"      , 0,'UINT32')   # user config

    top.init("expert","Top.BatcherEventBuilder.Bypass" , 0,'UINT8')
    top.init("expert","Top.BatcherEventBuilder.Timeout", 0,'UINT32')
    top.init("expert","Top.BatcherEventBuilder.Blowoff", 0,'UINT8')

    #  TriggerEventBuffer[x] - x should be hidden from application
    top.init("expert","Top.TriggerEventManager.TriggerEventBuffer[0].Partition"     , 0,'UINT8')
    top.init("expert","Top.TriggerEventManager.TriggerEventBuffer[0].PauseThreshold",16,'UINT8')
    top.init("expert","Top.TriggerEventManager.TriggerEventBuffer[0].TriggerDelay"  , 0,'UINT32')  # user config
    top.init("expert","Top.TriggerEventManager.TriggerEventBuffer[0].MasterEnable"  , 0,'UINT8')

    dlyAlane = [ [ 0x0c,0x0b,0x0e,0x0e,0x10,0x10,0x12,0x0b ],
                 [ 0x0a,0x08,0x0c,0x0b,0x0d,0x0c,0x0b,0x0c ],
                 [ 0x12,0x13,0x13,0x13,0x13,0x13,0x13,0x13 ],
                 [ 0x0d,0x0c,0x0d,0x0b,0x0a,0x12,0x12,0x13 ] ]
    dlyBlane = [ [ 0x11,0x11,0x12,0x12,0x10,0x11,0x0b,0x0b ],
                 [ 0x0a,0x0a,0x0c,0x0c,0x0c,0x0b,0x0b,0x0a ],
                 [ 0x14,0x14,0x14,0x14,0x14,0x12,0x10,0x11 ],
                 [ 0x13,0x12,0x13,0x12,0x12,0x11,0x12,0x11 ] ]

    for iadc in range(4):
        base = 'Top.AdcReadout[%d]'%iadc
        for lane in range(8):
            top.init('expert',base+'.DelayAdcALane[%d]'%lane, dlyAlane[iadc][lane], 'UINT8')
        for lane in range(8):
            top.init('expert',base+'.DelayAdcBLane[%d]'%lane, dlyBlane[iadc][lane], 'UINT8')
        top.init('expert',base+'.DMode'  , 3, 'UINT8')
        top.init('expert',base+'.Invert' , 0, 'UINT8')
        top.init('expert',base+'.Convert', 3, 'UINT8')

    for iadc in range(4):
        base = 'Top.AdcConfig[%d]'%iadc
        zeroregs = [7,8,0xb,0xc,0xf,0x10,0x11,0x12,0x12,0x13,0x14,0x16,0x17,0x18,0x20]
        for r in zeroregs:
            top.init('expert',base+'.AdcReg_0x%04X'%r,    0, 'UINT8')
        top.init('expert',base+'.AdcReg_0x0006'  , 0x80, 'UINT8')
        top.init('expert',base+'.AdcReg_0x000D'  , 0x6c, 'UINT8')
        top.init('expert',base+'.AdcReg_0x0015'  ,    1, 'UINT8')
        top.init('expert',base+'.AdcReg_0x001F'  , 0xff, 'UINT8')

    top.init('expert','Top.AdcPatternTester.Channel', 0, 'UINT8' )
    top.init('expert','Top.AdcPatternTester.Mask'   , 0, 'UINT8' )
    top.init('expert','Top.AdcPatternTester.Pattern', 0, 'UINT8' )
    top.init('expert','Top.AdcPatternTester.Samples', 0, 'UINT32' )
    top.init('expert','Top.AdcPatternTester.Request', 0, 'UINT8' )

    mycdb.add_alias('BEAM')
    mycdb.modify_device('BEAM', top)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Write a new wave8 configuration into the database')
    parser.add_argument('--name', help='Detector name', type=str, default='tstwave8')
    parser.add_argument('--yaml', help='Load values from yaml file', type=str, default='')
    args = parser.parse_args()

    write_to_daq_config_db(args.name, args.yaml)
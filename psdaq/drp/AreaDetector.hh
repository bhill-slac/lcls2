#ifndef AREA_DETECTOR_H
#define AREA_DETECTOR_H

#include "drp.hh"
#include "Detector.hh"
#include "xtcdata/xtc/Xtc.hh"
#include "xtcdata/xtc/NamesLookup.hh"

class AreaDetector : public Detector
{
public:
    AreaDetector(Parameters* para);
    void connect() override;
    unsigned configure(XtcData::Dgram& dgram) override;
    void event(XtcData::Dgram& dgram, PGPData* pgp_data) override;
private:
    enum {RawNamesIndex, FexNamesIndex};
    XtcData::NamesLookup m_namesLookup;
    unsigned m_evtcount;
};

#endif // AREA_DETECTOR_H

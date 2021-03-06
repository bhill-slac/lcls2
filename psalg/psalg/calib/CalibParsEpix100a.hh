#ifndef PSALG_CALIBPARSEPIX100A_H
#define PSALG_CALIBPARSEPIX100A_H
//-----------------------------

#include "psalg/calib/CalibPars.hh"

//using namespace std;
//using namespace calib;
using namespace psalg;

namespace calib {

//-----------------------------

class CalibParsEpix100a : public CalibPars {
public:

  CalibParsEpix100a(const char* detname="Epix100a", const DBTYPE& dbtype=DBWEB);
  virtual ~CalibParsEpix100a();

  void _default_msg(const std::string& msg=std::string()) const;

  /// access to calibration constants. DEFAULT IS USED IF UNDEFINED
  /*
  const NDArray<common_mode_t>&   common_mode      (Query&);
  const NDArray<pedestals_t>&     pedestals        (Query&);
  const NDArray<pixel_rms_t>&     rms              (Query&);
  const NDArray<pixel_status_t>&  status           (Query&);
  const NDArray<pixel_gain_t>&    gain             (Query&);
  const NDArray<pixel_offset_t>&  offset           (Query&);
  const NDArray<pixel_bkgd_t>&    background       (Query&);
  const NDArray<pixel_mask_t>&    mask_calib       (Query&);
  const NDArray<pixel_mask_t>&    mask_from_status (Query&);
  const NDArray<pixel_mask_t>&    mask_edges       (Query&);
  const NDArray<pixel_mask_t>&    mask_neighbors   (Query&);
  const NDArray<pixel_mask_t>&    mask_bits        (Query&);
  const NDArray<pixel_mask_t>&    mask             (Query&);

  /// access to geometry
  const geometry_t& geometry_str(Query&);
  const geometry_t& geometry(Query&);
  const NDArray<pixel_idx_t>&   indexes    (Query&);
  const NDArray<pixel_coord_t>& coords     (Query&);
  const NDArray<pixel_size_t>&  pixel_size (Query&);
  const NDArray<pixel_size_t>&  image_xaxis(Query&);
  const NDArray<pixel_size_t>&  image_yaxis(Query&);
  //virtual void move_geo(Query&);
  //virtual void tilt_geo(Query&);
  */

  CalibParsEpix100a(const CalibParsEpix100a&) = delete;
  CalibParsEpix100a& operator = (const CalibParsEpix100a&) = delete;

  //private:
  //NDArray<common_mode_t>  _common_mode;

}; // class

//-----------------------------

} // namespace calib

#endif // PSALG_CALIBPARSEPIX100A_H

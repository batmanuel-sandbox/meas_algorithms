// -*- lsst-c++ -*-
/* 
 * LSST Data Management System
 * Copyright 2008, 2009, 2010 LSST Corporation.
 * 
 * This product includes software developed by the
 * LSST Project (http://www.lsst.org/).
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the LSST License Statement and 
 * the GNU General Public License along with this program.  If not, 
 * see <http://www.lsstcorp.org/LegalNotices/>.
 */
 
#if !defined(LSST_MEAS_ALGORITHMS_COADDPSF_H)
#define LSST_MEAS_ALGORITHMS_COADDPSF_H
//!
// Describe an image's PSF
//
#include <boost/make_shared.hpp>
#include "ndarray/eigen.h"
#include "lsst/base.h"
#include "lsst/afw/detection/Psf.h"
#include "lsst/afw/detection/PsfFormatter.h"
#include "lsst/afw/image/Wcs.h"
#include "lsst/afw/geom/Box.h"
#include "lsst/afw/math/Kernel.h"

namespace afwImage = lsst::afw::image;
namespace afwGeom = lsst::afw::geom;
namespace lsst { namespace meas { namespace algorithms {

class CoaddPsfKernel : public lsst::afw::math::Kernel {
public:
 
    explicit CoaddPsfKernel() {
    };

    lsst::afw::math::Kernel::Ptr clone() const;

//  This is the critical piece of code to override.  The image needs to come from
//  the vector of PCA models, not from a spatially varying model itself
    double computeImage(
        afwImage::Image<double> &image,
        bool doNormalize,
        double x=0.0,
        double y=0.0
    ) const;

//  These methods are peculiar to the CoaddPsfKernel.  They are used to provide
//  the information about individual image psf's needed to supply a Psf at any point

    void addPsfComponent(PTR(lsst::afw::detection::Psf)  psf, PTR(lsst::afw::image::Wcs) wcs, lsst::afw::geom::Box2I bbox, double weight);

    int getComponentCount();

protected:


//  Vector of components used to house the information from individual images
private:
    struct Component {
        PTR(lsst::afw::detection::Psf) psf;
        PTR(lsst::afw::image::Wcs) wcs;
        lsst::afw::geom::Box2I bbox;
        double weight;
    };

    typedef std::vector<Component> ComponentVector;

    ComponentVector _components;
};

/*!
 * @brief Represent a PSF which is a stacked combination of Psfs from multiple images
 */
class CoaddPsf : public lsst::afw::detection::KernelPsf {
public:
    typedef PTR(CoaddPsf) Ptr;
    typedef CONST_PTR(CoaddPsf) ConstPtr;

    /**
     * @brief constructors for a CoadPsf
     *
     * Parameters:
     */
    explicit CoaddPsf();

    explicit CoaddPsf(PTR(lsst::afw::math::Kernel) kernel);

    explicit CoaddPsf(PTR(lsst::meas::algorithms::CoaddPsfKernel) kernel);

    virtual lsst::afw::detection::Psf::Ptr clone() const {
        return boost::make_shared<CoaddPsf>(*this); 
    }

    PTR(lsst::meas::algorithms::CoaddPsfKernel) getCoaddPsfKernel();
};

}}}

//BOOST_CLASS_EXPORT_GUID(lsst::meas::algorithms::CoaddPsf, "lsst::meas::algorithms::coaddPsf") // lowercase initial for backward compatibility


#endif

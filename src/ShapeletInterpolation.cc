
#include "lsst/meas/algorithms/ShapeletInterpolation.h"
#include "lsst/meas/algorithms/ShapeletPsfCandidate.h"

#include "lsst/meas/algorithms/shapelet/FittedPsf.h"
#include "lsst/meas/algorithms/shapelet/Bounds.h"

namespace lsst {
namespace meas {
namespace algorithms {

    class LoadCandidatesVisitor :
        public lsst::afw::math::CandidateVisitor 
    {
    public :
        typedef shapelet::Position Position;
        typedef shapelet::BVec BVec;
        typedef lsst::afw::math::SpatialCellCandidate SpatialCellCandidate;

        LoadCandidatesVisitor(
            std::vector<ShapeletPsfCandidate*>& cand,
            std::vector<Position>& pos,
            std::vector<BVec>& psf,
            std::vector<double>& nu,
            std::vector<long>& flags
        ) :
            _cand(cand), _pos(pos), _psf(psf), _nu(nu), _flags(flags)
        {}

        void reset() { }

        void processCandidate(SpatialCellCandidate* cand) 
        {
            ShapeletPsfCandidate* psfCand = 
                dynamic_cast<ShapeletPsfCandidate*>(cand);
            Assert(psfCand);
            _cand.push_back(psfCand);
            _pos.push_back(Position(psfCand->getX(),psfCand->getY()));
            _psf.push_back(psfCand->getShapelet()->viewAsBVec());
            // We already calculated nu for the rating...
            _nu.push_back(psfCand->getCandidateRating());
            _flags.push_back(long(0));
        }

        std::vector<ShapeletPsfCandidate*>& _cand;
        std::vector<Position>& _pos;
        std::vector<BVec>& _psf;
        std::vector<double>& _nu;
        std::vector<long>& _flags;
    };

    // All of the functionality is imported from shapelet::BVec
    // Just repeat the constructors, destructors, and op=
    class ShapeletInterpolationImpl
    {
    public :
        typedef lsst::pex::policy::Policy Policy;
        typedef lsst::afw::math::SpatialCellSet SpatialCellSet;
        typedef lsst::afw::image::Image<double> Image;
        typedef lsst::afw::image::Wcs Wcs;
        typedef lsst::afw::geom::PointD PointD;

        typedef shapelet::FittedPsf FittedPsf;

        ShapeletInterpolationImpl(const Policy& policy) 
        {
            shapelet::ConfigFile params;
            params["psf_order"] = policy.getInt("shapeletOrder");
            params["fitpsf_order"] = policy.getInt("interpOrder");
            params["fitpsf_nsigma_outlier"] = policy.getDouble("interpNSigmaClip");
            params["fitpsf_pca_thresh"] = policy.getDouble("pcaThresh");
            _fit.reset(new FittedPsf(params));
            _nStarsPerCell = policy.getInt("nStarsPerCell");
        }

        int getOrder() const { return _fit->getPsfOrder(); }

        int getFitOrder() const { return _fit->getFitOrder(); }

        double getSigma() const { return _fit->getSigma(); }

        int getSize() const { return (getOrder()+1)*(getOrder()+2)/2; }

        int getFitSize() const { return (getFitOrder()+1)*(getFitOrder()+2)/2; }

        void setSigma(double sigma) { _fit->setSigma(sigma); }

        void calculate(
            SpatialCellSet::Ptr cellSet,
            Image::ConstPtr image,
            Wcs::Ptr wcs,
            Image::ConstPtr weightImage)
        {
            using shapelet::Position;
            using shapelet::BVec;

            std::vector<ShapeletPsfCandidate*> cand;
            std::vector<Position> pos;
            std::vector<BVec> psf;
            std::vector<double> nu;
            std::vector<long> flags;

            LoadCandidatesVisitor visitor(cand,pos,psf,nu,flags);
            cellSet->visitCandidates(&visitor,_nStarsPerCell);

            // TODO: Currently, the rounds of outlier rejection are done
            // within FittedPSF, which means that we don't have the opportunity
            // to select other candidates that might be ok in that 
            // cell.  I should pull out some of that functionality, so I
            // can utilize the SpatialCells better.
            _fit->calculate(pos,psf,nu,flags);

            // Mark the flagged candidates as BAD.
            const int nCand = cand.size();
            for(int i=0; i<nCand; ++i) if (flags[i]) cand[i]->setBad();
        }

        Shapelet::Ptr interpolate(double x, double y)
        {
            shapelet::BVec b(getOrder(),getSigma());
            shapelet::Position pos(x,y);
            _fit->interpolate(pos,b);
            return Shapelet::Ptr(new Shapelet(b));
        }

        double interpolateSingleElement(double x, double y, int i)
        {
            shapelet::Position pos(x,y);
            return _fit->interpolateSingleElement(pos,i);
        }

    private :
        boost::shared_ptr<FittedPsf> _fit;
        int _nStarsPerCell;
    };

    ShapeletInterpolation::ShapeletInterpolation(const Policy& policy) :
        pImpl(new ShapeletInterpolationImpl(policy)) 
    {}

    ShapeletInterpolation::~ShapeletInterpolation()
    { delete pImpl; pImpl=0; }

    int ShapeletInterpolation::getOrder() const 
    { return pImpl->getOrder(); }

    int ShapeletInterpolation::getFitOrder() const 
    { return pImpl->getFitOrder(); }

    double ShapeletInterpolation::getSigma() const 
    { return pImpl->getSigma(); }

    int ShapeletInterpolation::getSize() const 
    { return pImpl->getSize(); }

    int ShapeletInterpolation::getFitSize() const 
    { return pImpl->getFitSize(); }

    void ShapeletInterpolation::setSigma(double sigma) 
    { pImpl->setSigma(sigma); }

    void ShapeletInterpolation::calculate(
        SpatialCellSet::Ptr cellSet,
        Image::ConstPtr image, Wcs::Ptr wcs, Image::ConstPtr weightImage)
    { pImpl->calculate(cellSet,image,wcs,weightImage); }

    Shapelet::Ptr ShapeletInterpolation::interpolate(const PointD& pos) const
    { return interpolate(pos.getX(),pos.getY()); }
    Shapelet::Ptr ShapeletInterpolation::interpolate(double x, double y) const
    { return pImpl->interpolate(x,y); }

    double ShapeletInterpolation::interpolateSingleElement(
        const PointD& pos, int i) const
    { return interpolateSingleElement(pos.getX(),pos.getY(),i); }
    double ShapeletInterpolation::interpolateSingleElement(
        double x, double y, int i) const
    { return pImpl->interpolateSingleElement(x,y,i); }

}}}


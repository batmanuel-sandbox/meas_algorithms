#
# LSST Data Management System
#
# Copyright 2008-2016  AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.
#
import unittest

import lsst.afw.detection as afwDet
import lsst.afw.image as afwImage
import lsst.afw.table as afwTable
import lsst.afw.geom as afwGeom
import lsst.meas.algorithms as measAlg
import lsst.utils.tests

try:
    type(display)
    import lsst.afw.display.ds9 as ds9
except NameError:
    display = False


def makeEmptyCatalog(psfCandidateField=None):
    """Return an empty catalog with a useful schema for psfCandidate testing.

    Parameters
    ----------
    psfCandidateField : `str` or None
        The name of a flag field to add to the schema.

    Returns
    -------
    catalog : `lsst.afw.table.SourceCatalog`
        The created (empty) catalog.
    """
    schema = afwTable.SourceTable.makeMinimalSchema()
    lsst.afw.table.Point2DKey.addFields(schema, "centroid", "centroid", "pixels")
    if psfCandidateField is not None:
        schema.addField(psfCandidateField, type="Flag", doc="Is a psfCandidate?")
    catalog = afwTable.SourceCatalog(schema)
    catalog.defineCentroid('centroid')

    return catalog


def createFakeSource(x, y, catalog, exposure, threshold=0.1):
    """Create a fake source at the given x/y centroid location.

    Parameters
    ----------
    x,y : `int`
        The x and y centroid coordinates to place the image at.
    catalog : `lsst.afw.table.SourceCatalog`
        The catalog to add the new source to.
    exposure : `lsst.afw.image.Exposure`
        The exposure to add the source to.
    threshold : `float`, optional
        The footprint threshold for identifying the source.

    Returns
    -------
    source : `lsst.afw.table.SourceRecord`
        The created source record that was added to ``catalog``.
    """
    source = catalog.addNew()
    source['centroid_x'] = x
    source['centroid_y'] = y

    exposure.getMaskedImage().getImage()[x, y] = 1.0
    fpSet = afwDet.FootprintSet(exposure.getMaskedImage(), afwDet.Threshold(threshold), "DETECTED")
    if display:
        ds9.mtv(exposure, frame=1)
        for fp in fpSet.getFootprints():
            for peak in fp.getPeaks():
                ds9.dot("x", peak.getIx(), peak.getIy(), frame=1)

    # There might be multiple footprints; only the one around x,y should go in the source
    found = False
    for fp in fpSet.getFootprints():
        if fp.contains(afwGeom.Point2I(x, y)):
            found = True
            break
    # We cannot continue if the the created source wasn't found.
    assert found, "Unable to find central peak in footprint: faulty test"

    source.setFootprint(fp)
    return source


class CandidateMaskingTestCase(lsst.utils.tests.TestCase):
    """Testing masking around PSF candidates."""

    def setUp(self):
        self.catalog = makeEmptyCatalog()

        self.x, self.y = 123, 45
        self.exposure = afwImage.ExposureF(256, 256)
        self.exposure.getMaskedImage().getVariance().set(0.01)

    def tearDown(self):
        del self.exposure
        del self.catalog

    def createCandidate(self, threshold=0.1):
        """Create a PSF candidate from self.exposure

        @param threshold: Threshold for creating footprints on image
        """
        source = createFakeSource(self.x, self.y, self.catalog, self.exposure, threshold)

        return measAlg.makePsfCandidate(source, self.exposure)

    def checkCandidateMasking(self, badPixels, extraPixels=[], size=25, threshold=0.1, pixelThreshold=0.0):
        """Check that candidates are masked properly

        We add various pixels to the image and investigate the masking.

        @param badPixels: (x,y,flux) triplet of pixels that should be masked
        @param extraPixels: (x,y,flux) triplet of additional pixels to add to image
        @param size: Size of candidate
        @param threshold: Threshold for creating footprints on image
        @param pixelThreshold: Threshold for masking pixels on candidate
        """
        image = self.exposure.getMaskedImage().getImage()
        for x, y, f in badPixels + extraPixels:
            image[x, y] = f
        cand = self.createCandidate(threshold=threshold)
        oldPixelThreshold = cand.getPixelThreshold()
        try:
            cand.setPixelThreshold(pixelThreshold)
            candImage = cand.getMaskedImage(size, size)
            mask = candImage.getMask()
            if display:
                ds9.mtv(candImage, frame=2)
                ds9.mtv(candImage.getMask().convertU(), frame=3)

            detected = mask.getMaskPlane("DETECTED")
            intrp = mask.getMaskPlane("INTRP")
            for x, y, f in badPixels:
                x -= self.x - size//2
                y -= self.y - size//2
                self.assertTrue(mask.get(x, y, intrp))
                self.assertFalse(mask.get(x, y, detected))
        finally:
            # Ensure this static variable is reset
            cand.setPixelThreshold(oldPixelThreshold)

    def testBlends(self):
        """Test that blended objects are masked."""
        """
        We create another object next to the one of interest,
        joined by a bridge so that they're part of the same
        footprint.  The extra object should be masked.
        """
        self.checkCandidateMasking([(self.x+2, self.y, 1.0)], [(self.x+1, self.y, 0.5)])

    def testNeighborMasking(self):
        """Test that neighbours are masked."""
        """
        We create another object separated from the one of
        interest, which should be masked.
        """
        self.checkCandidateMasking([(self.x+5, self.y, 1.0)])

    def testFaintNeighborMasking(self):
        """Test that faint neighbours are masked."""
        """
        We create another faint (i.e., undetected) object separated
        from the one of interest, which should be masked.
        """
        self.checkCandidateMasking([(self.x+5, self.y, 0.5)], threshold=0.9, pixelThreshold=1.0)


class MakePsfCandidatesTaskTest(lsst.utils.tests.TestCase):
    """Test MakePsfCandidatesTask on a handful of fake sources.

    Notes
    -----
    Does not test sources with NaN/Inf in their footprint. Also does not test
    any properties of the resulting PsfCandidates: those are assumed to be tested
    in ``CandidateMaskingTestCase`` above.
    """
    def setUp(self):
        self.psfCandidateField = "psfCandidate"
        self.catalog = makeEmptyCatalog(self.psfCandidateField)

        # id=0 is bad because it's on the edge, so fails with a WARN: LengthError.
        self.badIds = [1, ]
        self.goodIds = [2, 3]
        # x and y coordinate: keep these in sync with the above good/bad list.
        self.xCoords = [0, 100, 200]
        self.yCoords = [0, 100, 20]
        self.exposure = afwImage.ExposureF(256, 256)
        self.exposure.getMaskedImage().getVariance().set(0.01)
        for x, y in zip(self.xCoords, self.yCoords):
            createFakeSource(x, y, self.catalog, self.exposure, 0.1)

        self.makePsfCandidates = measAlg.MakePsfCandidatesTask()

    def testMakePsfCandidates(self):
        result = self.makePsfCandidates.run(self.catalog, self.exposure)
        self.assertEqual(len(result.psfCandidates), len(self.goodIds))

        for goodId in self.goodIds:
            self.assertIn(goodId, result.goodStarCat['id'])

        for badId in self.badIds:
            self.assertNotIn(badId, result.goodStarCat['id'])

    def testMakePsfCandidatesStarSelectedField(self):
        """Test MakePsfCandidatesTask setting a selected field."""
        result = self.makePsfCandidates.run(self.catalog,
                                            self.exposure,
                                            psfCandidateField=self.psfCandidateField)
        self.assertEqual(len(result.psfCandidates), len(self.goodIds))

        for goodId in self.goodIds:
            self.assertTrue(self.catalog.find(goodId).get(self.psfCandidateField))

        for badId in self.badIds:
            self.assertFalse(self.catalog.find(badId).get(self.psfCandidateField))


class TestMemory(lsst.utils.tests.MemoryTestCase):
    pass


def setup_module(module):
    lsst.utils.tests.init()


if __name__ == "__main__":
    lsst.utils.tests.init()
    unittest.main()

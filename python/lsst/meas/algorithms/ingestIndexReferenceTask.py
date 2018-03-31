#
# LSST Data Management System
#
# Copyright 2008-2017  AURA/LSST.
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
from __future__ import absolute_import, division, print_function

__all__ = ["IngestIndexedReferenceConfig", "IngestIndexedReferenceTask", "DatasetConfig"]

import numpy as np

import lsst.pex.config as pexConfig
import lsst.pipe.base as pipeBase
import lsst.afw.table as afwTable
import lsst.afw.geom as afwGeom
from lsst.afw.image import fluxFromABMag, fluxErrFromABMagErr
from .indexerRegistry import IndexerRegistry
from .readTextCatalogTask import ReadTextCatalogTask


class IngestReferenceRunner(pipeBase.TaskRunner):
    """!Task runner for the reference catalog ingester

    Data IDs are ignored so the runner should just run the task on the parsed command.
    """

    def run(self, parsedCmd):
        """!Run the task.
        Several arguments need to be collected to send on to the task methods.

        @param[in] parsedCmd  Parsed command including command line arguments.
        @param[out] Struct containing the result of the indexing.
        """
        files = parsedCmd.files
        butler = parsedCmd.butler
        task = self.TaskClass(config=self.config, log=self.log, butler=butler)
        task.writeConfig(parsedCmd.butler, clobber=self.clobberConfig, doBackup=self.doBackup)

        result = task.create_indexed_catalog(files)
        if self.doReturnResults:
            return pipeBase.Struct(
                result=result,
            )


class DatasetConfig(pexConfig.Config):
    ref_dataset_name = pexConfig.Field(
        dtype=str,
        default='cal_ref_cat',
        doc='String to pass to the butler to retrieve persisted files.',
    )
    indexer = IndexerRegistry.makeField(
        default='HTM',
        doc='Name of indexer algoritm to use.  Default is HTM',
    )


class IngestIndexedReferenceConfig(pexConfig.Config):
    dataset_config = pexConfig.ConfigField(
        dtype=DatasetConfig,
        doc="Configuration for reading the ingested data",
    )
    file_reader = pexConfig.ConfigurableField(
        target=ReadTextCatalogTask,
        doc='Task to use to read the files.  Default is to expect text files.'
    )
    ra_name = pexConfig.Field(
        dtype=str,
        doc="Name of RA column",
    )
    dec_name = pexConfig.Field(
        dtype=str,
        doc="Name of Dec column",
    )
    ra_err_name = pexConfig.Field(
        dtype=str,
        doc="Name of RA error column",
        optional=True,
    )
    dec_err_name = pexConfig.Field(
        dtype=str,
        doc="Name of Dec error column",
        optional=True,
    )
    mag_column_list = pexConfig.ListField(
        dtype=str,
        doc="The values in the reference catalog are assumed to be in AB magnitudes. "
            "List of column names to use for photometric information.  At least one entry is required."
    )
    mag_err_column_map = pexConfig.DictField(
        keytype=str,
        itemtype=str,
        default={},
        doc="A map of magnitude column name (key) to magnitude error column (value)."
    )
    is_photometric_name = pexConfig.Field(
        dtype=str,
        optional=True,
        doc='Name of column stating if satisfactory for photometric calibration (optional).'
    )
    is_resolved_name = pexConfig.Field(
        dtype=str,
        optional=True,
        doc='Name of column stating if the object is resolved (optional).'
    )
    is_variable_name = pexConfig.Field(
        dtype=str,
        optional=True,
        doc='Name of column stating if the object is measured to be variable (optional).'
    )
    id_name = pexConfig.Field(
        dtype=str,
        optional=True,
        doc='Name of column to use as an identifier (optional).'
    )
    pm_ra_name = pexConfig.Field(
        dtype=str,
        doc="Name of proper motion RA column",
        optional=True,
    )
    pm_dec_name = pexConfig.Field(
        dtype=str,
        doc="Name of proper motion Dec column",
        optional=True,
    )
    pm_ra_err_name = pexConfig.Field(
        dtype=str,
        doc="Name of proper motion RA error column",
        optional=True,
    )
    pm_dec_err_name = pexConfig.Field(
        dtype=str,
        doc="Name of proper motion Dec error column",
        optional=True,
    )
    pm_scale = pexConfig.Field(
        dtype=float,
        doc="Scale factor by which to multiply proper motion values to obtain units of milliarcsec/year",
        default=1.0,
    )
    epoch_name = pexConfig.Field(
        dtype=str,
        doc="Name of epoch column",
        optional=True,
    )
    epoch_poly = pexConfig.ListField(
        dtype=float,
        doc="Coefficients of ordinary polynomial to convert epoch values to MJD TAI, "
            "from zeroth to highest order. To convert from Unix time, use [40587.0, 1.0/86400].",
        default=[0.0],
    )
    extra_col_names = pexConfig.ListField(
        dtype=str,
        default=[],
        doc='Extra columns to add to the reference catalog.'
    )

    def validate(self):
        pexConfig.Config.validate(self)
        if not (self.ra_name and self.dec_name and self.mag_column_list):
            raise ValueError("ra_name and dec_name and at least one entry in mag_column_list must be" +
                             " supplied.")
        if (self.pm_ra_err_name is not None) != (self.pm_dec_err_name is not None):  # XOR
            raise ValueError("Only one of ra_err_name and dec_err_name has been specified")
        if len(self.mag_err_column_map) > 0 and not len(self.mag_column_list) == len(self.mag_err_column_map):
            raise ValueError("If magnitude errors are provided, all magnitudes must have an error column")
        if (sum(1 for col in ("pm_ra_name", "pm_dec_name", "epoch_name") if getattr(self, col) is not None)
            not in (0, 3)):
            raise ValueError("Only all or none of pm_ra_name, pm_dec_name and epoch_name may be specified")
        if (self.pm_ra_err_name is not None) != (self.pm_dec_err_name is not None):  # XOR
            raise ValueError("Only one of pm_ra_err_name and pm_dec_err_name has been specified")


class IngestIndexedReferenceTask(pipeBase.CmdLineTask):
    """!Class for both producing indexed reference catalogs and for loading them.

    This implements an indexing scheme based on hierarchical triangular mesh (HTM).
    The term index really means breaking the catalog into localized chunks called
    shards.  In this case each shard contains the entries from the catalog in a single
    HTM trixel
    """
    canMultiprocess = False
    ConfigClass = IngestIndexedReferenceConfig
    RunnerClass = IngestReferenceRunner
    _DefaultName = 'IngestIndexedReferenceTask'

    _flags = ['photometric', 'resolved', 'variable']

    @classmethod
    def _makeArgumentParser(cls):
        """Create an argument parser

        This overrides the original because we need the file arguments
        """
        parser = pipeBase.InputOnlyArgumentParser(name=cls._DefaultName)
        parser.add_argument("files", nargs="+", help="Names of files to index")
        return parser

    def __init__(self, *args, **kwargs):
        """!Constructor for the HTM indexing engine

        @param[in] butler  dafPersistence.Butler object for reading and writing catalogs
        """
        self.butler = kwargs.pop('butler')
        pipeBase.Task.__init__(self, *args, **kwargs)
        self.indexer = IndexerRegistry[self.config.dataset_config.indexer.name](
            self.config.dataset_config.indexer.active)
        self.epoch_poly = np.polynomial.Polynomial(self.config.epoch_poly)
        self.makeSubtask('file_reader')

    def create_indexed_catalog(self, files):
        """!Index a set of files comprising a reference catalog.  Outputs are persisted in the
        data repository.

        @param[in] files  A list of file names to read.
        """
        rec_num = 0
        first = True
        for filename in files:
            arr = self.file_reader.run(filename)
            index_list = self.indexer.index_points(arr[self.config.ra_name], arr[self.config.dec_name])
            if first:
                schema, key_map = self.make_schema(arr.dtype)
                # persist empty catalog to hold the master schema
                dataId = self.indexer.make_data_id('master_schema',
                                                   self.config.dataset_config.ref_dataset_name)
                self.butler.put(self.get_catalog(dataId, schema), 'ref_cat',
                                dataId=dataId)
                first = False
            pixel_ids = set(index_list)
            for pixel_id in pixel_ids:
                dataId = self.indexer.make_data_id(pixel_id, self.config.dataset_config.ref_dataset_name)
                catalog = self.get_catalog(dataId, schema)
                els = np.where(index_list == pixel_id)
                for row in arr[els]:
                    record = catalog.addNew()
                    rec_num = self._fill_record(record, row, rec_num, key_map)
                self.butler.put(catalog, 'ref_cat', dataId=dataId)
        dataId = self.indexer.make_data_id(None, self.config.dataset_config.ref_dataset_name)
        self.butler.put(self.config.dataset_config, 'ref_cat_config', dataId=dataId)

    @staticmethod
    def compute_coord(row, ra_name, dec_name):
        """!Create an ICRS SpherePoint from a np.array row
        @param[in] row  dict like object with ra/dec info in degrees
        @param[in] ra_name  name of RA key
        @param[in] dec_name  name of Dec key
        @param[out] ICRS SpherePoint constructed from the RA/Dec values
        """
        return afwGeom.SpherePoint(row[ra_name], row[dec_name], afwGeom.degrees)

    def _set_errors(self, record, row, key_map):
        """Set the coordinate errors from the input

        The errors are read from the specified columns, and installed
        in the appropriate columns of the output.

        Parameters
        ----------
        record : `lsst.afw.table.SourceRecord`
            Source record to modify.
        row : `dict`-like
            Row from numpy table.
        key_map : `dict` mapping `str` to `lsst.afw.table.Key`
            Map of catalog keys.
        """
        if self.config.ra_err_name is None:  # IngestIndexedReferenceConfig.validate ensures all or none
            record.set(key_map["coord_ra_err"], 0.0)
            record.set(key_map["coord_dec_err"], 0.0)
            return
        record.set(key_map["coord_ra_err"], row[self.config.ra_err_name])
        record.set(key_map["coord_dec_err"], row[self.config.dec_err_name])

    def _set_flags(self, record, row, key_map):
        """!Set the flags for a record.  Relies on the _flags class attribute
        @param[in,out] record  SourceCatalog record to modify
        @param[in] row  dict like object containing flag info
        @param[in] key_map  Map of catalog keys to use in filling the record
        """
        names = record.schema.getNames()
        for flag in self._flags:
            if flag in names:
                attr_name = 'is_{}_name'.format(flag)
                record.set(key_map[flag], bool(row[getattr(self.config, attr_name)]))

    def _set_mags(self, record, row, key_map):
        """!Set the flux records from the input magnitudes
        @param[in,out] record  SourceCatalog record to modify
        @param[in] row  dict like object containing magnitude values
        @param[in] key_map  Map of catalog keys to use in filling the record
        """
        for item in self.config.mag_column_list:
            record.set(key_map[item+'_flux'], fluxFromABMag(row[item]))
        if len(self.config.mag_err_column_map) > 0:
            for err_key in self.config.mag_err_column_map.keys():
                error_col_name = self.config.mag_err_column_map[err_key]
                record.set(key_map[err_key+'_fluxSigma'],
                           fluxErrFromABMagErr(row[error_col_name], row[err_key]))

    def _set_proper_motion(self, record, row, key_map):
        """Set the proper motions from the input

        The proper motions are read from the specified columns,
        scaled appropriately, and installed in the appropriate
        columns of the output.

        Parameters
        ----------
        record : `lsst.afw.table.SourceRecord`
            Source record to modify.
        row : `dict`-like
            Row from numpy table.
        key_map : `dict` mapping `str` to `lsst.afw.table.Key`
            Map of catalog keys.
        """
        if self.config.pm_ra_name is None:  # IngestIndexedReferenceConfig.validate ensures all or none
            return
        record.set(key_map["pmRa"], row[self.config.pm_ra_name]*self.config.pm_scale)
        record.set(key_map["pmDec"], row[self.config.pm_dec_name]*self.config.pm_scale)
        record.set(key_map["epoch"], self.epoch_poly(row[self.config.epoch_name]))
        if self.config.pm_ra_err_name is None or self.config.pm_dec_err_name is None:
            return
        record.set(key_map["pmRaErr"], row[self.config.pm_ra_err_name]*self.config.pm_scale)
        record.set(key_map["pmDecErr"], row[self.config.pm_dec_err_name]*self.config.pm_scale)

    def _set_extra(self, record, row, key_map):
        """!Copy the extra column information to the record
        @param[in,out] record  SourceCatalog record to modify
        @param[in] row  dict like object containing the column values
        @param[in] key_map  Map of catalog keys to use in filling the record
        """
        for extra_col in self.config.extra_col_names:
            value = row[extra_col]
            # If data read from a text file contains string like entires,
            # numpy stores this as its own internal type, a numpy.str_
            # object. This seems to be a consequence of how numpy stores
            # string like objects in fixed column arrays. This checks
            # if any of the values to be added to the catalog are numpy
            # string types, and if they are, casts them to a python string
            # which is what the python c++ records expect
            if isinstance(value, np.str_):
                value = str(value)
            record.set(key_map[extra_col], value)

    def _fill_record(self, record, row, rec_num, key_map):
        """!Fill a record to put in the persisted indexed catalogs

        @param[in,out] record  afwTable.SourceRecord in a reference catalog to fill.
        @param[in] row  A row from a numpy array constructed from the input catalogs.
        @param[in] rec_num  Starting integer to increment for the unique id
        @param[in] key_map  Map of catalog keys to use in filling the record
        """
        record.setCoord(self.compute_coord(row, self.config.ra_name, self.config.dec_name))
        if self.config.id_name:
            record.setId(row[self.config.id_name])
        else:
            rec_num += 1
            record.setId(rec_num)
        # No parents
        record.setParent(-1)

        self._set_errors(record, row, key_map)
        self._set_flags(record, row, key_map)
        self._set_mags(record, row, key_map)
        self._set_proper_motion(record, row, key_map)
        self._set_extra(record, row, key_map)
        return rec_num

    def get_catalog(self, dataId, schema):
        """!Get a catalog from the butler or create it if it doesn't exist

        @param[in] dataId  Identifier for catalog to retrieve
        @param[in] schema  Schema to use in catalog creation if the butler can't get it
        @param[out] afwTable.SourceCatalog for the specified identifier
        """
        if self.butler.datasetExists('ref_cat', dataId=dataId):
            return self.butler.get('ref_cat', dataId=dataId)
        return afwTable.SourceCatalog(schema)

    def make_schema(self, dtype):
        """!Make the schema to use in constructing the persisted catalogs.

        @param[in] dtype  A np.dtype to use in constructing the schema
        @param[out] The schema for the output source catalog.
        @param[out] A map of catalog keys to use in filling the record
        """
        key_map = {}
        mag_column_list = self.config.mag_column_list
        mag_err_column_map = self.config.mag_err_column_map
        if len(mag_err_column_map) > 0 and (
            not len(mag_column_list) == len(mag_err_column_map) or
                not sorted(mag_column_list) == sorted(mag_err_column_map.keys())):
            raise ValueError("Every magnitude column must have a corresponding error column")
        # makes a schema with a coord, id and parent_id
        schema = afwTable.SourceTable.makeMinimalSchema()

        def add_field(name):
            if dtype[name].kind == 'U':
                # dealing with a string like thing.  Need to get type and size.
                at_type = str
                at_size = dtype[name].itemsize
                return schema.addField(name, type=at_type, size=at_size)
            else:
                at_type = dtype[name].type
                return schema.addField(name, at_type)

        key_map["coord_ra_err"] = schema.addField("coord_ra_err", float)
        key_map["coord_dec_err"] = schema.addField("coord_dec_err", float)

        for item in mag_column_list:
            key_map[item+'_flux'] = schema.addField(item+'_flux', float)
        if len(mag_err_column_map) > 0:
            for err_item in mag_err_column_map.keys():
                key_map[err_item+'_fluxSigma'] = schema.addField(err_item+'_fluxSigma', float)
        for flag in self._flags:
            attr_name = 'is_{}_name'.format(flag)
            if getattr(self.config, attr_name):
                key_map[flag] = schema.addField(flag, 'Flag')
        if self.config.pm_ra_name is not None:  # pm_dec_name and epoch_name also; by validation
            key_map["pmRa"] = schema.addField("pmRa", float)
            key_map["pmDec"] = schema.addField("pmDec", float)
            key_map["epoch"] = schema.addField("epoch", float)
            if self.config.pm_ra_err_name is not None:  # pm_dec_err_name also; by validation
                key_map["pmRaErr"] = schema.addField("pmRaErr", float)
                key_map["pmDecErr"] = schema.addField("pmDecErr", float)
        for col in self.config.extra_col_names:
            key_map[col] = add_field(col)
        return schema, key_map

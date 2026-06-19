# -*- coding: utf-8 -*-
from qgis.PyQt import QtCore

class MenuStrings:
    """Strings appearing in the QGIS menu bar, submenus, and panels"""
    PLUGIN_NAME          = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Georef AR API")

    QUERIES_MENU_TITLE         = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Territorial and statistical areas")
    QUERIES_MENU_DESCRIPTION = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Territorial and statistical areas description")

    ADDRESSES_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "GeorefAR | Addresses")
    ADDRESSES_DESCRIPTION = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Addresses description")

    REVERSE_GEOREF_TITLE       = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "GeorefAR | Reverse Geocoding")
    REVERSE_GEOREF_DESCRIPTION = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Reverse Geocoding description")

    NEARBY_ESTABLISHMENT_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "GeorefAR | Nearby Establishments")
    NEARBY_ESTABLISHMENT_DESCRIPTION = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Nearby Establishments description")

    SETTINGS             = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Settings")
    ABOUT                = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "About")
    RUN_QUERY            = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Run Query")


class CategoryStrings:
    """Main Georef API categories used to group endpoints"""
    TERRITORIAL_DIVISIONS = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Territorial Divisions")
    INFRASTRUCTURE        = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Infrastructure and Streets")
    POINTS_OF_INTEREST    = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Points of Interest")


class ApiErrorStrings:
    """Global error messages for the QGIS message bar"""
    CONNECTION_FAILED = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Could not connect to Georef API. Please check your internet connection.")
    TIMEOUT           = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "The server took too long to respond. Please try again later.")
    HTTP_ERROR        = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "API Server Error (Status {code}).")


class HelpStrings:
    """General help or informational text"""
    NO_RESULTS    = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "The query returned no features. Try adjusting your filters.")
    SUCCESS_LAYER = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Layer successfully loaded into the project.")
# -*- coding: utf-8 -*-
from qgis.PyQt import QtCore

class MenuStrings:
    """Strings appearing in the QGIS menu bar, submenus, and panels"""
    PLUGIN_NAME = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Georef AR API")
    MENU_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Georef AR API")

    TERRITORIAL_UNITS_QUERIES_MENU_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Territorial units")

    GEOCODING_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Geocoding")
    GEOCODING_DESCRIPTION = QtCore.QCoreApplication.translate(
        'GeocodingDialog',
        "Allows standardizing and georeferencing a postal address using Georef services. "
        "Enter the address data, such as street, house number, and locality, to obtain its geographic location and "
        "associated territorial information. The results can be visualized directly on the map and used in "
        "subsequent spatial analyses."
    )

    REVERSE_GEOCODING_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Reverse Geocoding")
    REVERSE_GEOCODING_DESCRIPTION = QtCore.QCoreApplication.translate(
        'ReverseGeocodingDialog',
        "Allows obtaining territorial and addressing information from a geographic location. "
        "Enter the coordinates or select a point on the map to find the closest address—if it exists—and the different "
        "territorial units containing that point, such as province, department, municipality, and locality."
    )

    NEARBY_ESTABLISHMENT_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Nearby Establishments")
    NEARBY_ESTABLISHMENT_DESCRIPTION = QtCore.QCoreApplication.translate(
        'NearbyEstablishmentsDialog',
        "Allows locating public facilities and government agencies near a specific location. "
        "Select a point on the map or enter its coordinates, and specify the search radius, the maximum number of "
        "results, and the type of establishment to query. The results will be added to the project as a geographic "
        "layer for visualization and analysis."
    )

    SETTINGS_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "Settings")
    ABOUT_TITLE = QtCore.QCoreApplication.translate('GeorefQgisPlugin', "About")


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
import statsmodels.api as sm
import numpy as np
from scipy import optimize
import pvlib
import datetime
import pytz
from timezonefinder import TimezoneFinder
import pandas as pd
from scipy.interpolate import interp1d


def fit_tec_performance(technology, tec=None, climate_data=None):
    """
    Fits the performance parameters for a technology.
    :param technology: Dict read from json files with performance data and options for performance fits
    :return: dict of performance coefficients used in the model
    """
    # Initialize parameters dict
    parameters = dict()

    # Get options form file
    tec_type = technology['TechnologyPerf']['tec_type']
    if not (tec_type == 'RES'):
        tec_data = technology['TechnologyPerf']

    # Derive performance parameters for respective performance function type
    if tec_type == 'RES':  # Renewable technologies
        if tec == 'PV':
            if 'system_type' in technology:
                parameters['fit'] = perform_fitting_PV(climate_data, system_data=technology['system_type'])
            else:
                parameters['fit'] = perform_fitting_PV(climate_data)
        elif 'WT' in tec:
            if 'hubheight' in technology:
                hubheight = technology['hubheight']
            else:
                hubheight = 120
            parameters['fit'] = perform_fitting_WT(climate_data, technology['Name'], hubheight)


    elif tec_type == 'CONV2': # n inputs -> n output, fuel and output substitution
        parameters['fit'] = perform_fitting_tec_CONV2(tec_data)

    elif tec_type == 'STOR':  # storage technologies
        parameters['fit'] = perform_fitting_tec_STOR(tec_data, climate_data)

    parameters['TechnologyPerf'] = technology['TechnologyPerf']
    parameters['Economics'] = technology['Economics']
    return parameters

def perform_fitting_PV(climate_data, **kwargs):
    """
    Calculates capacity factors and specific area requirements for a PV system
    :param climate_data: contains information on weather data, and location
    :param PV_type: (optional) can specify a certain type of module
    :return: returns capacity factors and specific area requirements
    """
    # Todo: get perfect tilting angle
    if not kwargs.__contains__('system_data'):
        system_data = dict()
        system_data['tilt'] = 18
        system_data['surface_azimuth'] = 180
        system_data['module_name'] = 'SunPower_SPR_X20_327'
        system_data['inverter_eff'] = 0.96
    else:
        system_data = kwargs['system_data']

    def define_pv_system(location, system_data):
        """
        defines the pv system
        :param location: location information (latitude, longitude, altitude, time zone)
        :param system_data: contains data on tilt, surface_azimuth, module_name, inverter efficiency
        :return: returns PV model chain, peak power, specific area requirements
        """
        module_database = pvlib.pvsystem.retrieve_sam('CECMod')
        module = module_database[system_data['module_name']]

        # Define temperature losses of module
        temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

        # Create PV model chain
        inverter_parameters = {'pdc0': 5000, 'eta_inv_nom': system_data['inverter_eff']}
        system = pvlib.pvsystem.PVSystem(surface_tilt=system_data['tilt'],
                                         surface_azimuth=system_data['surface_azimuth'],
                                         module_parameters=module,
                                         inverter_parameters=inverter_parameters,
                                         temperature_model_parameters=temperature_model_parameters)

        pv_model = pvlib.modelchain.ModelChain(system, location, spectral_model="no_loss", aoi_model="physical")
        peakpower = module.STC
        specific_area = module.STC / module.A_c / 1000 / 1000

        return pv_model, peakpower, specific_area

    # Define parameters for convinience
    lon = climate_data['longitude']
    lat = climate_data['latitude']
    alt = climate_data['altitude']

    # Get location
    tf = TimezoneFinder()
    tz = tf.timezone_at(lng=lon, lat=lat)
    location = pvlib.location.Location(lat, lon, tz=tz, altitude=alt)

    # Initialize pv_system
    pv_model, peakpower, specific_area = define_pv_system(location, system_data)

    # Run system with climate data
    pv_model.run_model(climate_data['dataframe'])

    # Calculate cap factors
    power = pv_model.results.ac.p_mp
    capacity_factor = power / peakpower

    # return fit
    fitting = dict()
    fitting['capacity_factor'] = capacity_factor
    fitting['specific_area'] = specific_area
    return fitting

def perform_fitting_WT(climate_data, turbine_model, hubheight):
    # Load data for wind turbine type
    WT_data = pd.read_csv(r'.\data\technology_data\WT_data\WT_data.csv', delimiter=';')
    WT_data = WT_data[WT_data['TurbineName'] == turbine_model]

    # Load wind speed and correct for height
    ws = climate_data['dataframe']['ws10']

    #TODO: make power exponent choice possible
    #TODO: Make different heights possible
    alpha = 1/7
    # if data.node_data.windPowerExponent(node) >= 0
    #     alpha = data.node_data.windPowerExponent(node);
    # else:
    #     if data.node_data.offshore(node) == 1:
    #         alpha = 0.45;
    #     else:
    #         alpha = 1 / 7;

    if hubheight > 0:
        ws = ws * (hubheight / 10) ** alpha

    # Make power curve
    rated_power =  WT_data.iloc[0]['RatedPowerkW']
    x = np.linspace(0, 35, 71)
    y = WT_data.iloc[:,13:84]
    y = y.to_numpy()

    f = interp1d(x, y)
    capacity_factor = f(ws) / rated_power

    # return fit
    fitting = dict()
    fitting['capacity_factor'] = capacity_factor[0]
    fitting['rated_power'] = rated_power / 1000

    return fitting

def perform_fitting_tec_CONV2(tec_data):
    """
    Fits conversion technology type 2 and returns fitted parameters as a dict
    :param performance_data: contains X and y data of technology performance
    :param performance_function_type: options for type of performance function (linear, piecewise,...)
    :param nr_seg: number of segments on piecewise defined function
    """
    performance_data = tec_data['performance']
    performance_function_type = tec_data['performance_function_type']
    if 'nr_segments_piecewise' in performance_data:
        nr_seg = performance_data['nr_segments_piecewise']
    else:
        nr_seg = 2

    fitting = {}
    x = performance_data['in']
    for c in performance_data['out']:
        fitting[c] = dict()
        y = performance_data['out'][c]
        linmodel = sm.OLS(y, x)
        linfit = linmodel.fit()
        coeff = linfit.params
        fitting[c]['alpha1'] = round(coeff[0], 5)

    return fitting

def perform_fitting_tec_STOR(tec_data, climate_data):
    theta = tec_data['performance']['theta']

    fitting = {}
    fitting['ambient_loss_factor'] = (65 - climate_data['dataframe']['temp_air']) / (90 - 65) * theta
    for par in tec_data['performance']:
        if not par == 'theta':
            fitting[par] = tec_data['performance'][par]

    return fitting

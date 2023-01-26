import statsmodels.api as sm
import numpy as np
from scipy import optimize
import pvlib
import datetime
import pytz
from timezonefinder import TimezoneFinder
import pandas as pd
from scipy.interpolate import interp1d


def fit_netw_performance(network, climate_data=None):
    """
    Fits the performance parameters for a network, i.e. the consumption at each node.
    :param obj network: Dict read from json files with performance data and options for performance fits
    :param obj climate_data: Climate data
    :return: dict of performance coefficients used in the model
    """
    # Initialize parameters dict
    parameters = dict()

    # Get energy consumption at nodes form file
    network['NetworkPerf'].pop('energyconsumption')

    parameters['EnergyConsumption'] = {}

    parameters['NetworkPerf'] = network['NetworkPerf']
    parameters['Economics'] = network['Economics']
    parameters['connection'] = network['connection']
    parameters['distance'] = network['distance']
    return parameters

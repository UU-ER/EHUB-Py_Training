import src.data_management as dm
from pyomo.environ import units as u
import pandas as pd
import numpy as np
from src.energyhub import EnergyHub
from pyomo.environ import *

# TOPOLOGY
modeled_year = 2001

topology = {}
topology['timesteps'] = pd.date_range(start=str(modeled_year)+'-01-01 00:00', end=str(modeled_year)+'-12-31 23:00', freq='1h')

topology['timestep_length_h'] = 1
topology['carriers'] = ['electricity']
topology['nodes'] = ['onshore', 'offshore']
topology['technologies'] = {}
topology['technologies']['onshore'] = ['PV', 'battery']
topology['technologies']['offshore'] = []

topology['networks'] = {}
topology['networks']['electricitySimple'] = {}
network_data = dm.create_empty_network_data(topology['nodes'])
network_data['distance'].at['onshore', 'offshore'] = 100
network_data['distance'].at['offshore', 'onshore'] = 100
network_data['connection'].at['onshore', 'offshore'] = 1
network_data['connection'].at['offshore', 'onshore'] = 1
topology['networks']['electricitySimple'] = network_data

# Initialize instance of DataHandle
data = dm.DataHandle(topology)

# CLIMATE DATA
data.read_climate_data_from_file('onshore', '.\data\climate_data_onshore.txt')
data.read_climate_data_from_file('offshore', '.\data\climate_data_offshore.txt')

# DEMAND
electricity_demand = np.ones(len(topology['timesteps'])) * 10
data.read_demand_data('onshore', 'electricity', electricity_demand)

# READ TECHNOLOGY AND NETWORK DATA
data.read_technology_data()
data.read_network_data()

# # Read data
energyhub = EnergyHub(data)

# Construct equations
energyhub.construct_model()
energyhub.construct_balances()

# Solve model
energyhub.solve_model()
results = energyhub.write_results()
results.write_excel(r'.\userData\results')
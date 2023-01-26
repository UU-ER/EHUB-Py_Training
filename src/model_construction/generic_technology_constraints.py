from pyomo.environ import *
from pyomo.environ import units as u
from pyomo.gdp import *
import warnings
import src.config_model as m_config


def constraints_tec_RES(model, b_tec, tec_data):
    """
    Adds constraints to technology blocks for tec_type RES (renewable technology)

    **Parameter declarations:**

    - Capacity Factor of technology for each time step. The capacity factor has been calculated in
      ``src.model_construction.technology_performance_fitting``

    **Constraint declarations:**

    - Output of technology. The output can be curtailed in three different ways. For ``curtailment == 0``, there is
      no curtailment possible. For ``curtailment == 1``, the curtailment is continuous. For ``curtailment == 2``,
      the size needs to be an integer, and the technology can only be curtailed discretely, i.e. by turning full
      modules off. For ``curtailment == 0`` (default), it holds:

    .. math::
        Output_{t, car} = CapFactor_t * Size

    :param obj model: instance of a pyomo model
    :param obj b_tec: technology block
    :param tec_data: technology data
    :return: technology block
    """
    tec_fit = tec_data['fit']
    size_is_integer = tec_data['TechnologyPerf']['size_is_int']
    if size_is_integer:
        rated_power = tec_fit['rated_power']
    else:
        rated_power = 1

    if 'curtailment' in tec_data['TechnologyPerf']:
        curtailment = tec_data['TechnologyPerf']['curtailment']
    else:
        curtailment = 0

    # Set capacity factors as a parameter
    def init_capfactors(para, t):
        return tec_fit['capacity_factor'][t - 1]
    b_tec.para_capfactor = Param(model.set_t, domain=Reals, rule=init_capfactors)

    if curtailment == 0:  # no curtailment allowed (default)
        def init_input_output(const, t, c_output):
            return b_tec.var_output[t, c_output] == \
                   b_tec.para_capfactor[t] * b_tec.var_size * rated_power
        b_tec.const_input_output = Constraint(model.set_t, b_tec.set_output_carriers, rule=init_input_output)

    elif curtailment == 1:  # continuous curtailment
        def init_input_output(const, t, c_output):
            return b_tec.var_output[t, c_output] <= \
                   b_tec.para_capfactor[t] * b_tec.var_size * rated_power
        b_tec.const_input_output = Constraint(model.set_t, b_tec.set_output_carriers,
                                              rule=init_input_output)

    elif curtailment == 2:  # discrete curtailment
        b_tec.var_size_on = Var(model.set_t, within=NonNegativeIntegers, bounds=(b_tec.para_size_min, b_tec.para_size_max))
        def init_curtailed_units(const, t):
            return b_tec.var_size_on[t] <= b_tec.var_size
        b_tec.const_curtailed_units = Constraint(model.set_t, rule=init_curtailed_units)
        def init_input_output(const, t, c_output):
            return b_tec.var_output[t, c_output] == \
                   b_tec.para_capfactor[t] * b_tec.var_size_on[t] * rated_power
        b_tec.const_input_output = Constraint(model.set_t, b_tec.set_output_carriers,
                                              rule=init_input_output)

    return b_tec

def constraints_tec_CONV2(model, b_tec, tec_data):
    """
    Adds constraints to technology blocks for tec_type CONV2, i.e. :math:`output_{car} = f_{car}(\sum(inputs))`

    This technology type resembles a technology with full input substitution, but different performance functions
    for the respective output carriers.
    As for all conversion technologies, three different performance function fits are possible. The performance
    functions are fitted in ``src.model_construction.technology_performance_fitting``.

    **Constraint declarations:**

    - ``performance_function_type == 1``: Linear through origin, i.e.:

      .. math::
        Output_{t, car} == {\\alpha}_{1, car} \sum(Input_{t, car})

    - ``performance_function_type == 2``: Linear with minimal partload (makes big-m transformation required). If the
      technology is in on, it holds:

      .. math::
        Output_{t, car} = {\\alpha}_{1, car} \sum(Input_{t, car}) + {\\alpha}_{2, car}

      .. math::
        \sum(Input_{car}) \geq Input_{min} * S

      If the technology is off, input and output is set to 0:

      .. math::
         Output_{t, car} = 0

      .. math::
         \sum(Input_{t, car}) = 0

    - ``performance_function_type == 3``: Piecewise linear performance function (makes big-m transformation required).
      The same constraints as for ``performance_function_type == 2`` with the exception that the performance function
      is defined piecewise for the respective number of pieces

    :param obj model: instance of a pyomo model
    :param obj b_tec: technology block
    :param tec_data: technology data
    :return: technology block
    """
    tec_fit = tec_data['fit']
    performance_function_type = tec_data['TechnologyPerf']['performance_function_type']
    performance_data = tec_data['TechnologyPerf']

    alpha1 = {}
    # Get performance parameters
    for c in performance_data['performance']['out']:
        alpha1[c] = tec_fit[c]['alpha1']

    # LINEAR, NO MINIMAL PARTLOAD, THROUGH ORIGIN
    def init_input_output(const, t, car_output):
        return b_tec.var_output[t, car_output] == \
               alpha1[car_output] * sum(b_tec.var_input[t, car_input]
                                        for car_input in b_tec.set_input_carriers)
    b_tec.const_input_output = Constraint(model.set_t, b_tec.set_output_carriers,
                                          rule=init_input_output)

    # size constraint based on sum of inputs
    def init_size_constraint(const, t):
        return sum(b_tec.var_input[t, car_input] for car_input in b_tec.set_input_carriers) \
               <= b_tec.var_size
    b_tec.const_size = Constraint(model.set_t, rule=init_size_constraint)

    return b_tec

def constraints_tec_STOR(model, b_tec, tec_data):
    """
    Adds constraints to technology blocks for tec_type STOR, resembling a storage technology

    As for all conversion technologies, three different performance function fits are possible. The performance
    functions are fitted in ``src.model_construction.technology_performance_fitting``.
    Note that this technology only works for one carrier, and thus the carrier index is dropped in the below notation.

    **Parameter declarations:**
    - :math:`{\\eta}_{in}`: Charging efficiency

    - :math:`{\\eta}_{out}`: Discharging efficiency

    - :math:`{\\lambda}`: Self-Discharging coefficient (independent of environment)

    - :math:`ambientLossFactor`: Self-Discharging coefficient (dependent on environment)

    - :math:`Input_{max}`: Maximal charging capacity in one time-slice

    - :math:`Output_{max}`: Maximal discharging capacity in one time-slice

    **Variable declarations:**
    - Storage level in :math:`t`: :math:`E_t`

    **Constraint declarations:**
    - Maximal charging and discharging:

      .. math::
        Input_{t} \leq Input_{max} \\
        Output_{t} \leq Output_{max} \\

    - Size constraint:

      .. math::
        E_{t} \leq S

    - Storage level calculation:

      .. math::
        E_{t} = E_{t-1} * (1 - \\lambda) - ambientLossFactor * E_{t-1} + {\\eta}_{in} * Input_{t} - 1 / {\\eta}_{out} * Output_{t}

    - If ``allow_only_one_direction == 1``, then only input or output can be unequal to zero in each respective time
      step (otherwise, simultanous charging and discharging can lead to unwanted 'waste' of energy/material).

    :param obj model: instance of a pyomo model
    :param obj b_tec: technology block
    :param tec_data: technology data
    :return: technology block
    """

    tec_fit = tec_data['fit']
    if 'allow_only_one_direction' in tec_fit:
        allow_only_one_direction = tec_fit['allow_only_one_direction']
    else:
        allow_only_one_direction = 0

    # Additional decision variables
    b_tec.var_storage_level = Var(model.set_t, b_tec.set_input_carriers, domain=NonNegativeReals)

    # Additional parameters
    b_tec.para_eta_in = Param(domain=NonNegativeReals, initialize=tec_fit['eta_in'])
    b_tec.para_eta_out = Param(domain=NonNegativeReals, initialize=tec_fit['eta_out'])
    b_tec.para_eta_lambda = Param(domain=NonNegativeReals, initialize=tec_fit['lambda'])
    b_tec.para_charge_max = Param(domain=NonNegativeReals, initialize=tec_fit['charge_max'])
    b_tec.para_discharge_max = Param(domain=NonNegativeReals, initialize=tec_fit['discharge_max'])
    def init_ambient_loss_factor(para, t):
        return tec_fit['ambient_loss_factor'].values[t - 1]
    b_tec.para_ambient_loss_factor = Param(model.set_t, domain=NonNegativeReals, rule=init_ambient_loss_factor)

    # Size constraint
    def init_size_constraint(const, t, car):
        return b_tec.var_storage_level[t, car] <= b_tec.var_size
    b_tec.const_size = Constraint(model.set_t, b_tec.set_input_carriers, rule=init_size_constraint)

    # Storage level calculation
    def init_storage_level(const, t, car):
        if t == 1: # couple first and last time interval
            return b_tec.var_storage_level[t, car] == \
                  b_tec.var_storage_level[max(model.set_t), car] * (1 - b_tec.para_eta_lambda) - \
                  b_tec.para_ambient_loss_factor[max(model.set_t)] * b_tec.var_storage_level[max(model.set_t), car] + \
                  b_tec.para_eta_in * b_tec.var_input[t, car] - \
                  1 / b_tec.para_eta_out * b_tec.var_output[t, car]
        else: # all other time intervalls
            return b_tec.var_storage_level[t, car] == \
                b_tec.var_storage_level[t-1, car] * (1 - b_tec.para_eta_lambda) - \
                b_tec.para_ambient_loss_factor[t] * b_tec.var_storage_level[t-1, car] + \
                b_tec.para_eta_in * b_tec.var_input[t, car] - \
                1/b_tec.para_eta_out * b_tec.var_output[t, car]
    b_tec.const_storage_level = Constraint(model.set_t, b_tec.set_input_carriers, rule=init_storage_level)

    # This makes sure that only either input or output is larger zero.
    if allow_only_one_direction == 1:
        m_config.presolve.big_m_transformation_required = 1
        s_indicators = range(0, 2)

        def init_input_output(dis, t, ind):
            if ind == 0:  # input only
                def init_output_to_zero(const, car_input):
                    return b_tec.var_output[t, car_input] == 0
                dis.const_output_to_zero = Constraint(b_tec.set_input_carriers, rule=init_output_to_zero)

            elif ind == 1:  # output only
                def init_input_to_zero(const, car_input):
                    return b_tec.var_input[t, car_input] == 0
                dis.const_input_to_zero = Constraint(b_tec.set_input_carriers, rule=init_input_to_zero)

        b_tec.dis_input_output = Disjunct(model.set_t, s_indicators, rule=init_input_output)

        # Bind disjuncts
        def bind_disjunctions(dis, t):
            return [b_tec.dis_input_output[t, i] for i in s_indicators]
        b_tec.disjunction_input_output = Disjunction(model.set_t, rule=bind_disjunctions)

    def init_maximal_charge(const,t,car):
        return b_tec.var_input[t, car] <= b_tec.para_charge_max * b_tec.var_size
    b_tec.const_max_charge = Constraint(model.set_t, b_tec.set_input_carriers, rule=init_maximal_charge)

    def init_maximal_discharge(const,t,car):
        return b_tec.var_output[t, car] <= b_tec.para_discharge_max * b_tec.var_size
    b_tec.const_max_discharge = Constraint(model.set_t, b_tec.set_input_carriers, rule=init_maximal_discharge)

    return b_tec
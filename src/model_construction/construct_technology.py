import numbers
from src.model_construction.generic_technology_constraints import *
import src.model_construction as mc
import src.config_model as m_config



def add_technologies(nodename, set_tecsToAdd, model, data, b_node):
    r"""
    Adds all technologies as model blocks to respective node.

    This function initializes parameters and decision variables for all technologies at respective node.
    For each technology, it adds one block indexed by the set of all technologies at the node :math:`S_n`.
    This function adds Sets, Parameters, Variables and Constraints that are common for all technologies.
    For each technology type, individual parts are added. The following technology types are currently available:

    - Type RES: Renewable technology with cap_factor as input. Constructed with \
      :func:`src.model_construction.generic_technology_constraints.constraints_tec_RES`
    - Type CONV1: n inputs -> n output, fuel and output substitution. Constructed with \
      :func:`src.model_construction.generic_technology_constraints.constraints_tec_CONV1`
    - Type CONV2: n inputs -> n output, fuel substitution. Constructed with \
      :func:`src.model_construction.generic_technology_constraints.constraints_tec_CONV2`
    - Type CONV2: n inputs -> n output, no fuel and output substitution. Constructed with \
      :func:`src.model_construction.generic_technology_constraints.constraints_tec_CONV3`
    - Type STOR: Storage technology (1 input -> 1 output). Constructed with \
      :func:`src.model_construction.generic_technology_constraints.constraints_tec_STOR`

    **Set declarations:**

    - Set of input carriers
    - Set of output carriers

    **Parameter declarations:**

    - Min Size
    - Max Size
    - Output max (same as size max)
    - Unit CAPEX
    - Variable OPEX
    - Fixed OPEX

    **Variable declarations:**

    - Size (can be integer or continuous)
    - Input for each input carrier
    - Output for each output carrier
    - CAPEX
    - Variable OPEX
    - Fixed OPEX

    **Constraint declarations**
    - CAPEX, can be linear (for ``capex_model == 1``) or piecewise linear (for ``capex_model == 2``). Linear is defined as:

    .. math::
        CAPEX_{tec} = Size_{tec} * UnitCost_{tec}

    - Variable OPEX: defined per unit of output for the main carrier:

    .. math::
        OPEXvar_{t, tec} = Output_{t, maincarrier} * opex_{var} \forall t \in T

    - Fixed OPEX: defined as a fraction of annual CAPEX:

    .. math::
        OPEXfix_{tec} = CAPEX_{tec} * opex_{fix}

    :param str nodename: name of node for which technology is installed
    :param object b_node: pyomo block for respective node
    :param object model: pyomo model
    :param DataHandle data:  instance of a DataHandle
    :return: model
    """
    def init_technology_block(b_tec, tec):

        # region Get options from data
        tec_data = data.technology_data[nodename][tec]
        tec_type = tec_data['TechnologyPerf']['tec_type']
        capex_model = tec_data['Economics']['CAPEX_model']
        size_is_integer = tec_data['TechnologyPerf']['size_is_int']
        # endregion

        # region PARAMETERS

        # We need this shit because python does not accept single value in its build-in min function
        if isinstance(tec_data['TechnologyPerf']['size_min'], numbers.Number):
            size_min = tec_data['TechnologyPerf']['size_min']
        else:
            size_min = min(tec_data['TechnologyPerf']['size_min'])
        if isinstance(tec_data['TechnologyPerf']['size_max'], numbers.Number):
            size_max = tec_data['TechnologyPerf']['size_max']
        else:
            size_max = max(tec_data['TechnologyPerf']['size_max'])

        if size_is_integer:
            unit_size = u.dimensionless
        else:
            unit_size = u.MW
        b_tec.para_size_min = Param(domain=NonNegativeReals, initialize=size_min, units=unit_size)
        b_tec.para_size_max = Param(domain=NonNegativeReals, initialize=size_max, units=unit_size)
        b_tec.para_output_max = Param(domain=NonNegativeReals, initialize=size_max, units=u.MW)
        b_tec.para_unit_CAPEX = Param(domain=Reals, initialize=tec_data['Economics']['unit_CAPEX_annual'],
                                      units=u.EUR/unit_size)
        b_tec.para_OPEX_variable = Param(domain=Reals, initialize=tec_data['Economics']['OPEX_variable'],
                                         units=u.EUR/u.MWh)
        b_tec.para_OPEX_fixed = Param(domain=Reals, initialize=tec_data['Economics']['OPEX_fixed'],
                                      units=u.EUR/u.EUR)
        b_tec.para_tec_emissionfactor = Param(domain=Reals, initialize=tec_data['TechnologyPerf']['emission_factor'],
                                      units=u.t/u.MWh)

        # endregion

        # region SETS
        b_tec.set_input_carriers = Set(initialize=tec_data['TechnologyPerf']['input_carrier'])
        b_tec.set_output_carriers = Set(initialize=tec_data['TechnologyPerf']['output_carrier'])
        # endregion

        # region DECISION VARIABLES
        # Input
        if not tec_type == 'RES':
            b_tec.var_input = Var(model.set_t, b_tec.set_input_carriers, within=NonNegativeReals,
                                  bounds=(b_tec.para_size_min, b_tec.para_size_max), units=u.MW)
        # Output
        b_tec.var_output = Var(model.set_t, b_tec.set_output_carriers, within=NonNegativeReals,
                               bounds=(0, b_tec.para_output_max), units=u.MW)

        # Emissions
        b_tec.var_tec_emissions_pos = Var(within=NonNegativeReals, units=u.t)
        b_tec.var_tec_emissions_neg = Var(within=NonNegativeReals, units=u.t)

        # Size
        if size_is_integer:  # size
            b_tec.var_size = Var(within=NonNegativeIntegers, bounds=(b_tec.para_size_min, b_tec.para_size_max))
        else:
            b_tec.var_size = Var(within=NonNegativeReals, bounds=(b_tec.para_size_min, b_tec.para_size_max),
                                 units=u.MW)
        # Capex/Opex
        b_tec.var_CAPEX = Var(units=u.EUR)  # capex
        b_tec.var_OPEX_variable = Var(model.set_t, units=u.EUR)  # variable opex
        b_tec.var_OPEX_fixed = Var(units=u.EUR)  # fixed opex
        # endregion

        # region GENERAL CONSTRAINTS
        # Capex
        b_tec.const_CAPEX = Constraint(expr=b_tec.var_size * b_tec.para_unit_CAPEX == b_tec.var_CAPEX)

        # fixed Opex
        b_tec.const_OPEX_fixed = Constraint(expr=b_tec.var_CAPEX * b_tec.para_OPEX_fixed == b_tec.var_OPEX_fixed)

        # variable Opex
        def init_OPEX_variable(const, t):
            return sum(b_tec.var_output[t, car] for car in b_tec.set_output_carriers) * b_tec.para_OPEX_variable == \
                   b_tec.var_OPEX_variable[t]
        b_tec.const_OPEX_variable = Constraint(model.set_t, rule=init_OPEX_variable)

        # Emissions
        if tec_type == 'RES':
            # Set emissions to zero
            b_tec.const_tec_emissions_pos = Constraint(expr=b_tec.var_tec_emissions_pos == 0)
            b_tec.const_tec_emissions_neg = Constraint(expr=b_tec.var_tec_emissions_neg == 0)
        else:
            # Calculate emissions from emission factor
            def init_tec_emissions_pos(const):
                if tec_data['TechnologyPerf']['emission_factor'] >= 0:
                    return sum(b_tec.var_input[t, tec_data['TechnologyPerf']['main_input_carrier']]
                               for t in model.set_t) \
                           * b_tec.para_tec_emissionfactor \
                           == b_tec.var_tec_emissions_pos
                else:
                    return b_tec.var_tec_emissions_pos == 0
            b_tec.const_tec_emissions_pos = Constraint(rule=init_tec_emissions_pos)

            def init_tec_emissions_neg(const):
                if tec_data['TechnologyPerf']['emission_factor'] < 0:
                    return sum(b_tec.var_input[t, tec_data['TechnologyPerf']['main_input_carrier']]
                               for t in model.set_t) * \
                           (-b_tec.para_tec_emissionfactor) == \
                           b_tec.var_tec_emissions_neg
                else:
                    return b_tec.var_tec_emissions_neg == 0
            b_tec.const_tec_emissions_neg = Constraint(rule=init_tec_emissions_neg)


        # region TECHNOLOGY TYPES
        if tec_type == 'RES': # Renewable technology with cap_factor as input
            b_tec = constraints_tec_RES(model, b_tec, tec_data)

        elif tec_type == 'CONV2': # n inputs -> n output, fuel and output substitution
            b_tec = constraints_tec_CONV2(model, b_tec, tec_data)

        elif tec_type == 'STOR': # Storage technology (1 input -> 1 output)
            b_tec = constraints_tec_STOR(model, b_tec, tec_data)

        if m_config.presolve.big_m_transformation_required:
            mc.perform_disjunct_relaxation(b_tec)

        return b_tec

    # Create a new block containing all new technologies. The set of nodes that need to be added
    if b_node.find_component('tech_blocks_new'):
        b_node.del_component(b_node.tech_blocks_new)
    b_node.tech_blocks_new = Block(set_tecsToAdd, rule=init_technology_block)

    # If it exists, carry over active tech blocks to temporary block
    if b_node.find_component('tech_blocks_active'):
        b_node.tech_blocks_existing = Block(b_node.set_tecsAtNode)
        for tec in b_node.set_tecsAtNode:
            b_node.tech_blocks_existing[tec].transfer_attributes_from(b_node.tech_blocks_active[tec])
        b_node.del_component(b_node.tech_blocks_active)

    # Create a block containing all active technologies at node
    if not set(set_tecsToAdd).issubset(b_node.set_tecsAtNode):
        b_node.set_tecsAtNode.add(set_tecsToAdd)

    def init_active_technology_blocks(bl, tec):
        if tec in set_tecsToAdd:
            bl.transfer_attributes_from(b_node.tech_blocks_new[tec])
        else:
            bl.transfer_attributes_from(b_node.tech_blocks_existing[tec])
    b_node.tech_blocks_active = Block(b_node.set_tecsAtNode, rule=init_active_technology_blocks)

    if b_node.find_component('tech_blocks_new'):
        b_node.del_component(b_node.tech_blocks_new)
    if b_node.find_component('tech_blocks_existing'):
        b_node.del_component(b_node.tech_blocks_existing)
    return b_node

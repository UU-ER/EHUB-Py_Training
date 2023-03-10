Developer Instruction
=====================================
This page contains general instructions for the developers that are working on the EnergyHub.

Coding conventions
-----------------------
To keep the code consistent and clear for other developers, try to use the coding conventions that are described in this \
section as much as possible.

For the Pyomo classes we use:

+-------------+--------------+
| Type        | Code         |
+=============+==============+
| Objective   | objective... |
+-------------+--------------+
| Constraint  | const...     |
+-------------+--------------+
| Piecewise   | const...     |
+-------------+--------------+
| Set         | set...       |
+-------------+--------------+
| Block       | b...         |
+-------------+--------------+
| Var         | var...       |
+-------------+--------------+
| Param       | para...      |
+-------------+--------------+
| Disjunct    | dis...       |
+-------------+--------------+
| Disjunction | disjunction..|
+-------------+--------------+
| rule        | init...      |
+-------------+--------------+
| unit        | u            |
+-------------+--------------+

Other names that are regularly used in the EnergyHub are:

+-------------+--------------+
| Type        | Code         |
+=============+==============+
| Timestep    | t...         |
+-------------+--------------+
| Carrier     | car...       |
+-------------+--------------+
| Node        | node...      |
+-------------+--------------+
| Network     | netw...      |
+-------------+--------------+
| Technology  | tec...       |
+-------------+--------------+
| Consumption | cons...      |
+-------------+--------------+
| Input       | input...     |
+-------------+--------------+
| Output      | output...    |
+-------------+--------------+

Document your code!
-------------------
Please make sure to document your code properly. Each function should have a docstring at the beginning \
that shortly describes what the function does as well as input and return variables. This docstring \
is meant to appear in this documentation and should be written in a way that can be understood by \
users and not only developers. In addition, include comments in your code that are valuable hints for \
people reading your code. To create a new version of this website, you need to have \
`sphinx <https://sphinx-tutorial.readthedocs.io/>`_, a documentation tool for python. To create an \
html documentation website, you need to move to the ``.\docs`` folder in your terminal and execute \
either `.\make html` or simply `make html`.
We refer to the following guides on documentation:

* `PEP 8 - Style Guide for Python Code <https://peps.python.org/pep-0008/>`_
* `PEP 257 <https://peps.python.org/pep-0257/>`_ (also explained well `here <https://pandas.pydata.org/docs/development/contributing_docstring.html>`_)
* `Shinx Cheat Sheets <https://sphinx-tutorial.readthedocs.io/cheatsheet/>`_

As such, the documentation of a function can look like this:

.. testcode::

    def create_empty_network_data(nodes):
        """
        Function creating connection and distance matrices for defined nodes.

        :param list nodes: list of nodes to create matrices from
        :return: dictionary containing two pandas data frames with a distance and connection matrix respectively
        """
        # initialize return data dict
        data = {}

        # construct connection matrix
        matrix = pd.DataFrame(data=np.full((len(nodes), len(nodes)), 0),
                              index=nodes, columns=nodes)
        data['connection'] = matrix

        # construct distance matrix
        matrix = pd.DataFrame(data=np.full((len(nodes), len(nodes)), 0),
                              index=nodes, columns=nodes)
        data['distance'] = matrix
        return data


Testing new features
----------------------
The energyhub comes with a test suite, located in ``.\test``. For new features, try to implement a \
test function in one a respective module (or create a new module). All tests can be executed by \
running py.test from the terminal.
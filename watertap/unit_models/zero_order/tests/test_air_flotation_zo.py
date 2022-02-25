###############################################################################
# WaterTAP Copyright (c) 2021, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National
# Laboratory, National Renewable Energy Laboratory, and National Energy
# Technology Laboratory (subject to receipt of any required approvals from
# the U.S. Dept. of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#
###############################################################################
"""
Tests for zero-order air flotation model
"""
import pytest

from io import StringIO
from pyomo.environ import (
    ConcreteModel, Constraint, value, Var, assert_optimal_termination)
from pyomo.util.check_units import assert_units_consistent

from idaes.core import FlowsheetBlock
from idaes.core.util import get_solver
from idaes.core.util.model_statistics import degrees_of_freedom
from idaes.core.util.testing import initialization_tester

from watertap.unit_models.zero_order import AirFlotationZO
from watertap.core.wt_database import Database
from watertap.core.zero_order_properties import WaterParameterBlock

solver = get_solver()

class TestAirFloatationZO:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["tss"]})

        m.fs.unit = AirFlotationZO(default={
            "property_package": m.fs.params,
            "database": m.db})

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(10)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(1)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.energy_electric_flow_vol_inlet, Var)
        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("air_flotation")

        model.fs.unit.load_parameters_from_database()

        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert model.fs.unit.recovery_frac_mass_H2O[0].value == \
            data["recovery_frac_mass_H2O"]["value"]

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.energy_electric_flow_vol_inlet.fixed
        assert model.fs.unit.energy_electric_flow_vol_inlet.value == data[
            "energy_electric_flow_vol_inlet"]["value"]

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(1.1e-2, rel=1e-5) ==
                value(model.fs.unit.properties_in[0].flow_vol))
        assert (pytest.approx(90.9091, rel=1e-5) ==
                value(model.fs.unit.properties_in[0].conc_mass_comp["tss"]))
        assert (pytest.approx(0.010099, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].flow_vol))
        assert (pytest.approx(9.90197, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].conc_mass_comp["tss"]))
        assert (pytest.approx(9.01e-4, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].flow_vol))
        assert (pytest.approx(998.890, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].conc_mass_comp["tss"]))
        assert (pytest.approx(11.88, abs=1e-5) ==
                value(model.fs.unit.electricity[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-6 >= abs(value(
                model.fs.unit.inlet.flow_mass_comp[0, j] -
                model.fs.unit.treated.flow_mass_comp[0, j] -
                model.fs.unit.byproduct.flow_mass_comp[0, j]))

    @pytest.mark.component
    def test_report(self, model):
        stream = StringIO()

        model.fs.unit.report(ostream=stream)

        output = """
====================================================================================
Unit : fs.unit                                                             Time: 0.0
------------------------------------------------------------------------------------
    Unit Performance

    Variables: 

    Key                   : Value   : Fixed : Bounds
       Electricity Demand :  11.880 : False : (None, None)
    Electricity Intensity : 0.30000 :  True : (None, None)
     Solute Removal [tss] : 0.90000 :  True : (0, None)
           Water Recovery : 0.99990 :  True : (1e-08, 1.0000001)

------------------------------------------------------------------------------------
    Stream Table
                             Inlet   Treated  Byproduct
    Volumetric Flowrate    0.011000 0.010099 0.00090100
    Mass Concentration H2O   909.09   990.10     1.1099
    Mass Concentration tss   90.909   9.9020     998.89
====================================================================================
"""

        assert output in stream.getvalue()

class TestAirFlotationZO_w_default_removal:
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.db = Database()

        m.fs = FlowsheetBlock(default={"dynamic": False})
        m.fs.params = WaterParameterBlock(
            default={"solute_list": ["tss", "foo"]})

        m.fs.unit = AirFlotationZO(default={
            "property_package": m.fs.params,
            "database": m.db})

        m.fs.unit.inlet.flow_mass_comp[0, "H2O"].fix(10)
        m.fs.unit.inlet.flow_mass_comp[0, "tss"].fix(1)
        m.fs.unit.inlet.flow_mass_comp[0, "foo"].fix(1)

        return m

    @pytest.mark.unit
    def test_build(self, model):
        assert model.fs.unit.config.database == model.db

        assert isinstance(model.fs.unit.electricity, Var)
        assert isinstance(model.fs.unit.energy_electric_flow_vol_inlet, Var)
        assert isinstance(model.fs.unit.electricity_consumption, Constraint)

    @pytest.mark.component
    def test_load_parameters(self, model):
        data = model.db.get_unit_operation_parameters("air_flotation")

        model.fs.unit.load_parameters_from_database(use_default_removal=True)

        assert model.fs.unit.recovery_frac_mass_H2O[0].fixed
        assert model.fs.unit.recovery_frac_mass_H2O[0].value == \
            data["recovery_frac_mass_H2O"]["value"]

        for (t, j), v in model.fs.unit.removal_frac_mass_solute.items():
            assert v.fixed
            if j == "foo":
                assert v.value == data["default_removal_frac_mass_solute"]["value"]
            else:
                assert v.value == data["removal_frac_mass_solute"][j]["value"]

        assert model.fs.unit.energy_electric_flow_vol_inlet.fixed
        assert model.fs.unit.energy_electric_flow_vol_inlet.value == data[
            "energy_electric_flow_vol_inlet"]["value"]

    @pytest.mark.component
    def test_degrees_of_freedom(self, model):
        assert degrees_of_freedom(model.fs.unit) == 0

    @pytest.mark.component
    def test_unit_consistency(self, model):
        assert_units_consistent(model.fs.unit)

    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert_optimal_termination(results)

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(1.2e-2, rel=1e-5) ==
                value(model.fs.unit.properties_in[0].flow_vol))
        assert (pytest.approx(83.3333, rel=1e-5) ==
                value(model.fs.unit.properties_in[0].conc_mass_comp["tss"]))
        assert (pytest.approx(83.3333, rel=1e-5) ==
                value(model.fs.unit.properties_in[0].conc_mass_comp["foo"]))
        assert (pytest.approx(0.011099, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].flow_vol))
        assert (pytest.approx(9.00982, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].conc_mass_comp["tss"]))
        assert (pytest.approx(90.0982, rel=1e-5) ==
                value(model.fs.unit.properties_treated[0].conc_mass_comp["foo"]))
        assert (pytest.approx(9.01e-4, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].flow_vol))
        assert (pytest.approx(998.890, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].conc_mass_comp["tss"]))
        assert (pytest.approx(8.8790e-7, rel=1e-5) ==
                value(model.fs.unit.properties_byproduct[0].conc_mass_comp["foo"]))
        assert (pytest.approx(12.96, abs=1e-5) ==
                value(model.fs.unit.electricity[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        for j in model.fs.params.component_list:
            assert 1e-6 >= abs(value(
                model.fs.unit.inlet.flow_mass_comp[0, j] -
                model.fs.unit.treated.flow_mass_comp[0, j] -
                model.fs.unit.byproduct.flow_mass_comp[0, j]))

    @pytest.mark.component
    def test_report(self, model):
        stream = StringIO()

        model.fs.unit.report(ostream=stream)

        output = """
====================================================================================
Unit : fs.unit                                                             Time: 0.0
------------------------------------------------------------------------------------
    Unit Performance

    Variables: 

    Key                   : Value   : Fixed : Bounds
       Electricity Demand :  12.960 : False : (None, None)
    Electricity Intensity : 0.30000 :  True : (None, None)
     Solute Removal [foo] :  0.0000 :  True : (0, None)
     Solute Removal [tss] : 0.90000 :  True : (0, None)
           Water Recovery : 0.99990 :  True : (1e-08, 1.0000001)

------------------------------------------------------------------------------------
    Stream Table
                             Inlet   Treated  Byproduct
    Volumetric Flowrate    0.012000 0.011099 0.00090100
    Mass Concentration H2O   833.33   900.89     1.1099
    Mass Concentration tss   83.333   9.0098     998.89
    Mass Concentration foo   83.333   90.098 8.8790e-07
====================================================================================
"""

        assert output in stream.getvalue()
import os
import jinja2

class PulseConfigGenerator():
    def __init__(self) -> None:
        self.template = """
from pathlib import Path

from pulse.cdm.engine import eSwitch, eSerializationFormat
from pulse.cdm.engine import SEDataRequestManager, SEDataRequest
from pulse.cdm.patient import SEPatientConfiguration
from pulse.cdm.patient_actions import SEPrimaryBlastLungInjury
from pulse.cdm.physiology import eLungCompartment
from pulse.cdm.scalars import FrequencyUnit, LengthUnit, MassUnit, PressureUnit, \
                              TimeUnit, VolumeUnit

from pulse.engine.PulseEngine import PulseEngine
from pulse.engine.PulseConfiguration import PulseConfiguration

def HowTo_ExpandedRespiratory():
    pulse = PulseEngine()
    pulse.set_log_filename("./test_results/howto/HowTo_ExpandedRespiratory.py.log")
    pulse.log_to_console(True)

    cfg = PulseConfiguration()
    cfg.set_expanded_respiratory(eSwitch.On)
    pulse.set_configuration_override(cfg)
    data_requests = [
        {% for request in data_requests %}
        SEDataRequest.create_physiology_request("{{ request.name }}", unit={{ request.unit }}),
        {% endfor %}
    ]
    data_req_mgr = SEDataRequestManager(data_requests)

    state_filename = Path("./test_results/howto/Satish.json")
    if state_filename.exists():
        pulse.serialize_from_file(str(state_filename), data_req_mgr)
    else:
        pc = SEPatientConfiguration()
        p = pc.get_patient()
        p.set_name("Satish")
        p.get_age().set_value(22, TimeUnit.yr)
        p.get_height().set_value(72, LengthUnit.inch)
        p.get_weight().set_value(180, MassUnit.lb)
        if not pulse.initialize_engine(pc, data_req_mgr):
            print("Unable to load stabilize engine")
            return
        pulse.serialize_to_file(str(state_filename))

    results = pulse.pull_data()
    pulse.print_results()

    pulse.advance_time_s(30)
    results = pulse.pull_data()
    pulse.print_results()

    pbli = SEPrimaryBlastLungInjury()
    {% for severity in compartment_severities %}
    pbli.get_severity(eLungCompartment.{{ severity.compartment }}).set_value({{ severity.value }})
    {% endfor %}
    pulse.process_action(pbli)

    pulse.advance_time_s({{ max_time_of_sim }})
    results = pulse.pull_data()
    pulse.print_results()
HowTo_ExpandedRespiratory()
"""

    def generate_py_script(self, data, projectid):
        # Create a Jinja2 environment and load the template
        template = jinja2.Template(self.template)
        rendered_script = template.render(data)

        # Ensure the directory exists
        directory_path = os.path.join(f'./projects/{projectid}/Physiology')
        os.makedirs(directory_path, exist_ok=True)

        # Write the script to a file
        script_path = os.path.join(directory_path, 'pulse_script.py')
        with open(script_path, 'w') as file:
            file.write(rendered_script)

        return f'./projects/{projectid}/pulse_script.py'

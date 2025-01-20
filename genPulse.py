import os
import jinja2

class PulseConfigGenerator:
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
    pulse.set_log_filename("./pulse.log")
    pulse.log_to_console(True)

    cfg = PulseConfiguration()
    cfg.set_expanded_lung(eSwitch.On)
    pulse.set_configuration_override(cfg)

    data_requests = [
        {% for request, include in data_requests.items() if include %}
        {% if request_units[request] %}
        SEDataRequest.create_physiology_request("{{ request }}", unit={{ request_units[request] }}),
        {% else %}
        SEDataRequest.create_physiology_request("{{ request }}"),
        {% endif %}
        {% endfor %}
    ]
    data_req_mgr = SEDataRequestManager(data_requests)
    data_req_mgr.set_results_filename("pulseresults.csv")

    state_filename = Path("./test_results/howto/Satish.json")
    if state_filename.exists():
        pulse.serialize_from_file(str(state_filename), data_req_mgr)
    else:
        pc = SEPatientConfiguration()
        p = pc.get_patient()
        p.set_name("UNDEX Patient")
        p.get_age().set_value(22, TimeUnit.yr)
        p.get_height().set_value(72, LengthUnit.inch)
        p.get_weight().set_value(180, MassUnit.lb)
        if not pulse.initialize_engine(pc, data_req_mgr):
            print("Unable to load stabilize engine")
            return
        pulse.serialize_to_file(str(state_filename))

    results = pulse.pull_data()
    pulse.print_results()
    severity = None
    if {{ peakPressureCriterion }}:
        chargeDistance = {{ peakPressureData['distanceTillCharge'] }} * 3.28084
        chargeMass = {{ peakPressureData['massOfCharge'] }} * 2.20462
        peakPressure = 13000 * (chargeMass ** 0.33) / chargeDistance
        # PBLI severity mapping
        severity = 0.0005 * peakPressure
        # Bounding the severity between 0 and 1
        severity = max(min(severity, 1.0), 0.0)

        print(f"Charge Mass: {chargeMass} lbs")
        print(f"Charge Distance: {chargeDistance} ft")
        print(f"Peak Pressure: {peakPressure} mmHg")
        print(f"Severity: {severity}")

    pulse.advance_time_s(30)
    results = pulse.pull_data()
    pulse.print_results()

    pbli = SEPrimaryBlastLungInjury()

    if {{ peakPressureCriterion }}:
       {% for key in damages %}
       pbli.get_severity(eLungCompartment.{{ key }}).set_value(severity)
       {% endfor %}
    else:
       {% for key, value in damages.items() %}
       pbli.get_severity(eLungCompartment.{{ key }}).set_value({{ value }})
       {% endfor %}

    pulse.process_action(pbli)

    pulse.advance_time_s({{ max_time_of_sim }})
    results = pulse.pull_data()
    pulse.print_results()
HowTo_ExpandedRespiratory()
"""

    def generate_py_script(self, data, userid, projectid, caseid):
        # Define unit mappings for each request type
        request_units = {
            'HeartRate': 'FrequencyUnit.Per_min',
            'ArterialPressure': 'PressureUnit.mmHg',
            'MeanArterialPressure': 'PressureUnit.mmHg',
            'SystolicArterialPressure': 'PressureUnit.mmHg',
            'DiastolicArterialPressure': 'PressureUnit.mmHg',
            'EndTidalCarbonDioxidePressure': 'PressureUnit.mmHg',
            'HorowitzIndex': 'PressureUnit.mmHg',
            'OxygenSaturation': None,  # No unit for OxygenSaturation
            'RespirationRate': 'FrequencyUnit.Per_min',
            'TidalVolume': 'VolumeUnit.mL',
            'TotalLungVolume': 'VolumeUnit.mL',
            'ArterialOxygenPressure': 'PressureUnit.mmHg',
            'ArterialCarbonDioxidePressure': 'PressureUnit.mmHg',
            'LeftLungPulmonary': 'VolumeUnit.mL',  # Example
            'RightLungPulmonary': 'VolumeUnit.L',   # Example
        }

        # Create a Jinja2 environment and load the template
        template = jinja2.Template(self.template)
        rendered_script = template.render(data_requests=data['results'],
                                          request_units=request_units,
                                          damages=data['cardioModel']['damages'],
                                          max_time_of_sim=data['simSettings']['maxSimTime'],
                                          peakPressureCriterion=data['peakPressure'],
                                          peakPressureData=data['pressureCriterion'])

        # Ensure the directory exists
        directory_path = os.path.join(f'./projects/{userid}/{projectid}/{caseid}/Physiology')
        os.makedirs(directory_path, exist_ok=True)

        # Write the script to a file
        script_path = os.path.join(directory_path, 'runPulse.py')
        with open(script_path, 'w') as file:
            file.write(rendered_script)

        return f'./projects/{userid}/{projectid}/{caseid}/Physiology/runPulse.py'

# Example usage
data = {
    'results': {
        'HeartRate': True,
        'ArterialPressure': True,
        'MeanArterialPressure': True,
        'SystolicArterialPressure': True,
        'DiastolicArterialPressure': True,
        'EndTidalCarbonDioxidePressure': True,
        'HorowitzIndex': True,
        'OxygenSaturation': True,
        'RespirationRate': True,
        'TidalVolume': True,
        'TotalLungVolume': True,
        'ArterialOxygenPressure': True,
        'ArterialCarbonDioxidePressure': True
    },
    'cardioModel': {
        'damages': {
            'RightLung': 0.5,
            'LeftLung': 0.3
        }
    },
    'simSettings': {
        'maxSimTime': 300
    },
    'peakPressure': True,
    'pressureCriterion': {
        'distanceTillCharge': 10,
        'massOfCharge': 5
    }
}


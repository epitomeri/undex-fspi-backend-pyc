from xml.etree import ElementTree as ET
import time
import os

def get_log_enabled(file_path):

    with open(file_path, 'r') as file:
        lines = file.readlines()

    log_section = []
    log_section_started = False
    for line in lines:
        if '<log enabled=' in line:
            log_section_started = True
        if log_section_started:
            log_section.append(line)
        if '</log>' in line:
            break

    log_section_xml = ''.join(log_section)

    log_tree = ET.ElementTree(ET.fromstring(log_section_xml))
    log_root = log_tree.getroot()

    log_enabled = log_root.get('enabled')

    file_sink = log_root.find(".//sink[@type='file']")
    file_output = file_sink.get('output') if file_sink is not None else None

    return log_enabled, file_output


def tail_file(file_path):

    if not os.path.exists(file_path):
        yield f"data: Log does not exist. Retrying...\n\n"
        return

    with open(file_path, "r") as file:
        file.seek(0)  
        lines = file.readlines()
        for line in lines:
            yield f"data: {line}\n\n"

        file.seek(0, 2)  
        while True:
            line = file.readline()
            if not line:
                time.sleep(0.5)  
                continue
            yield f"data: {line}\n\n"
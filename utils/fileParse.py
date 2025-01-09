from xml.etree import ElementTree as ET
import time
import os
from collections import deque

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

    try:
        with open(file_path, "r") as file:
            lines = deque(file, maxlen=50)
            for line in lines:
                yield f"data: {line}\n\n"

            # Move to the end of the file for real-time updates
            file.seek(0, 2)

            # Start streaming new lines as they are added to the file
            while True:
                line = file.readline()
                if line:  # If a line is found, yield it
                    yield f"data: {line}\n\n"
                else:  # If no new line, wait and continue checking
                    time.sleep(0.5)
    except Exception as e:
        # Catch any exceptions (e.g., permission issues) and yield the error message
        yield f"data: Error reading log file: {str(e)}\n\n"
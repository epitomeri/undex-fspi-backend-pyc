def format_xml_string(xml_content):
    """
    A simple string-based formatter for XML content. 
    This is not XML-standard compliant but will make the file more readable.
    """
    indent_level = 0
    formatted_xml = []
    xml_elements = xml_content.replace('><', '>\n<').split('\n')

    for element in xml_elements:
        if element.startswith('</'):
            indent_level -= 1

        formatted_xml.append('    ' * indent_level + element)

        if element.startswith('<') and not element.startswith('</') and not element.endswith('/>'):
            indent_level += 1

    return '\n'.join(formatted_xml)

def format_and_overwrite_xml_file(file_path):
    # Read the content from the file
    with open(file_path, 'r') as file:
        xml_content = file.read()

    # Format the XML content
    formatted_xml = format_xml_string(xml_content)

    # Overwrite the file with the formatted content
    with open(file_path, 'w') as file:
        file.write(formatted_xml)

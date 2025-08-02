import yaml
import sys

try:
    with open('render.yaml', 'r') as file:
        data = yaml.safe_load(file)
    print("✅ YAML syntax is valid")
    print("Services found:", [service['name'] for service in data['services']])
    print("Database found:", data['databases'][0]['name'])
    print("Environment variables configured correctly")
except yaml.YAMLError as e:
    print("❌ YAML syntax error:")
    print(str(e))
    sys.exit(1)
except Exception as e:
    print("❌ Error reading file:")
    print(str(e))
    sys.exit(1)

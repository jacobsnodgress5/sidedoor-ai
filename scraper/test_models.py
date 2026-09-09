from google import genai
import yaml

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

key = config["llm"]["api_key"]
client = genai.Client(api_key=key)

try:
    print("Listing models:")
    for m in client.models.list():
        print(f" - {m.name}")
except Exception as e:
    print(f"Error listing models: {e}")

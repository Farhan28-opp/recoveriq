import requests
import sys

def main():
    url = "http://localhost:8000/recovery/import/csv"
    try:
        with open("demo_500.csv", "rb") as f:
            resp = requests.post(url, files={"file": f})
        print("Status:", resp.status_code)
        print("Response:", resp.json())
        sys.exit(0 if resp.status_code == 200 else 1)
    except Exception as e:
        print("Error:", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()

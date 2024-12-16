import requests
import json

def test_met_api():
    base_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    
    # Test different search terms
    test_terms = [
        "rainbow",
        "rainbows",
        "iridescent",
        "spectrum",
        "color",
        "prismatic"
    ]
    
    for term in test_terms:
        print(f"\nTesting search term: {term}")
        params = {
            'q': term,
            'hasImages': 'true'
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            print(f"Status code: {response.status_code}")
            
            if response.ok:
                data = response.json()
                total = data.get('total', 0)
                ids = data.get('objectIDs', [])
                print(f"Total results: {total}")
                print(f"Number of object IDs: {len(ids) if ids else 0}")
                
                # If we got results, fetch first artwork details
                if ids:
                    obj_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{ids[0]}"
                    obj_response = requests.get(obj_url, timeout=10)
                    if obj_response.ok:
                        obj_data = obj_response.json()
                        print(f"First result: {obj_data.get('title')} ({obj_data.get('objectDate')})")
                        print(f"Medium: {obj_data.get('medium')}")
                        print(f"Department: {obj_data.get('department')}")
            else:
                print(f"Error response: {response.text}")
                
        except Exception as e:
            print(f"Error testing term '{term}': {str(e)}")

if __name__ == "__main__":
    test_met_api()

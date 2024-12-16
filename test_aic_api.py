import requests
import json

def test_aic_api():
    base_url = "https://api.artic.edu/api/v1/artworks/search"
    
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
            'limit': 10,
            'fields': ['id', 'title', 'artist_display', 'date_display', 'medium_display', 
                      'image_id', 'thumbnail', 'department_title', 'dimensions_display']
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            print(f"Status code: {response.status_code}")
            
            if response.ok:
                data = response.json()
                total = data.get('pagination', {}).get('total', 0)
                results = data.get('data', [])
                print(f"Total results: {total}")
                print(f"Number of results in this page: {len(results) if results else 0}")
                
                # Show first result details
                if results:
                    first = results[0]
                    print(f"First result: {first.get('title')} ({first.get('date_display')})")
                    print(f"Artist: {first.get('artist_display')}")
                    print(f"Medium: {first.get('medium_display')}")
                    print(f"Department: {first.get('department_title')}")
                    if first.get('image_id'):
                        print(f"Image available: Yes (ID: {first.get('image_id')})")
                    else:
                        print("Image available: No")
            else:
                print(f"Error response: {response.text}")
                
        except Exception as e:
            print(f"Error testing term '{term}': {str(e)}")

if __name__ == "__main__":
    test_aic_api()

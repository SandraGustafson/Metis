import os
import random
import logging
import re
from typing import List, Dict, Any
import requests
from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Initialize Flask app
# Version 1.0.1 - Clean deployment
app = Flask(__name__)
Bootstrap(app)

# Global cache to track recently shown artworks
recently_shown_artworks = set()
MAX_CACHE_SIZE = 1000  # Maximum number of artwork IDs to remember

def clear_old_cache_entries():
    """Clear old entries from the cache if it gets too large."""
    global recently_shown_artworks
    if len(recently_shown_artworks) > MAX_CACHE_SIZE:
        # Keep only the most recent half of the entries
        recently_shown_artworks = set(list(recently_shown_artworks)[MAX_CACHE_SIZE//2:])

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Search endpoint that combines results from multiple art APIs."""
    try:
        data = request.get_json()
        if not data or 'theme' not in data:
            return jsonify({'error': 'No theme provided'}), 400
            
        theme = data['theme'].strip()
        if not theme:
            return jsonify({'error': 'Theme cannot be empty'}), 400
            
        # Search Met Museum API
        met_results = search_met_artwork(theme)
        
        # Combine and return results
        all_results = met_results
        
        return jsonify({
            'results': all_results,
            'count': len(all_results)
        })
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def expand_search_terms(theme: str) -> List[str]:
    """Expand search terms with relevant art-related keywords."""
    # Dictionary of common art themes and related terms
    theme_expansions = {
        'nature': ['landscape', 'flowers', 'animals', 'birds', 'trees', 'garden'],
        'people': ['portrait', 'figure', 'human', 'face', 'crowd'],
        'culture': ['ceremony', 'ritual', 'tradition', 'festival', 'customs'],
        'religion': ['sacred', 'divine', 'worship', 'deity', 'spiritual'],
        'daily life': ['scene', 'activity', 'domestic', 'everyday'],
        'war': ['battle', 'conflict', 'military', 'warrior', 'combat'],
        'love': ['romance', 'couple', 'embrace', 'affection'],
        'death': ['memorial', 'tomb', 'funeral', 'mourning'],
        'power': ['royal', 'ruler', 'throne', 'crown', 'authority'],
        'work': ['labor', 'craft', 'occupation', 'trade', 'skill'],
        'education': ['learning', 'teaching', 'school', 'study', 'knowledge'],
        'family': ['mother', 'father', 'child', 'parent', 'household'],
        'identity': ['self', 'portrait', 'personal', 'individual'],
        'mythology': ['myth', 'legend', 'god', 'hero', 'folklore'],
        'social justice': ['protest', 'rights', 'equality', 'freedom', 'justice'],
        'gender': ['women', 'men', 'feminine', 'masculine', 'identity'],
        'race': ['ethnic', 'diversity', 'cultural', 'identity', 'heritage'],
    }
    
    # List of art movements and styles
    art_movements = [
        'contemporary', 'modern', 'classical', 'ancient', 'traditional',
        'abstract', 'realistic', 'impressionist', 'expressionist',
        'indigenous', 'folk', 'tribal', 'ceremonial'
    ]
    
    # List of art mediums
    art_mediums = [
        'painting', 'sculpture', 'textile', 'ceramic', 'print',
        'photograph', 'drawing', 'carving', 'weaving', 'pottery'
    ]
    
    search_terms = [theme]  # Start with original theme
    theme_lower = theme.lower()
    
    # Add related theme terms
    for key, values in theme_expansions.items():
        if any(word in theme_lower for word in [key] + values):
            search_terms.extend(values)
            break
    
    # Add relevant art movements based on keywords
    if 'modern' in theme_lower or 'contemporary' in theme_lower:
        search_terms.extend(['modern', 'contemporary', '20th century', '21st century'])
    elif 'ancient' in theme_lower or 'historical' in theme_lower:
        search_terms.extend(['ancient', 'historical', 'classical'])
    elif 'traditional' in theme_lower or 'cultural' in theme_lower:
        search_terms.extend(['traditional', 'indigenous', 'folk'])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_terms = []
    for term in search_terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)
    
    return unique_terms

def is_religious_artwork(obj: Dict[str, Any]) -> bool:
    """Check if artwork is likely religious based on metadata."""
    religious_keywords = {
        'religious', 'sacred', 'divine', 'biblical', 'christian', 'christ',
        'virgin', 'saint', 'madonna', 'jesus', 'angel', 'crucifixion',
        'buddhist', 'hindu', 'islamic', 'deity', 'god', 'goddess', 'temple',
        'church', 'mosque', 'shrine', 'altar', 'prayer', 'worship'
    }
    
    # Check various metadata fields
    text_to_check = ' '.join([
        obj.get('title', '').lower(),
        obj.get('culture', '').lower(),
        obj.get('classification', '').lower(),
        obj.get('department', '').lower(),
        obj.get('period', '').lower(),
        obj.get('objectName', '').lower(),
        obj.get('description', '').lower()
    ])
    
    return any(keyword in text_to_check for keyword in religious_keywords)

def parse_artwork_date(date_str: str) -> int:
    """Extract the latest year from an artwork date string."""
    try:
        # Remove any BCE/CE indicators and clean the string
        date_str = date_str.lower().replace('bce', '').replace('ce', '').replace('c.', '')
        
        # Find all numbers in the string
        years = [int(year) for year in re.findall(r'\d+', date_str)]
        
        if not years:
            return 0
            
        # Return the latest year (usually the end date if a range is given)
        return max(years)
    except Exception:
        return 0

def search_met_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Metropolitan Museum API for artwork matching the theme."""
    global recently_shown_artworks
    base_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    object_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    
    try:
        # Clear old cache entries if needed
        clear_old_cache_entries()
        
        # Expand search terms
        search_terms = expand_search_terms(theme)
        logger.info(f"Expanded search terms: {search_terms}")
        
        modern_ids = set()
        historic_ids = set()
        
        # Search for each term
        for term in search_terms[:3]:  # Limit to first 3 terms to avoid rate limits
            try:
                # First try to get modern works (prioritize these)
                modern_urls = [
                    f"{base_url}?q={term}&hasImages=true&dateBegin=1950&dateEnd=2023",  # Very modern
                    f"{base_url}?q={term}&hasImages=true&dateBegin=1923&dateEnd=1949"   # Early modern
                ]
                
                historic_url = f"{base_url}?q={term}&hasImages=true&dateEnd=1922"
                
                # Try to get very modern works first
                for modern_url in modern_urls:
                    logger.info(f"Searching Met API for modern works: {modern_url}")
                    modern_response = requests.get(modern_url, timeout=10)
                    
                    if modern_response.status_code == 429:
                        logger.error("Met API rate limit exceeded. Please try again later.")
                        break
                        
                    if modern_response.ok:
                        modern_data = modern_response.json()
                        if modern_data.get('objectIDs'):
                            modern_ids.update(
                                id for id in modern_data['objectIDs']
                                if id not in recently_shown_artworks
                            )
                
                # Then get historic works
                logger.info(f"Searching Met API for historic works: {term}")
                historic_response = requests.get(historic_url, timeout=10)
                
                if historic_response.status_code == 429:
                    logger.error("Met API rate limit exceeded. Please try again later.")
                    break
                    
                if historic_response.ok:
                    historic_data = historic_response.json()
                    if historic_data.get('objectIDs'):
                        historic_ids.update(
                            id for id in historic_data['objectIDs']
                            if id not in recently_shown_artworks
                        )
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while searching term: {term}")
                continue
                
        logger.info(f"Found {len(modern_ids)} modern and {len(historic_ids)} historic artworks")
        
        if not modern_ids and not historic_ids:
            logger.warning(f"No results found for any search terms: {search_terms}")
            return []
            
        # Process modern works first
        modern_artworks = []
        historic_artworks = []
        processed_count = 0
        
        # Randomize IDs
        modern_id_list = list(modern_ids)
        historic_id_list = list(historic_ids)
        random.shuffle(modern_id_list)
        random.shuffle(historic_id_list)
        
        # Process modern works first (aiming for at least 10)
        for obj_id in modern_id_list:
            if len(modern_artworks) >= 10:
                break
                
            if processed_count >= 50:  # Limit total processed to avoid excessive API calls
                break
                
            try:
                logger.info(f"Fetching details for modern artwork ID: {obj_id}")
                obj_response = requests.get(f"{object_url}/{obj_id}", timeout=10)
                processed_count += 1
                
                if obj_response.status_code == 429:
                    logger.error("Met API rate limit exceeded while fetching artwork details")
                    break
                    
                if not obj_response.ok:
                    continue
                    
                obj = obj_response.json()
                
                # Skip if no primary image
                primary_image = obj.get('primaryImage')
                if not primary_image or not primary_image.startswith('http'):
                    continue
                
                # Verify it's actually a modern work
                date_str = obj.get('objectDate', '')
                year = parse_artwork_date(date_str)
                if year < 1923:  # Skip if it's not actually modern
                    continue
                
                # Check religious quota
                is_religious = is_religious_artwork(obj)
                if is_religious and sum(1 for a in modern_artworks if a.get('is_religious', False)) >= 1:
                    continue
                
                artwork = create_artwork_dict(obj, is_religious, year)
                modern_artworks.append(artwork)
                recently_shown_artworks.add(obj_id)
                logger.info(f"Added modern artwork: {artwork['title']} ({year})")
                
            except Exception as e:
                logger.error(f"Error processing modern artwork {obj_id}: {str(e)}")
                continue
        
        # Then process historic works to fill remaining slots
        remaining_slots = 20 - len(modern_artworks)
        for obj_id in historic_id_list:
            if len(historic_artworks) >= remaining_slots:
                break
                
            if processed_count >= 100:  # Limit total processed
                break
                
            try:
                logger.info(f"Fetching details for historic artwork ID: {obj_id}")
                obj_response = requests.get(f"{object_url}/{obj_id}", timeout=10)
                processed_count += 1
                
                if obj_response.status_code == 429:
                    logger.error("Met API rate limit exceeded while fetching artwork details")
                    break
                    
                if not obj_response.ok:
                    continue
                    
                obj = obj_response.json()
                
                # Skip if no primary image
                primary_image = obj.get('primaryImage')
                if not primary_image or not primary_image.startswith('http'):
                    continue
                
                # Verify it's a historic work
                date_str = obj.get('objectDate', '')
                year = parse_artwork_date(date_str)
                if year >= 1923:  # Skip if it's actually modern
                    continue
                
                # Check religious quota
                is_religious = is_religious_artwork(obj)
                if is_religious and sum(1 for a in historic_artworks if a.get('is_religious', False)) >= 1:
                    continue
                
                artwork = create_artwork_dict(obj, is_religious, year)
                historic_artworks.append(artwork)
                recently_shown_artworks.add(obj_id)
                logger.info(f"Added historic artwork: {artwork['title']} ({year})")
                
            except Exception as e:
                logger.error(f"Error processing historic artwork {obj_id}: {str(e)}")
                continue
        
        # Combine results
        results = modern_artworks + historic_artworks
        random.shuffle(results)
        
        logger.info(f"Returning {len(results)} total results ({len(modern_artworks)} modern, "
                   f"{len(historic_artworks)} historic)")
        return results
        
    except Exception as e:
        logger.error(f"Error in Met API search: {str(e)}")
        return []

def create_artwork_dict(obj: Dict[str, Any], is_religious: bool, year: int) -> Dict[str, Any]:
    """Create a standardized artwork dictionary from Met API data."""
    artist = obj.get('artistDisplayName', 'Unknown')
    culture = obj.get('culture', 'Unknown')
    period = obj.get('period', 'Unknown')
    
    return {
        'title': obj.get('title', 'Untitled'),
        'artist': artist if artist != 'Unknown' else None,
        'date': obj.get('objectDate', ''),
        'year': year,
        'medium': obj.get('medium', ''),
        'culture': culture if culture != 'Unknown' else None,
        'period': period if period != 'Unknown' else None,
        'image_url': obj.get('primaryImage', ''),
        'source': 'The Metropolitan Museum of Art',
        'source_url': obj.get('objectURL', ''),
        'description': obj.get('description', ''),
        'department': obj.get('department', ''),
        'tags': ', '.join(filter(None, [
            culture if culture != 'Unknown' else None,
            period if period != 'Unknown' else None,
            obj.get('classification') if obj.get('classification') != 'Unknown' else None,
            obj.get('department') if obj.get('department') != 'Unknown' else None
        ])),
        'is_religious': is_religious
    }

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

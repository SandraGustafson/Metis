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
    base_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    object_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    
    try:
        # Expand search terms
        search_terms = expand_search_terms(theme)
        logger.info(f"Expanded search terms: {search_terms}")
        
        all_object_ids = set()  # Use set to avoid duplicates
        
        # Search for each term
        for term in search_terms[:3]:  # Limit to first 3 terms to avoid rate limits
            try:
                # Add date filters to encourage modern works
                modern_search_url = f"{base_url}?q={term}&hasImages=true&dateBegin=1923&dateEnd=2023"
                historic_search_url = f"{base_url}?q={term}&hasImages=true&dateEnd=1922"
                
                logger.info(f"Searching Met API for modern works: {term}")
                modern_response = requests.get(modern_search_url, timeout=10)
                
                logger.info(f"Searching Met API for historic works: {term}")
                historic_response = requests.get(historic_search_url, timeout=10)
                
                if modern_response.status_code == 429 or historic_response.status_code == 429:
                    logger.error("Met API rate limit exceeded. Please try again later.")
                    break
                    
                modern_data = modern_response.json() if modern_response.ok else {'objectIDs': []}
                historic_data = historic_response.json() if historic_response.ok else {'objectIDs': []}
                
                if modern_data.get('objectIDs'):
                    all_object_ids.update(modern_data['objectIDs'])
                if historic_data.get('objectIDs'):
                    all_object_ids.update(historic_data['objectIDs'])
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while searching term: {term}")
                continue
                
        if not all_object_ids:
            logger.warning(f"No results found for any search terms: {search_terms}")
            return []
            
        # Convert set to list and process
        object_ids = list(all_object_ids)
        logger.info(f"Found {len(object_ids)} total unique artworks across all terms")
        
        # Get artwork details and separate by period
        modern_artworks = []
        historic_artworks = []
        processed_count = 0
        
        random.shuffle(object_ids)
        
        for obj_id in object_ids:
            if len(modern_artworks) + len(historic_artworks) >= 20:  # Stop after getting 20 valid results
                break
                
            if processed_count >= 100:  # Limit total processed to avoid excessive API calls
                break
                
            try:
                logger.info(f"Fetching details for artwork ID: {obj_id}")
                obj_response = requests.get(f"{object_url}/{obj_id}", timeout=10)
                processed_count += 1
                
                if obj_response.status_code == 429:  # Rate limit exceeded
                    logger.error("Met API rate limit exceeded while fetching artwork details")
                    break
                    
                if not obj_response.ok:
                    logger.warning(f"Failed to fetch artwork {obj_id}: {obj_response.status_code}")
                    continue
                    
                obj = obj_response.json()
                
                # Skip if no primary image
                primary_image = obj.get('primaryImage')
                if not primary_image or not primary_image.startswith('http'):
                    logger.debug(f"Skipping artwork {obj_id}: No valid primary image")
                    continue
                
                # Check if artwork is religious
                is_religious = is_religious_artwork(obj)
                if is_religious and sum(1 for a in modern_artworks + historic_artworks if a.get('is_religious', False)) >= 2:
                    logger.debug(f"Skipping religious artwork {obj_id}: quota reached")
                    continue
                
                # Get basic metadata
                artist = obj.get('artistDisplayName', 'Unknown')
                culture = obj.get('culture', 'Unknown')
                period = obj.get('period', 'Unknown')
                date_str = obj.get('objectDate', '')
                year = parse_artwork_date(date_str)
                
                artwork = {
                    'title': obj.get('title', 'Untitled'),
                    'artist': artist if artist != 'Unknown' else None,
                    'date': date_str,
                    'year': year,
                    'medium': obj.get('medium', ''),
                    'culture': culture if culture != 'Unknown' else None,
                    'period': period if period != 'Unknown' else None,
                    'image_url': primary_image,
                    'source': 'The Metropolitan Museum of Art',
                    'source_url': obj.get('objectURL', ''),
                    'description': obj.get('description', ''),
                    'tags': ', '.join(filter(None, [
                        culture if culture != 'Unknown' else None,
                        period if period != 'Unknown' else None,
                        obj.get('classification') if obj.get('classification') != 'Unknown' else None
                    ])),
                    'is_religious': is_religious
                }
                
                # Sort into modern or historic based on year
                if year >= 1923:  # Last 100 years
                    if len(modern_artworks) < 10:  # Ensure we don't exceed our quota
                        modern_artworks.append(artwork)
                        logger.info(f"Added modern artwork: {artwork['title']} ({year})")
                else:
                    if len(historic_artworks) < 10:  # Ensure we don't exceed our quota
                        historic_artworks.append(artwork)
                        logger.info(f"Added historic artwork: {artwork['title']} ({year})")
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while fetching artwork {obj_id}")
                continue
            except Exception as e:
                logger.error(f"Error processing Met object {obj_id}: {str(e)}")
                continue
                
        # Combine results, ensuring balanced representation
        results = []
        modern_count = len(modern_artworks)
        historic_count = len(historic_artworks)
        
        logger.info(f"Found {modern_count} modern and {historic_count} historic artworks")
        
        # Add all modern works
        results.extend(modern_artworks)
        
        # Add historic works to fill the remainder
        results.extend(historic_artworks[:20-len(results)])
        
        # If we don't have enough modern works, add more historic ones
        if len(results) < 20 and historic_count > len(historic_artworks[:20-len(modern_artworks)]):
            additional_historic = historic_artworks[20-len(modern_artworks):20]
            results.extend(additional_historic)
        
        random.shuffle(results)  # Randomize final order
        
        logger.info(f"Returning {len(results)} total results ({sum(1 for a in results if a['year'] >= 1923)} modern, "
                   f"{sum(1 for a in results if a['year'] < 1923)} historic)")
        return results
        
    except requests.exceptions.Timeout:
        logger.error("Timeout while searching Met API")
        return []
    except Exception as e:
        logger.error(f"Error in Met API search: {str(e)}")
        return []

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

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
    """Handle artwork search requests."""
    try:
        data = request.get_json()
        theme = data.get('theme', '').strip()
        
        if not theme:
            return jsonify({'error': 'No search theme provided'}), 400
            
        logger.info(f"Received search request for theme: {theme}")
        
        # Test direct API call first
        test_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
        test_params = {
            'q': theme,
            'hasImages': 'true'
        }
        logger.info(f"Testing direct API call with URL: {test_url} and params: {test_params}")
        
        test_response = requests.get(test_url, params=test_params, timeout=10)
        logger.info(f"Direct API test response status: {test_response.status_code}")
        if test_response.ok:
            logger.info(f"Direct API test response: {test_response.text[:500]}")
        
        # Proceed with normal search
        results = search_met_artwork(theme)
        
        if not results:
            return jsonify({
                'error': f'No artwork found for "{theme}". Try a different search term or check your spelling.'
            }), 404
            
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def expand_search_terms(theme: str) -> List[str]:
    """Expand search terms to include related concepts."""
    theme = theme.lower().strip()
    
    # Log original theme
    logger.info(f"Original search theme: {theme}")
    
    # Basic term mapping
    term_mapping = {
        'rainbow': ['rainbow', 'rainbows', 'spectrum', 'iridescent', 'prismatic'],
        'rainbows': ['rainbow', 'rainbows', 'spectrum', 'iridescent', 'prismatic'],
        'nature': ['nature', 'landscape', 'natural', 'organic', 'flora', 'fauna'],
        'identity': ['identity', 'portrait', 'self-portrait', 'figure', 'personal'],
        'social': ['social', 'society', 'community', 'people', 'gathering'],
        'justice': ['justice', 'equality', 'rights', 'freedom', 'liberty'],
        'power': ['power', 'authority', 'strength', 'force', 'might'],
    }
    
    # Get base terms
    terms = set([theme])  # Start with original term
    
    # Add mapped terms if they exist
    if theme in term_mapping:
        terms.update(term_mapping[theme])
    
    # Add any word-by-word mappings
    for word in theme.split():
        if word in term_mapping:
            terms.update(term_mapping[word])
    
    # Log expanded terms
    logger.info(f"Expanded search terms: {terms}")
    
    return list(terms)

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
        
        all_ids = set()
        
        # First do a basic search to get all matching artworks
        for term in search_terms[:3]:  # Limit to first 3 terms to avoid rate limits
            try:
                params = {
                    'q': term,
                    'hasImages': 'true'
                }
                
                logger.info(f"Making API request to {base_url} with params: {params}")
                response = requests.get(base_url, params=params, timeout=10)
                
                if response.ok:
                    data = response.json()
                    total = data.get('total', 0)
                    logger.info(f"Total results for term '{term}': {total}")
                    
                    if data.get('objectIDs'):
                        # Add all IDs that haven't been shown recently
                        new_ids = set(id for id in data['objectIDs'] if id not in recently_shown_artworks)
                        all_ids.update(new_ids)
                        logger.info(f"Found {len(new_ids)} new artworks for term '{term}'")
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while searching term: {term}")
                continue
            except Exception as e:
                logger.error(f"Error searching term '{term}': {str(e)}")
                continue
        
        logger.info(f"Total unique artworks found: {len(all_ids)}")
        
        if not all_ids:
            return []
            
        # Convert to list and shuffle
        all_ids = list(all_ids)
        random.shuffle(all_ids)
        
        # Get details for up to 10 artworks
        results = []
        religious_count = 0
        modern_count = 0
        
        for artwork_id in all_ids[:30]:  # Try up to 30 artworks to find 10 good ones
            if len(results) >= 10:
                break
                
            try:
                artwork_url = f"{object_url}/{artwork_id}"
                response = requests.get(artwork_url, timeout=10)
                
                if response.ok:
                    artwork = response.json()
                    
                    # Skip if no image
                    if not artwork.get('primaryImage'):
                        continue
                        
                    # Get year and check if it's modern (post 1923)
                    year = parse_artwork_date(artwork.get('objectDate', ''))
                    is_modern = year >= 1923 if year else False
                    
                    # Skip if we already have enough modern or historic works
                    if is_modern and modern_count >= 5:
                        continue
                    if not is_modern and len(results) - modern_count >= 5:
                        continue
                        
                    # Check for religious content (basic check)
                    religious_terms = {'religious', 'sacred', 'holy', 'divine', 'biblical', 'christian', 'islamic', 'buddhist', 'hindu'}
                    is_religious = any(term.lower() in artwork.get('title', '').lower() or 
                                     term.lower() in artwork.get('culture', '').lower() or
                                     term.lower() in artwork.get('classification', '').lower() 
                                     for term in religious_terms)
                    
                    if is_religious and religious_count >= 2:
                        continue
                        
                    # Add artwork to results
                    results.append({
                        'id': artwork_id,
                        'title': artwork.get('title', 'Untitled'),
                        'artist': artwork.get('artistDisplayName', 'Unknown Artist'),
                        'date': artwork.get('objectDate', 'Date unknown'),
                        'medium': artwork.get('medium', 'Medium unknown'),
                        'culture': artwork.get('culture', 'Culture unknown'),
                        'image_url': artwork.get('primaryImage'),
                        'object_url': artwork.get('objectURL'),
                        'department': artwork.get('department', 'Department unknown'),
                        'dimensions': artwork.get('dimensions', 'Dimensions unknown'),
                        'credit': artwork.get('creditLine', 'Credit unknown')
                    })
                    
                    # Update counters
                    if is_modern:
                        modern_count += 1
                    if is_religious:
                        religious_count += 1
                    
                    # Add to recently shown
                    recently_shown_artworks.add(artwork_id)
                    
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error fetching artwork {artwork_id}: {str(e)}")
                continue
        
        return results
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
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

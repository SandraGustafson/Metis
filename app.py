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

# Constants for APIs
MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
AIC_API_BASE = "https://api.artic.edu/api/v1"
AIC_IMAGE_BASE = "https://www.artic.edu/iiif/2"

# Global cache to track recently shown artworks
recently_shown_artworks = set()
MAX_CACHE_SIZE = 1000  # Maximum number of artwork IDs to remember

def clear_old_cache_entries():
    """Clear old entries from the cache if it gets too large."""
    global recently_shown_artworks
    if len(recently_shown_artworks) > MAX_CACHE_SIZE:
        # Keep only the most recent half of the entries
        recently_shown_artworks = set(list(recently_shown_artworks)[MAX_CACHE_SIZE//2:])

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

def search_aic_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Art Institute of Chicago API for artwork matching the theme."""
    try:
        # Use the public search endpoint
        search_url = f"{AIC_API_BASE}/artworks/search"
        params = {
            'q': theme,
            'limit': 30,  # Get more results to allow for filtering
            'fields': [
                'id', 'title', 'artist_display', 'date_display', 'medium_display',
                'image_id', 'thumbnail', 'department_title', 'dimensions_display',
                'credit_line', 'date_start', 'artist_title', 'place_of_origin',
                'classification_title'
            ]
        }
        
        logger.info(f"Searching AIC with term: {theme}")
        response = requests.get(search_url, params=params, timeout=10)
        
        if not response.ok:
            logger.error(f"AIC API error: {response.status_code} - {response.text}")
            return []
            
        data = response.json()
        results = data.get('data', [])
        
        if not results:
            return []
            
        artworks = []
        for artwork in results:
            # Skip if no image
            if not artwork.get('image_id'):
                continue
                
            # Get year
            year = artwork.get('date_start')
            is_modern = year >= 1923 if year else False
            
            # Check for religious content
            religious_terms = {'religious', 'sacred', 'holy', 'divine', 'biblical', 'christian', 'islamic', 'buddhist', 'hindu'}
            is_religious = any(term.lower() in str(artwork.get('title', '')).lower() or
                             term.lower() in str(artwork.get('classification_title', '')).lower()
                             for term in religious_terms)
            
            # Create image URL using IIIF
            image_url = f"{AIC_IMAGE_BASE}/{artwork['image_id']}/full/843,/0/default.jpg"
            
            artworks.append({
                'id': f"AIC_{artwork['id']}",
                'title': artwork.get('title', 'Untitled'),
                'artist': artwork.get('artist_display', 'Unknown Artist'),
                'date': artwork.get('date_display', 'Date unknown'),
                'medium': artwork.get('medium_display', 'Medium unknown'),
                'culture': artwork.get('place_of_origin', 'Culture unknown'),
                'image_url': image_url,
                'object_url': f"https://www.artic.edu/artworks/{artwork['id']}",
                'department': artwork.get('department_title', 'Department unknown'),
                'dimensions': artwork.get('dimensions_display', 'Dimensions unknown'),
                'credit': artwork.get('credit_line', 'Credit unknown'),
                'museum': 'Art Institute of Chicago',
                'is_modern': is_modern,
                'is_religious': is_religious,
                'year': year
            })
        
        return artworks
        
    except Exception as e:
        logger.error(f"Error in AIC search: {str(e)}")
        return []

def search_met_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Metropolitan Museum API for artwork matching the theme."""
    try:
        search_url = f"{MET_API_BASE}/search"
        params = {
            'q': theme,
            'hasImages': 'true'
        }
        
        logger.info(f"Searching Met with term: {theme}")
        response = requests.get(search_url, params=params, timeout=10)
        
        if not response.ok:
            logger.error(f"Met API error: {response.status_code} - {response.text}")
            return []
            
        data = response.json()
        object_ids = data.get('objectIDs', [])
        
        if not object_ids:
            return []
            
        # Shuffle and take first 30
        random.shuffle(object_ids)
        object_ids = object_ids[:30]
        
        artworks = []
        for obj_id in object_ids:
            try:
                obj_url = f"{MET_API_BASE}/objects/{obj_id}"
                obj_response = requests.get(obj_url, timeout=10)
                
                if not obj_response.ok:
                    continue
                    
                artwork = obj_response.json()
                
                # Skip if no image
                if not artwork.get('primaryImage'):
                    continue
                    
                # Get year
                year = parse_artwork_date(artwork.get('objectDate', ''))
                is_modern = year >= 1923 if year else False
                
                # Check for religious content
                religious_terms = {'religious', 'sacred', 'holy', 'divine', 'biblical', 'christian', 'islamic', 'buddhist', 'hindu'}
                is_religious = any(term.lower() in str(artwork.get('title', '')).lower() or
                                 term.lower() in str(artwork.get('classification', '')).lower()
                                 for term in religious_terms)
                
                artworks.append({
                    'id': f"MET_{obj_id}",
                    'title': artwork.get('title', 'Untitled'),
                    'artist': artwork.get('artistDisplayName', 'Unknown Artist'),
                    'date': artwork.get('objectDate', 'Date unknown'),
                    'medium': artwork.get('medium', 'Medium unknown'),
                    'culture': artwork.get('culture', 'Culture unknown'),
                    'image_url': artwork.get('primaryImage'),
                    'object_url': artwork.get('objectURL'),
                    'department': artwork.get('department', 'Department unknown'),
                    'dimensions': artwork.get('dimensions', 'Dimensions unknown'),
                    'credit': artwork.get('creditLine', 'Credit unknown'),
                    'museum': 'The Metropolitan Museum of Art',
                    'is_modern': is_modern,
                    'is_religious': is_religious,
                    'year': year
                })
                
            except Exception as e:
                logger.error(f"Error fetching Met artwork {obj_id}: {str(e)}")
                continue
        
        return artworks
        
    except Exception as e:
        logger.error(f"Error in Met search: {str(e)}")
        return []

def combine_and_filter_results(met_results: List[Dict[str, Any]], 
                             aic_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine and filter results from both museums."""
    # Combine all results
    all_results = met_results + aic_results
    
    if not all_results:
        return []
        
    # Shuffle results
    random.shuffle(all_results)
    
    # Filter and balance results
    final_results = []
    modern_count = 0
    historic_count = 0
    religious_count = 0
    met_count = 0
    aic_count = 0
    
    for artwork in all_results:
        if len(final_results) >= 20:  # Return up to 20 total results
            break
            
        # Check museum quotas (max 10 from each)
        if artwork['museum'] == 'The Metropolitan Museum of Art':
            if met_count >= 10:
                continue
        else:
            if aic_count >= 10:
                continue
        
        # Check modern/historic balance
        if artwork['is_modern']:
            if modern_count >= 10:
                continue
        else:
            if historic_count >= 10:
                continue
                
        # Check religious quota
        if artwork['is_religious'] and religious_count >= 2:
            continue
            
        # Add artwork
        final_results.append(artwork)
        
        # Update counters
        if artwork['is_modern']:
            modern_count += 1
        else:
            historic_count += 1
            
        if artwork['is_religious']:
            religious_count += 1
            
        if artwork['museum'] == 'The Metropolitan Museum of Art':
            met_count += 1
        else:
            aic_count += 1
    
    return final_results

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
        
        # Search both museums in parallel
        met_results = search_met_artwork(theme)
        aic_results = search_aic_artwork(theme)
        
        # Combine all results
        all_results = met_results + aic_results
        
        if not all_results:
            return jsonify({
                'error': f'No artwork found for "{theme}". Try a different search term or check your spelling.'
            }), 404
            
        # Shuffle results
        random.shuffle(all_results)
        
        # Filter and balance results
        final_results = []
        modern_count = 0
        historic_count = 0
        religious_count = 0
        met_count = 0
        aic_count = 0
        
        for artwork in all_results:
            if len(final_results) >= 20:  # Return up to 20 total results
                break
                
            # Check museum quotas (max 10 from each)
            if artwork['museum'] == 'The Metropolitan Museum of Art':
                if met_count >= 10:
                    continue
            else:
                if aic_count >= 10:
                    continue
            
            # Check modern/historic balance
            if artwork.get('is_modern'):
                if modern_count >= 10:
                    continue
            else:
                if historic_count >= 10:
                    continue
                    
            # Check religious quota
            if artwork.get('is_religious') and religious_count >= 2:
                continue
                
            # Add artwork
            final_results.append(artwork)
            
            # Update counters
            if artwork.get('is_modern'):
                modern_count += 1
            else:
                historic_count += 1
                
            if artwork.get('is_religious'):
                religious_count += 1
                
            if artwork['museum'] == 'The Metropolitan Museum of Art':
                met_count += 1
            else:
                aic_count += 1
        
        # Log result statistics
        logger.info(f"Found {len(final_results)} total results:")
        logger.info(f"- Met: {met_count}, AIC: {aic_count}")
        logger.info(f"- Modern: {modern_count}, Historic: {len(final_results) - modern_count}")
        logger.info(f"- Religious: {religious_count}")
        
        return jsonify({'results': final_results})
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

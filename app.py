import os
import random
import logging
import re
from typing import List, Dict, Any, Optional
import requests
from flask import Flask, render_template, request, jsonify, make_response
from flask_bootstrap import Bootstrap
from dotenv import load_dotenv
import time
import urllib.parse

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

# Met Museum Department IDs and Names
MET_DEPARTMENTS = {
    1: "The American Wing",
    3: "Ancient Near Eastern Art",
    4: "Arms and Armor",
    5: "Arts of Africa, Oceania, and the Americas",
    6: "Asian Art",
    7: "The Cloisters",
    8: "The Costume Institute",
    9: "Drawings and Prints",
    10: "Egyptian Art",
    11: "European Paintings",
    12: "European Sculpture and Decorative Arts",
    13: "Greek and Roman Art",
    14: "Islamic Art",
    15: "The Robert Lehman Collection",
    16: "The Libraries",
    17: "Medieval Art",
    18: "Musical Instruments",
    19: "Photographs",
    21: "Modern and Contemporary Art"
}

# Global cache with timestamp
class ArtworkCache:
    def __init__(self):
        self.cache = {}
        self.max_size = 1000
        self.expiry_time = 3600  # 1 hour in seconds

    def add(self, artwork_id: str):
        current_time = time.time()
        self.cache[artwork_id] = current_time
        self._cleanup()

    def contains(self, artwork_id: str) -> bool:
        if artwork_id not in self.cache:
            return False
        # Remove if expired
        if time.time() - self.cache[artwork_id] > self.expiry_time:
            del self.cache[artwork_id]
            return False
        return True

    def _cleanup(self):
        current_time = time.time()
        # Remove expired entries
        self.cache = {k: v for k, v in self.cache.items() 
                     if current_time - v <= self.expiry_time}
        # If still too large, remove oldest entries
        if len(self.cache) > self.max_size:
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1])
            self.cache = dict(sorted_items[len(sorted_items)//2:])

artwork_cache = ArtworkCache()

def is_contemporary(artwork: Dict[str, Any]) -> bool:
    """Determine if an artwork is contemporary based on various criteria."""
    # Check date
    year = artwork.get('year')
    if isinstance(year, int) and year >= 1950:
        return True
    
    # Check style/movement indicators
    contemporary_terms = {
        'contemporary', 'modern', 'abstract', 'digital', 'installation',
        'mixed media', 'conceptual', 'post-modern', 'experimental',
        'performance', 'video', 'new media', 'pop art', 'minimal',
        'photography', 'assemblage', 'environmental', 'site-specific'
    }
    
    text_to_check = ' '.join([
        str(artwork.get('title', '')).lower(),
        str(artwork.get('style', '')).lower(),
        str(artwork.get('classification', '')).lower(),
        str(artwork.get('department', '')).lower(),
        str(artwork.get('medium', '')).lower(),
        str(artwork.get('artwork_type', '')).lower(),
        ', '.join(str(x).lower() for x in artwork.get('categories', [])),
        ', '.join(str(x).lower() for x in artwork.get('terms', []))
    ])
    
    return any(term in text_to_check for term in contemporary_terms)

def expand_search_terms(theme: str) -> List[str]:
    """Expand search terms to include semantic relationships and thematic concepts."""
    # Base theme
    terms = [theme.lower()]
    
    # Common emotional and thematic mappings
    theme_mappings = {
        'hope': [
            'sunrise', 'light', 'spring', 'rainbow', 'dove', 'flower', 'bloom', 
            'bright', 'upward', 'rising', 'joy', 'smile', 'peace', 'optimism'
        ],
        'joy': [
            'celebration', 'dance', 'smile', 'sun', 'play', 'festival', 
            'music', 'bright', 'happy', 'garden', 'children', 'flowers'
        ],
        'peace': [
            'dove', 'olive', 'calm', 'serene', 'quiet', 'meditation', 
            'harmony', 'balance', 'nature', 'water', 'garden'
        ],
        'love': [
            'heart', 'couple', 'embrace', 'kiss', 'romance', 'family',
            'mother', 'child', 'tenderness', 'affection', 'devotion'
        ],
        'power': [
            'throne', 'crown', 'warrior', 'lion', 'eagle', 'sword',
            'victory', 'strength', 'mighty', 'royal', 'emperor'
        ],
        'nature': [
            'landscape', 'garden', 'forest', 'mountain', 'river', 'sea',
            'tree', 'flower', 'animal', 'bird', 'seasons'
        ],
        'freedom': [
            'bird', 'sky', 'wing', 'flight', 'break', 'chain', 'liberty',
            'release', 'escape', 'open', 'horizon', 'eagle'
        ],
        'wisdom': [
            'book', 'scroll', 'owl', 'sage', 'teacher', 'study',
            'contemplation', 'meditation', 'knowledge', 'learning'
        ],
        'faith': [
            'prayer', 'worship', 'divine', 'sacred', 'spiritual', 'devotion',
            'belief', 'ritual', 'sanctuary', 'holy'
        ],
        'time': [
            'clock', 'hourglass', 'season', 'cycle', 'age', 'eternal',
            'moment', 'passing', 'memory', 'history'
        ],
        'identity': [
            'portrait', 'mirror', 'mask', 'self', 'reflection', 'persona',
            'character', 'individual', 'culture', 'heritage'
        ]
    }
    
    # Add direct theme mappings if available
    if theme.lower() in theme_mappings:
        terms.extend(theme_mappings[theme.lower()])
    
    # Add compound themes (e.g., "peaceful garden" -> check both "peace" and "nature")
    words = theme.lower().split()
    for word in words:
        if word in theme_mappings:
            terms.extend(theme_mappings[word])
    
    return list(set(terms))  # Remove duplicates

def calculate_relevance_score(artwork: Dict[str, Any], search_terms: List[str]) -> float:
    """Calculate artwork relevance based on multiple factors."""
    score = 0.0
    
    # Convert all text fields to lowercase for case-insensitive matching
    title = str(artwork.get('title', '')).lower()
    description = str(artwork.get('description', '')).lower()
    medium = str(artwork.get('medium', '')).lower()
    classification = str(artwork.get('classification', '')).lower()
    culture = str(artwork.get('culture', '')).lower()
    tags = [str(tag).lower() for tag in artwork.get('tags', [])]
    
    # Combine all text fields for content matching
    all_text = ' '.join([title, description, medium, classification, culture] + tags)
    
    for term in search_terms:
        # Title matches get highest weight
        if term in title:
            score += 3.0
        
        # Direct content matches
        if term in all_text:
            score += 1.0
        
        # Partial word matches (e.g., "hope" in "hopeful")
        if any(term in word for word in all_text.split()):
            score += 0.5
    
    # Boost score for certain criteria
    if artwork.get('primaryImage'):  # Has image
        score *= 1.2
    
    if artwork.get('artistDisplayName'):  # Has known artist
        score *= 1.1
    
    return score

def search_met_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Metropolitan Museum API with semantic understanding."""
    try:
        search_terms = expand_search_terms(theme)
        all_artworks = []
        seen_artworks = set()
        
        logger.info(f"Expanded search terms: {search_terms}")
        
        # Search with each term
        for term in search_terms[:5]:  # Limit to top 5 terms for performance
            search_url = f"{MET_API_BASE}/search"
            params = {
                'q': term,
                'hasImages': True
            }
            
            logger.info(f"Searching Met with term: {term}")
            response = requests.get(search_url, params=params, timeout=10)
            
            if not response.ok:
                continue
                
            data = response.json()
            object_ids = data.get('objectIDs', [])
            
            if not object_ids:
                continue
            
            # Shuffle to get different results each time
            random.shuffle(object_ids)
            
            # Process a subset of results for each term
            for obj_id in object_ids[:20]:
                if obj_id in seen_artworks:
                    continue
                    
                artwork_dict = fetch_met_artwork(obj_id)
                if artwork_dict:
                    # Calculate relevance score
                    relevance_score = calculate_relevance_score(artwork_dict, search_terms)
                    artwork_dict['relevance_score'] = relevance_score
                    
                    if relevance_score > 0.5:  # Only include if somewhat relevant
                        all_artworks.append(artwork_dict)
                        seen_artworks.add(obj_id)
        
        # Sort by relevance score
        all_artworks.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return all_artworks
        
    except Exception as e:
        logger.error(f"Error in Met search: {str(e)}")
        return []

def search_aic_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Art Institute of Chicago API with semantic understanding."""
    try:
        search_terms = expand_search_terms(theme)
        all_artworks = []
        seen_artworks = set()
        
        # Build query with semantic terms
        for term in search_terms[:5]:
            search_url = f"{AIC_API_BASE}/artworks/search"
            params = {
                'q': term,
                'fields': [
                    'id', 'title', 'artist_display', 'date_display', 'medium_display',
                    'image_id', 'thumbnail', 'department_title', 'artwork_type_title',
                    'classification_title', 'subject_titles', 'theme_titles',
                    'material_titles', 'term_titles', 'style_title'
                ],
                'limit': 30
            }
            
            logger.info(f"Searching AIC with term: {term}")
            response = requests.get(search_url, params=params, timeout=10)
            
            if not response.ok:
                continue
                
            data = response.json()
            results = data.get('data', [])
            
            for artwork in results:
                if not artwork.get('image_id'):
                    continue
                    
                artwork_id = f"AIC_{artwork['id']}"
                if artwork_id in seen_artworks:
                    continue
                    
                artwork_dict = {
                    'id': artwork_id,
                    'title': artwork.get('title', 'Untitled'),
                    'artist': artwork.get('artist_display', 'Unknown Artist'),
                    'date': artwork.get('date_display', 'Date unknown'),
                    'medium': artwork.get('medium_display', 'Medium unknown'),
                    'image_url': f"{AIC_IMAGE_BASE}/{artwork['image_id']}/full/843,/0/default.jpg",
                    'object_url': f"https://www.artic.edu/artworks/{artwork['id']}",
                    'museum': 'Art Institute of Chicago',
                    'department': artwork.get('department_title', ''),
                    'classification': artwork.get('classification_title', ''),
                    'subjects': artwork.get('subject_titles', []),
                    'themes': artwork.get('theme_titles', []),
                    'materials': artwork.get('material_titles', []),
                    'style': artwork.get('style_title', ''),
                    'artwork_type': artwork.get('artwork_type_title', '')
                }
                
                # Calculate relevance score
                relevance_score = calculate_relevance_score(artwork_dict, search_terms)
                artwork_dict['relevance_score'] = relevance_score
                
                if relevance_score > 0.5:  # Only include if somewhat relevant
                    all_artworks.append(artwork_dict)
                    seen_artworks.add(artwork_id)
        
        # Sort by relevance score
        all_artworks.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return all_artworks
        
    except Exception as e:
        logger.error(f"Error in AIC search: {str(e)}")
        return []

def combine_and_filter_results(met_results: List[Dict[str, Any]], 
                             aic_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Combine and filter results from both museums."""
    # Combine all results
    all_results = met_results + aic_results
    
    if not all_results:
        return []
    
    # Sort by relevance score
    all_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    # Take top 40 most relevant results
    top_results = all_results[:40]
    
    # Shuffle within relevance bands to increase diversity
    # Group by relevance score rounded to nearest 0.5
    relevance_bands = {}
    for artwork in top_results:
        score = round(artwork.get('relevance_score', 0) * 2) / 2  # Round to nearest 0.5
        if score not in relevance_bands:
            relevance_bands[score] = []
        relevance_bands[score].append(artwork)
    
    # Shuffle within each band
    for band in relevance_bands.values():
        random.shuffle(band)
    
    # Reconstruct results list
    final_results = []
    met_count = 0
    aic_count = 0
    
    # Process each relevance band, starting from highest
    for score in sorted(relevance_bands.keys(), reverse=True):
        band = relevance_bands[score]
        for artwork in band:
            if len(final_results) >= 20:
                break
                
            if artwork['museum'] == 'The Metropolitan Museum of Art':
                if met_count >= 10:
                    continue
                met_count += 1
            else:
                if aic_count >= 10:
                    continue
                aic_count += 1
                
            final_results.append(artwork)
    
    return final_results

def fetch_met_artwork(obj_id: int) -> Optional[Dict[str, Any]]:
    """Fetch and process a single artwork from the Met API."""
    try:
        obj_url = f"{MET_API_BASE}/objects/{obj_id}"
        obj_response = requests.get(obj_url, timeout=10)
        
        if not obj_response.ok:
            return None
            
        artwork = obj_response.json()
        
        # Skip if no image
        if not artwork.get('primaryImage'):
            return None
            
        # Skip if in cache
        artwork_id = f"MET_{obj_id}"
        if artwork_cache.contains(artwork_id):
            return None
            
        # Get department name
        dept_id = artwork.get('department')
        department = MET_DEPARTMENTS.get(dept_id, 'Unknown Department')
        
        # Extract year for sorting
        year = None
        date = artwork.get('objectDate', '')
        try:
            year_match = re.search(r'(\d{4})', date)
            if year_match:
                year = int(year_match.group(1))
        except:
            year = None
            
        artwork_dict = {
            'id': artwork_id,
            'title': artwork.get('title', 'Untitled'),
            'artist': artwork.get('artistDisplayName', 'Unknown Artist'),
            'date': artwork.get('objectDate', 'Date unknown'),
            'year': year,
            'medium': artwork.get('medium', 'Medium unknown'),
            'image_url': artwork['primaryImage'],
            'object_url': artwork.get('objectURL', ''),
            'museum': 'The Metropolitan Museum of Art',
            'department': department,
            'culture': artwork.get('culture', ''),
            'period': artwork.get('period', ''),
            'dynasty': artwork.get('dynasty', ''),
            'reign': artwork.get('reign', ''),
            'classification': artwork.get('classification', ''),
            'geographic_location': artwork.get('geographyType', '')
        }
        
        artwork_cache.add(artwork_id)
        return artwork_dict
        
    except Exception as e:
        logger.error(f"Error fetching Met artwork {obj_id}: {str(e)}")
        return None

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
    """Handle artwork search requests."""
    theme = request.args.get('theme', '').strip()
    logger.debug(f"Received search theme: {theme}")
    
    if not theme:
        logger.warning("No search theme provided")
        return jsonify({'error': 'No search theme provided'}), 400
    
    try:
        # Encode theme for URL safety
        encoded_theme = urllib.parse.quote(theme)
        logger.info(f"Encoded search theme: {encoded_theme}")
        
        # Search both APIs with explicit error handling
        met_results = []
        aic_results = []
        
        try:
            met_results = search_met_artwork(encoded_theme)
            logger.info(f"Met results count: {len(met_results)}")
        except Exception as met_error:
            logger.error(f"Met API search error: {met_error}", exc_info=True)
        
        try:
            aic_results = search_aic_artwork(encoded_theme)
            logger.info(f"AIC results count: {len(aic_results)}")
        except Exception as aic_error:
            logger.error(f"AIC API search error: {aic_error}", exc_info=True)
        
        # Combine and filter results
        try:
            results = combine_and_filter_results(met_results, aic_results)
            logger.info(f"Combined results count: {len(results)}")
        except Exception as combine_error:
            logger.error(f"Result combination error: {combine_error}", exc_info=True)
            results = []
        
        if not results:
            logger.warning("No results found for the search theme")
            return jsonify({
                'error': 'No results found. Try different search terms or check back later.',
                'theme': theme
            }), 404
        
        # Ensure all results are JSON serializable with extensive logging
        serializable_results = []
        for idx, result in enumerate(results):
            try:
                # Detailed serialization attempt
                serializable_result = {}
                for k, v in result.items():
                    try:
                        # Attempt to serialize each value
                        json.dumps(v)
                        serializable_result[k] = v
                    except TypeError:
                        # Log specific serialization failures
                        try:
                            serializable_result[k] = str(v)
                            logger.debug(f"Converted {k} to string: {serializable_result[k]}")
                        except Exception as convert_error:
                            logger.error(f"Failed to convert {k} for result {idx}: {convert_error}")
                            serializable_result[k] = f"Unconvertible value of type {type(v)}"
                
                serializable_results.append(serializable_result)
            except Exception as serialize_error:
                logger.error(f"Serialization error for result {idx}: {serialize_error}", exc_info=True)
        
        # Comprehensive response data
        response_data = {
            'results': serializable_results,
            'timestamp': int(time.time()),
            'theme': theme,
            'result_count': len(serializable_results)
        }
        
        # Log response data structure for debugging
        logger.debug(f"Response data structure: {json.dumps(response_data, indent=2)}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Unexpected search error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'An unexpected error occurred during search',
            'details': str(e),
            'theme': theme
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

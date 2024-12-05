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
                # URL encode the search term
                encoded_term = requests.utils.quote(term)
                search_url = f"{base_url}?q={encoded_term}&hasImages=true"
                
                logger.info(f"Making API request to: {search_url}")
                response = requests.get(search_url, timeout=10)
                
                logger.info(f"API Response status: {response.status_code}")
                if response.ok:
                    logger.info(f"API Response content: {response.text[:500]}")  # Log first 500 chars
                else:
                    logger.error(f"API Error response: {response.text}")
                
                if response.status_code == 429:
                    logger.error("Met API rate limit exceeded. Please try again later.")
                    break
                    
                if response.ok:
                    data = response.json()
                    if data.get('objectIDs'):
                        new_ids = set(id for id in data['objectIDs'] if id not in recently_shown_artworks)
                        all_ids.update(new_ids)
                        logger.info(f"Found {len(new_ids)} new artworks for term '{term}'")
                    else:
                        logger.warning(f"No objectIDs found for term '{term}'")
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while searching term: {term}")
                continue
            except Exception as e:
                logger.error(f"Error searching term '{term}': {str(e)}")
                continue
        
        logger.info(f"Total unique artworks found: {len(all_ids)}")
        
        if not all_ids:
            logger.warning(f"No results found for any search terms: {search_terms}")
            return []
        
        # Process artworks
        modern_artworks = []
        historic_artworks = []
        processed_count = 0
        
        # Randomize IDs
        id_list = list(all_ids)
        random.shuffle(id_list)
        
        # First pass: collect all artworks and sort them by period
        for obj_id in id_list:
            if processed_count >= 100:  # Limit total processed
                break
                
            try:
                logger.info(f"Fetching details for artwork ID: {obj_id}")
                obj_response = requests.get(f"{object_url}/{obj_id}", timeout=10)
                processed_count += 1
                
                if obj_response.status_code == 429:
                    logger.error("Met API rate limit exceeded while fetching artwork details")
                    break
                    
                if not obj_response.ok:
                    logger.error(f"Error fetching artwork {obj_id}: {obj_response.status_code} - {obj_response.text}")
                    continue
                    
                obj = obj_response.json()
                
                # Skip if no primary image
                primary_image = obj.get('primaryImage')
                if not primary_image or not primary_image.startswith('http'):
                    logger.debug(f"Skipping artwork {obj_id}: No valid primary image")
                    continue
                
                # Check if it's relevant to the search terms
                title = obj.get('title', '').lower()
                desc = obj.get('description', '').lower()
                tags = obj.get('tags', [])
                medium = obj.get('medium', '').lower()
                classification = obj.get('classification', '').lower()
                
                # Build a combined text for searching
                searchable_text = f"{title} {desc} {medium} {classification} {' '.join(tags)}".lower()
                logger.debug(f"Searchable text for {obj_id}: {searchable_text[:200]}...")  # Log first 200 chars
                
                # Check if any search term appears in the searchable text
                is_relevant = False
                for term in search_terms:
                    if term.lower() in searchable_text:
                        is_relevant = True
                        logger.info(f"Found relevant artwork: {title} (matches term: {term})")
                        break
                
                if not is_relevant:
                    logger.debug(f"Skipping artwork {obj_id}: Not relevant to search terms")
                    continue
                
                # Get the year and sort into modern/historic
                date_str = obj.get('objectDate', '')
                year = parse_artwork_date(date_str)
                
                # Check religious quota
                is_religious = is_religious_artwork(obj)
                
                artwork = create_artwork_dict(obj, is_religious, year)
                
                if year >= 1923:
                    if len(modern_artworks) < 10 and not (is_religious and sum(1 for a in modern_artworks if a.get('is_religious', False)) >= 1):
                        modern_artworks.append(artwork)
                        recently_shown_artworks.add(obj_id)
                        logger.info(f"Added modern artwork: {artwork['title']} ({year})")
                else:
                    if len(historic_artworks) < 10 and not (is_religious and sum(1 for a in historic_artworks if a.get('is_religious', False)) >= 1):
                        historic_artworks.append(artwork)
                        recently_shown_artworks.add(obj_id)
                        logger.info(f"Added historic artwork: {artwork['title']} ({year})")
                
                # Stop if we have enough of both
                if len(modern_artworks) >= 10 and len(historic_artworks) >= 10:
                    break
                
            except Exception as e:
                logger.error(f"Error processing artwork {obj_id}: {str(e)}")
                continue
        
        # Combine results
        results = modern_artworks + historic_artworks
        random.shuffle(results)
        
        logger.info(f"Final results - Modern: {len(modern_artworks)} ({[a['year'] for a in modern_artworks]})")
        logger.info(f"Final results - Historic: {len(historic_artworks)} ({[a['year'] for a in historic_artworks]})")
        
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

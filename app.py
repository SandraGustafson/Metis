import os
import random
import logging
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

def search_met_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Metropolitan Museum API for artwork matching the theme."""
    base_url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
    object_url = "https://collectionapi.metmuseum.org/public/collection/v1/objects"
    
    try:
        # Search for artworks
        search_url = f"{base_url}?q={theme}&hasImages=true"
        logger.info(f"Searching Met API with URL: {search_url}")
        response = requests.get(search_url, timeout=10)
        
        if response.status_code == 429:  # Rate limit exceeded
            logger.error("Met API rate limit exceeded. Please try again later.")
            return []
            
        if not response.ok:
            logger.error(f"Met API search failed: {response.status_code}")
            return []
            
        data = response.json()
        if not data.get('objectIDs'):
            logger.warning(f"No results found for theme: {theme}")
            return []
            
        # Get details for up to 20 random artworks
        results = []
        object_ids = data['objectIDs']
        logger.info(f"Found {len(object_ids)} total artworks for theme: {theme}")
        
        # Truly randomize the selection
        if len(object_ids) > 100:
            # Take a random sample of 100 IDs
            object_ids = random.sample(object_ids, 100)
        random.shuffle(object_ids)
        
        for obj_id in object_ids:
            if len(results) >= 20:  # Stop after getting 20 valid results
                break
                
            try:
                logger.info(f"Fetching details for artwork ID: {obj_id}")
                obj_response = requests.get(f"{object_url}/{obj_id}", timeout=10)
                
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
                    
                # Get basic metadata
                artist = obj.get('artistDisplayName', 'Unknown')
                culture = obj.get('culture', 'Unknown')
                period = obj.get('period', 'Unknown')
                
                artwork = {
                    'title': obj.get('title', 'Untitled'),
                    'artist': artist if artist != 'Unknown' else None,
                    'date': obj.get('objectDate', ''),
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
                    ]))
                }
                
                results.append(artwork)
                logger.info(f"Added artwork: {artwork['title']}")
                
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout while fetching artwork {obj_id}")
                continue
            except Exception as e:
                logger.error(f"Error processing Met object {obj_id}: {str(e)}")
                continue
                
        logger.info(f"Found {len(results)} valid results for theme: {theme}")
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

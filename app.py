import os
import re
import json
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
MET_API_KEY = os.getenv('MET_API_KEY')
AIC_API_KEY = os.getenv('AIC_API_KEY')
HARVARD_API_KEY = os.getenv('HARVARD_API_KEY')
YALE_API_KEY = os.getenv('YALE_API_KEY')
RIJKS_API_KEY = os.getenv('RIJKS_API_KEY')
SMITHSONIAN_API_KEY = os.getenv('SMITHSONIAN_API_KEY')
VICTORIA_ALBERT_API_KEY = os.getenv('VICTORIA_ALBERT_API_KEY')
MOMA_API_KEY = os.getenv('MOMA_API_KEY')
TATE_API_KEY = os.getenv('TATE_API_KEY')
POMPIDOU_API_KEY = os.getenv('POMPIDOU_API_KEY')
GUGGENHEIM_API_KEY = os.getenv('GUGGENHEIM_API_KEY')
WHITNEY_API_KEY = os.getenv('WHITNEY_API_KEY')
LACMA_API_KEY = os.getenv('LACMA_API_KEY')
STANFORD_API_KEY = os.getenv('STANFORD_API_KEY')
PRINCETON_API_KEY = os.getenv('PRINCETON_API_KEY')
OXFORD_API_KEY = os.getenv('OXFORD_API_KEY')
GOOGLE_ARTS_API_KEY = os.getenv('GOOGLE_ARTS_API_KEY')
EUROPEANA_API_KEY = os.getenv('EUROPEANA_API_KEY')
DPLA_API_KEY = os.getenv('DPLA_API_KEY')

# API endpoints and configuration
MET_API_URL = "https://collectionapi.metmuseum.org/public/collection/v1"
AIC_API_URL = "https://api.artic.edu/api/v1"
HARVARD_API_URL = "https://api.harvardartmuseums.org"
YALE_API_URL = "https://api.collections.yale.edu/v2"
RIJKS_API_URL = "https://www.rijksmuseum.nl/api/en"
SMITHSONIAN_API_URL = "https://api.si.edu/openaccess/api/v1.0"
VICTORIA_ALBERT_API_URL = "https://api.vam.ac.uk/v2"
MOMA_API_URL = "https://api.moma.org/v1"
TATE_API_URL = "https://api.tate.org.uk"
POMPIDOU_API_URL = "https://api.centrepompidou.fr"
GUGGENHEIM_API_URL = "https://api.guggenheim.org/collections"
WHITNEY_API_URL = "https://api.whitney.org"
LACMA_API_URL = "https://api.lacma.org"
STANFORD_API_URL = "https://api.museum.stanford.edu"
PRINCETON_API_URL = "https://data.artmuseum.princeton.edu"
OXFORD_API_URL = "https://api.museums.ox.ac.uk"
GOOGLE_ARTS_API_URL = "https://www.google.com/culturalinstitute/api"
EUROPEANA_API_URL = "https://api.europeana.eu/record/v2"
DPLA_API_URL = "https://api.dp.la/v2"
AAA_API_URL = "https://api.aaa.si.edu/collections"

def is_contemporary(date_str: str) -> bool:
    """
    Determine if an artwork is contemporary based on its date.
    Contemporary art is generally considered to be art produced from 1970 onwards.
    """
    if not date_str:
        return False
        
    date_str = str(date_str).lower().strip()
    
    # Handle empty or unknown dates
    if date_str in ['unknown', 'n.d.', 'none', '']:
        return False
    
    try:
        # Handle century descriptions
        if '21st century' in date_str or '21st c' in date_str:
            return True
        if '20th century' in date_str or '20th c' in date_str:
            if any(term in date_str for term in ['late', 'end', 'latter']):
                return True
        
        # Extract years using regex
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', date_str)
        if years:
            latest_year = max(int(year) for year in years)
            return latest_year >= 1970
            
    except Exception:
        pass
    
    return False

def has_valid_image(artwork: Dict[str, Any]) -> bool:
    """
    Check if an artwork has a valid image URL.
    Returns False for missing, unknown, or placeholder images.
    """
    image_url = artwork.get('image_url', '')
    if not image_url:
        return False
        
    # Check for common placeholder or unknown image indicators
    invalid_indicators = [
        'unknown',
        'placeholder',
        'no-image',
        'default',
        'missing',
        'not-available',
        'null',
        'none'
    ]
    
    image_url_lower = image_url.lower()
    return not any(indicator in image_url_lower for indicator in invalid_indicators)

def filter_valid_artworks(artworks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter a list of artworks to only include those with valid images
    and required metadata.
    """
    return [
        artwork for artwork in artworks
        if has_valid_image(artwork) and
        artwork.get('title') and  # Must have a title
        artwork.get('date') and   # Must have a date
        any([                     # Must have at least one of these fields
            artwork.get('description'),
            artwork.get('medium'),
            artwork.get('culture'),
            artwork.get('period')
        ])
    ]

def preprocess_theme(theme: str) -> Dict[str, Any]:
    """
    Analyze the search theme as a single concept.
    Returns a dictionary with processed theme information.
    """
    try:
        import spacy
        # Try to use spaCy if available
        try:
            nlp = spacy.load('en_core_web_lg')
            # Process with spaCy
            doc = nlp(theme.lower())
            
            # Keep the theme as a single unit
            theme_phrase = theme.lower()
            
            # Extract named entities but exclude PERSON type
            entities = [ent.text for ent in doc.ents if ent.label_ != 'PERSON']
            
            return {
                'original': theme,
                'theme_phrase': theme_phrase,
                'entities': entities,
                'use_spacy': True,
                'doc': doc
            }
        except OSError:
            # spaCy model not found, fall back to basic processing
            raise ImportError
            
    except ImportError:
        # Basic processing without spaCy
        theme_phrase = theme.lower()
        
        return {
            'original': theme,
            'theme_phrase': theme_phrase,
            'entities': [],
            'use_spacy': False,
            'doc': None
        }

def get_time_period(theme: str) -> Dict[str, Any]:
    """
    Identify if a theme refers to a specific historical period and return its date range.
    """
    historical_periods = {
        'cold war': {
            'start': 1947,
            'end': 1991,
            'aliases': [],
            'keywords': [
                'iron curtain',
                'nuclear',
                'atomic',
                'communist',
                'soviet',
                'propaganda',
                'space race',
                'berlin wall',
                'vietnam war',
                'korean war',
                'arms race',
                'missile crisis',
                'mccarthyism'
            ]
        },
        'world war 2': {'start': 1939, 'end': 1945, 'aliases': ['ww2', 'wwii', 'second world war']},
        'world war 1': {'start': 1914, 'end': 1918, 'aliases': ['ww1', 'wwi', 'first world war', 'great war']},
        'cold war': {'start': 1947, 'end': 1991, 'aliases': []},
        'vietnam war': {'start': 1955, 'end': 1975, 'aliases': []},
        'korean war': {'start': 1950, 'end': 1953, 'aliases': []},
        'great depression': {'start': 1929, 'end': 1939, 'aliases': []},
        'civil rights movement': {'start': 1954, 'end': 1968, 'aliases': []},
        'industrial revolution': {'start': 1760, 'end': 1840, 'aliases': []},
        'renaissance': {'start': 1300, 'end': 1600, 'aliases': []},
        'medieval period': {'start': 476, 'end': 1450, 'aliases': ['middle ages', 'medieval era']},
        'gilded age': {'start': 1870, 'end': 1900, 'aliases': []},
        'roaring twenties': {'start': 1920, 'end': 1929, 'aliases': ['1920s']},
        'progressive era': {'start': 1896, 'end': 1916, 'aliases': []},
        'reconstruction era': {'start': 1865, 'end': 1877, 'aliases': ['reconstruction period']},
        'victorian era': {'start': 1837, 'end': 1901, 'aliases': ['victorian period']},
    }
    
    theme_lower = theme.lower()
    
    # Check direct matches and aliases
    for period, info in historical_periods.items():
        if period in theme_lower or any(alias in theme_lower for alias in info.get('aliases', [])):
            result = {
                'name': period,
                'start': info['start'],
                'end': info['end'],
                'is_historical_period': True,
                'keywords': info.get('keywords', [])
            }
            return result
    
    # Check for century references (e.g., "19th century")
    century_match = re.search(r'(\d+)(st|nd|rd|th)\s+century', theme_lower)
    if century_match:
        century = int(century_match.group(1))
        start_year = (century - 1) * 100
        end_year = century * 100
        return {
            'name': f"{century_match.group(1)}{century_match.group(2)} century",
            'start': start_year,
            'end': end_year,
            'is_historical_period': True,
            'keywords': []
        }
    
    # Check for decade references (e.g., "1960s")
    decade_match = re.search(r'(\d{3})0s', theme_lower)
    if decade_match:
        decade_start = int(f"{decade_match.group(1)}0")
        return {
            'name': f"{decade_start}s",
            'start': decade_start,
            'end': decade_start + 9,
            'is_historical_period': True,
            'keywords': []
        }
    
    return {'is_historical_period': False, 'keywords': []}

def extract_year_from_date(date_str: str) -> Optional[int]:
    """
    Extract a year from various date string formats.
    """
    if not date_str:
        return None
        
    # Try to extract a year from the date string
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if year_match:
        return int(year_match.group(1))
    
    # Handle century descriptions (e.g., "19th century")
    century_match = re.search(r'(\d+)(st|nd|rd|th)\s+century', date_str.lower())
    if century_match:
        century = int(century_match.group(1))
        return (century - 1) * 100 + 50  # Return mid-century year
    
    # Handle decade descriptions (e.g., "1960s")
    decade_match = re.search(r'(\d{3})0s', date_str)
    if decade_match:
        return int(f"{decade_match.group(1)}5")  # Return mid-decade year
    
    return None

def calculate_relevance_score(artwork: Dict[str, Any], theme_info: Dict[str, Any]) -> float:
    """
    Calculate relevance score treating theme as a single concept.
    Explicitly excludes artist names from matching and considers historical periods.
    """
    score = 0.0
    
    # Get artist name to exclude from matching
    artist_name = artwork.get('artist', '').lower()
    
    # Combine all relevant artwork text fields EXCEPT artist name
    artwork_text = ' '.join(filter(None, [
        artwork.get('title', ''),
        artwork.get('description', ''),
        artwork.get('medium', ''),
        artwork.get('culture', ''),
        artwork.get('period', ''),
        artwork.get('style', ''),
        artwork.get('tags', ''),
        artwork.get('classification', '')
    ])).lower()
    
    # Remove any mentions of the artist name from the artwork text
    if artist_name:
        # Split artist name into parts and remove each part
        artist_parts = artist_name.split()
        for part in artist_parts:
            if len(part) > 2:  # Only remove parts longer than 2 characters
                artwork_text = artwork_text.replace(part, '')
    
    # Check if theme refers to a historical period
    time_period = get_time_period(theme_info['original'])
    if time_period['is_historical_period']:
        artwork_year = extract_year_from_date(artwork.get('date', ''))
        
        # Check temporal relevance
        if artwork_year:
            # Direct match for works created during the period
            if time_period['start'] <= artwork_year <= time_period['end']:
                score += 5.0
            # Smaller boost for works created within 10 years after the period
            elif time_period['end'] < artwork_year <= time_period['end'] + 10:
                score += 2.0
            # Even smaller boost for works created within 20 years after
            elif time_period['end'] + 10 < artwork_year <= time_period['end'] + 20:
                score += 1.0
        
        # Check for period-specific keywords
        for keyword in time_period.get('keywords', []):
            if keyword in artwork_text:
                score += 2.0
    
    if theme_info['use_spacy']:
        try:
            import spacy
            nlp = spacy.load('en_core_web_lg')
            artwork_doc = nlp(artwork_text)
            
            # Vector similarity if both have vectors
            if theme_info['doc'].has_vector and artwork_doc.has_vector:
                similarity = theme_info['doc'].similarity(artwork_doc)
                score += similarity * 2.0
                
                # Boost score if the exact theme phrase appears
                if theme_info['theme_phrase'] in artwork_text:
                    score += 1.0
        except:
            # If spaCy fails, fall back to basic matching
            pass
    
    # Basic text matching (always performed as backup)
    # Check for exact theme phrase match
    if theme_info['theme_phrase'] in artwork_text:
        score += 3.0
    
    # Check for entity matches (excluding PERSON entities)
    for entity in theme_info['entities']:
        if entity.lower() in artwork_text:
            score += 1.0
    
    # Analyze temporal relevance for non-historical themes
    if not time_period['is_historical_period'] and is_contemporary(artwork.get('date', '')):
        score += 0.3
    
    # Add small randomization factor to prevent same-score clustering
    import random
    score += random.uniform(0, 0.1)
    
    # Normalize score to 0-1 range
    return min(score / 10.0, 1.0)

def get_artwork_context(artwork: Dict[str, Any], theme_info: Dict[str, Any]) -> str:
    """
    Generate contextual connections between the artwork and the search theme.
    Works with or without spaCy. Excludes artist names from theme matching.
    """
    context_points = []
    
    # Get artwork description, excluding artist name
    artwork_text = ' '.join(filter(None, [
        artwork.get('title', ''),
        artwork.get('description', ''),
        artwork.get('medium', ''),
        artwork.get('culture', ''),
        artwork.get('period', '')
    ]))
    
    if not artwork_text.strip():
        return ""
    
    # Try to use spaCy for advanced analysis if available
    if theme_info['use_spacy']:
        try:
            import spacy
            nlp = spacy.load('en_core_web_lg')
            artwork_doc = nlp(artwork_text)
            theme_doc = theme_info['doc']
            
            if artwork_doc.has_vector and theme_doc.has_vector:
                similarity = artwork_doc.similarity(theme_doc)
                if similarity > 0.3:
                    context_points.append(f"This artwork shows strong thematic connections to your search theme.")
        except:
            pass
    
    # Basic context gathering (always performed)
    if artwork.get('date'):
        context_points.append(f"Created in {artwork.get('date')}")
    
    if artwork.get('culture'):
        context_points.append(f"Cultural Context: {artwork.get('culture')}")
    
    if artwork.get('period'):
        context_points.append(f"Period: {artwork.get('period')}")
    
    if artwork.get('medium'):
        context_points.append(f"Medium & Technique: {artwork.get('medium')}")
    
    # Add artist information separately, not as part of theme matching
    if artwork.get('artist'):
        context_points.append(f"Artist: {artwork.get('artist')}")
    
    return "\n".join(context_points)

def search_met_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search the Metropolitan Museum of Art's collection."""
    try:
        theme_info = preprocess_theme(theme)
        
        # First, search for objects
        search_url = f"https://collectionapi.metmuseum.org/public/collection/v1/search?q={theme}"
        response = requests.get(search_url)
        if not response.ok:
            return []
            
        data = response.json()
        if not data.get('objectIDs'):
            return []
            
        # Get details for each object
        artworks = []
        # Limit to first 20 results for performance
        for object_id in data['objectIDs'][:20]:
            details_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}"
            details_response = requests.get(details_url)
            if not details_response.ok:
                continue
                
            artwork = details_response.json()
            
            # Create standardized artwork object
            processed_artwork = {
                'title': artwork.get('title'),
                'artist': artwork.get('artistDisplayName'),
                'date': artwork.get('objectDate'),
                'medium': artwork.get('medium'),
                'description': artwork.get('objectDescription', ''),
                'culture': artwork.get('culture', ''),
                'period': artwork.get('period', ''),
                'image_url': artwork.get('primaryImageSmall') or artwork.get('primaryImage'),
                'source_url': artwork.get('objectURL'),
                'source': 'Metropolitan Museum of Art',
                'department': artwork.get('department'),
                'classification': artwork.get('classification', ''),
                'tags': ', '.join(filter(None, [
                    artwork.get('culture'),
                    artwork.get('period'),
                    artwork.get('classification')
                ]))
            }
            
            # Only add artwork if it has a valid image
            if has_valid_image(processed_artwork):
                artworks.append(processed_artwork)
        
        # Filter and score artworks
        valid_artworks = filter_valid_artworks(artworks)
        scored_artworks = [
            {**artwork, 'score': calculate_relevance_score(artwork, theme_info)}
            for artwork in valid_artworks
        ]
        
        # Sort by score and return top results
        return sorted(scored_artworks, key=lambda x: x['score'], reverse=True)
        
    except Exception as e:
        print(f"Met Museum API error: {str(e)}")
        return []

def search_aic_artwork(theme: str) -> List[Dict[str, Any]]:
    theme_info = preprocess_theme(theme)
    search_url = f"{AIC_API_URL}/artworks/search"
    params = {
        'q': theme_info['original'],
        'limit': 20,  # Get more results initially for filtering
        'fields': 'id,title,image_id,date_display,artist_display,medium_display,artwork_type_title,style_title,classification_title,subject_titles,theme_titles,exhibition_history,publication_history,artist_bio'
    }
    
    response = requests.get(search_url, params=params)
    if response.status_code != 200:
        return []
    
    data = response.json()
    artworks = []
    
    for artwork in data.get('data', []):
        if artwork.get('image_id'):
            # Calculate relevance score
            artwork['relevance_score'] = calculate_relevance_score(artwork, theme_info)
            
            # Get artist statement if available
            artist_statement = ""
            
            context = []
            if artwork.get('artist_bio'):
                context.append(f"About the artist: {artwork.get('artist_bio')}")
            
            if artist_statement:
                context.append(f"\nArtist Statement: {artist_statement}")
            
            if artwork.get('medium_display'):
                context.append(f"\nMedium: {artwork.get('medium_display')}")
            
            if artwork.get('exhibition_history'):
                context.append(f"\nExhibition History: {artwork.get('exhibition_history')}")
            
            image_url = f"https://www.artic.edu/iiif/2/{artwork['image_id']}/full/843,/0/default.jpg"
            
            artworks.append({
                'title': artwork.get('title', 'Unknown'),
                'artist': artwork.get('artist_display', 'Unknown Artist'),
                'date': artwork.get('date_display', 'Unknown Date'),
                'image_url': image_url,
                'description': ' '.join(context),
                'source': 'Art Institute of Chicago',
                'more_info': f"https://www.artic.edu/artworks/{artwork['id']}",
                'relevance_score': artwork['relevance_score'],
                'is_contemporary': is_contemporary(artwork.get('date_display', ''))
            })
    
    # Sort by relevance score and contemporaneity
    artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
    return artworks[:5]  # Return top 5 most relevant results

def search_harvard_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Harvard Art Museums collection"""
    if not HARVARD_API_KEY or HARVARD_API_KEY == 'your_harvard_api_key_here':
        return []  # Skip if no valid API key
        
    try:
        theme_info = preprocess_theme(theme)
        params = {
            'apikey': HARVARD_API_KEY,
            'q': theme_info['original'],
            'size': 20,
            'sort': 'dateend',
            'sortorder': 'desc',
            'fields': 'id,title,primaryimageurl,people,dated,division,description,url,provenance,commentary,labeltext,technique,period,culture',
            'hasimage': 1
        }
        
        response = requests.get(HARVARD_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for record in data.get('records', []):
            if record.get('primaryimageurl'):
                # Calculate relevance score
                record['relevance_score'] = calculate_relevance_score(record, theme_info)
                
                # Get artist info
                artist_info = record.get('people', [{}])[0]
                artist_name = artist_info.get('displayname', 'Unknown Artist')
                
                context = []
                
                # Add artist information
                if artist_info.get('displayname'):
                    context.append(f"Created by {artist_info.get('displayname')}")
                    if artist_info.get('culture'):
                        context.append(f"({artist_info.get('culture')})")
                
                # Add technique and medium
                if record.get('technique'):
                    context.append(f"\nTechnique: {record.get('technique')}")
                
                # Add curatorial commentary
                if record.get('commentary'):
                    context.append(f"\nCuratorial Notes: {record.get('commentary')}")
                elif record.get('labeltext'):
                    context.append(f"\nGallery Label: {record.get('labeltext')}")
                
                # Add provenance
                if record.get('provenance'):
                    context.append(f"\nProvenance: {record.get('provenance')}")
                
                artworks.append({
                    'title': record.get('title', 'Unknown'),
                    'artist': artist_name,
                    'date': record.get('dated', 'Unknown Date'),
                    'image_url': record['primaryimageurl'],
                    'description': ' '.join(context),
                    'source': 'Harvard Art Museums',
                    'more_info': record.get('url', ''),
                    'relevance_score': record['relevance_score'],
                    'is_contemporary': is_contemporary(record.get('dated', ''))
                })
        
        # Sort by relevance score and contemporaneity
        artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
        return artworks[:5]
    
    except Exception as e:
        print(f"Error searching Harvard Art Museums: {e}")
        return []

def search_yale_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Yale University Art Gallery collection"""
    if not YALE_API_KEY:
        return []
        
    theme_info = preprocess_theme(theme)
    params = {
        'key': YALE_API_KEY,
        'q': theme_info['original'],
        'limit': 20,
        'hasImage': 'true',
        'sortBy': 'yearLatest',
        'sortOrder': 'desc'
    }
    
    try:
        response = requests.get(YALE_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for record in data.get('data', []):
            if record.get('imageUrl'):
                # Calculate relevance score
                record['relevance_score'] = calculate_relevance_score(record, theme_info)
                
                context = []
                
                # Add artist information
                if record.get('agents'):
                    artist = record['agents'][0]
                    context.append(f"Created by {artist.get('name', 'Unknown Artist')}")
                    if artist.get('biography'):
                        context.append(f"({artist.get('biography')})")
                
                # Add medium and technique
                if record.get('medium'):
                    context.append(f"\nMedium: {record.get('medium')}")
                
                # Add curatorial description
                if record.get('description'):
                    context.append(f"\nDescription: {record.get('description')}")
                
                # Add exhibition history
                if record.get('exhibitions'):
                    exhibitions = record['exhibitions'][:3]  # List up to 3 recent exhibitions
                    context.append("\nExhibition History: " + 
                                "; ".join(ex.get('title', '') for ex in exhibitions))
                
                artworks.append({
                    'title': record.get('title', 'Unknown'),
                    'artist': record.get('agents', [{}])[0].get('name', 'Unknown Artist'),
                    'date': record.get('dated', 'Unknown Date'),
                    'image_url': record['imageUrl'],
                    'description': ' '.join(context),
                    'source': 'Yale University Art Gallery',
                    'more_info': record.get('website', ''),
                    'relevance_score': record['relevance_score'],
                    'is_contemporary': is_contemporary(record.get('dated', ''))
                })
        
        # Sort by relevance score and contemporaneity
        artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
        return artworks[:5]
    
    except Exception as e:
        print(f"Error searching Yale Art Gallery: {e}")
        return []

def search_rijksmuseum_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Rijksmuseum collection"""
    if not RIJKS_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'key': RIJKS_API_KEY,
        'q': theme_info['original'],
        'ps': 20,  # page size
        'imgonly': True,
        'toppieces': True,
        'format': 'json'
    }
    
    try:
        response = requests.get(f"{RIJKS_API_URL}", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('artObjects', []):
            # Calculate relevance score
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            # Get detailed information
            detail_response = requests.get(f"{RIJKS_API_URL}/{art['objectNumber']}", 
                                        params={'key': RIJKS_API_KEY, 'format': 'json'})
            if detail_response.status_code == 200:
                details = detail_response.json().get('artObject', {})
                
                context = []
                
                # Add artist information
                if details.get('principalMaker'):
                    context.append(f"Created by {details.get('principalMaker')}")
                    if details.get('physicalMedium'):
                        context.append(f"\nMedium: {details.get('physicalMedium')}")
                
                # Add description
                if details.get('label', {}).get('description'):
                    context.append(f"\nDescription: {details['label']['description']}")
                
                # Add exhibition history
                if details.get('exhibitions'):
                    recent_exhibitions = details['exhibitions'][:3]
                    context.append("\nExhibition History: " + 
                                "; ".join(ex.get('title', '') for ex in recent_exhibitions))
                
                artworks.append({
                    'title': art.get('title', 'Unknown'),
                    'artist': art.get('principalOrFirstMaker', 'Unknown Artist'),
                    'date': art.get('dating', {}).get('presentingDate', 'Unknown Date'),
                    'image_url': art.get('webImage', {}).get('url', ''),
                    'description': ' '.join(context),
                    'source': 'Rijksmuseum',
                    'more_info': art.get('links', {}).get('web', ''),
                    'relevance_score': art['relevance_score'],
                    'is_contemporary': is_contemporary(str(art.get('dating', {}).get('sortingDate', '')))
                })
        
        artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
        return artworks[:5]
    
    except Exception as e:
        print(f"Error searching Rijksmuseum: {e}")
        return []

def search_smithsonian_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Smithsonian American Art Museum collection"""
    if not SMITHSONIAN_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    headers = {
        'api_key': SMITHSONIAN_API_KEY
    }
    
    params = {
        'q': theme_info['original'],
        'rows': 20,
        'type': 'edanmdm',
        'images': 1
    }
    
    try:
        response = requests.get(SMITHSONIAN_API_URL, headers=headers, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for record in data.get('response', {}).get('rows', []):
            content = record.get('content', {})
            
            # Calculate relevance score
            content['relevance_score'] = calculate_relevance_score(content, theme_info)
            
            context = []
            
            # Add artist information
            if content.get('nameContent'):
                context.append(f"Created by {content['nameContent']}")
            
            # Add medium information
            if content.get('physicalDescription'):
                context.append(f"\nMedium: {content['physicalDescription']}")
            
            # Add notes
            if content.get('notes'):
                context.append(f"\nCuratorial Notes: {content['notes']}")
            
            image_url = None
            if content.get('descriptiveNonRepeating', {}).get('online_media', {}).get('media', []):
                media = content['descriptiveNonRepeating']['online_media']['media'][0]
                image_url = media.get('content')
            
            if image_url:
                artworks.append({
                    'title': content.get('title', {}).get('content', 'Unknown'),
                    'artist': content.get('nameContent', 'Unknown Artist'),
                    'date': content.get('date', 'Unknown Date'),
                    'image_url': image_url,
                    'description': ' '.join(context),
                    'source': 'Smithsonian American Art Museum',
                    'more_info': content.get('record_link', ''),
                    'relevance_score': content['relevance_score'],
                    'is_contemporary': is_contemporary(content.get('date', ''))
                })
        
        artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
        return artworks[:5]
    
    except Exception as e:
        print(f"Error searching Smithsonian: {e}")
        return []

def search_victoria_albert_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Victoria and Albert Museum collection"""
    if not VICTORIA_ALBERT_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'images': 1,
        'api_key': VICTORIA_ALBERT_API_KEY
    }
    
    try:
        response = requests.get(VICTORIA_ALBERT_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for record in data.get('records', []):
            # Calculate relevance score
            record['relevance_score'] = calculate_relevance_score(record, theme_info)
            
            context = []
            
            # Add artist information
            if record.get('artistMaker'):
                context.append(f"Created by {record['artistMaker']}")
            
            # Add medium and technique
            if record.get('materials') or record.get('techniques'):
                materials = []
                if record.get('materials'): materials.append(record['materials'])
                if record.get('techniques'): materials.extend(record['techniques'])
                context.append(f"\nMaterials and Techniques: {', '.join(materials)}")
            
            # Add description
            if record.get('description'):
                context.append(f"\nDescription: {record['description']}")
            
            if record.get('image'):
                artworks.append({
                    'title': record.get('title', 'Unknown'),
                    'artist': record.get('artistMaker', 'Unknown Artist'),
                    'date': record.get('date', 'Unknown Date'),
                    'image_url': record['image'],
                    'description': ' '.join(context),
                    'source': 'Victoria and Albert Museum',
                    'more_info': record.get('url', ''),
                    'relevance_score': record['relevance_score'],
                    'is_contemporary': is_contemporary(record.get('date', ''))
                })
        
        artworks.sort(key=lambda x: (x['is_contemporary'], x['relevance_score']), reverse=True)
        return artworks[:5]
    
    except Exception as e:
        print(f"Error searching Victoria and Albert Museum: {e}")
        return []

def search_moma_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search MoMA collection"""
    if not MOMA_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': MOMA_API_KEY
    }
    
    try:
        response = requests.get(f"{MOMA_API_URL}/artworks/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('data', []):
            # Calculate relevance score
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist', {}).get('name'):
                context.append(f"Created by {art['artist']['name']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', {}).get('name', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImageUrl', ''),
                'description': ' '.join(context),
                'source': 'Museum of Modern Art',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching MoMA: {e}")
        return []

def search_tate_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Tate collection"""
    if not TATE_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': TATE_API_KEY
    }
    
    try:
        response = requests.get(TATE_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('results', []):
            # Calculate relevance score
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist'):
                context.append(f"Created by {art['artist']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', 'Unknown Artist'),
                'date': art.get('dateText', 'Unknown Date'),
                'image_url': art.get('thumbnailUrl', ''),
                'description': ' '.join(context),
                'source': 'Tate Modern',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('dateText', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Tate: {e}")
        return []

def search_pompidou_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Centre Pompidou collection"""
    if not POMPIDOU_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': POMPIDOU_API_KEY
    }
    
    try:
        response = requests.get(f"{POMPIDOU_API_URL}/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('works', []):
            # Calculate relevance score
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist'):
                context.append(f"Created by {art['artist']}")
            
            if art.get('medium') or art.get('techniques'):
                materials = []
                if art.get('medium'): materials.append(art['medium'])
                if art.get('techniques'): materials.extend(art['techniques'])
                context.append(f"\nMaterials and Techniques: {', '.join(materials)}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('imageUrl', ''),
                'description': ' '.join(context),
                'source': 'Centre Pompidou',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Centre Pompidou: {e}")
        return []

def search_guggenheim_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Guggenheim collection"""
    if not GUGGENHEIM_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': GUGGENHEIM_API_KEY
    }
    
    try:
        response = requests.get(f"{GUGGENHEIM_API_URL}/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('objects', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist', {}).get('name'):
                context.append(f"Created by {art['artist']['name']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('exhibitions'):
                recent = art['exhibitions'][:3]
                context.append("\nExhibition History: " + 
                            "; ".join(ex.get('title', '') for ex in recent))
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', {}).get('name', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImage', ''),
                'description': ' '.join(context),
                'source': 'Guggenheim Museum',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Guggenheim: {e}")
        return []

def search_whitney_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Whitney Museum collection"""
    if not WHITNEY_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': WHITNEY_API_KEY
    }
    
    try:
        response = requests.get(WHITNEY_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('data', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist'):
                context.append(f"Created by {art['artist']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('image', ''),
                'description': ' '.join(context),
                'source': 'Whitney Museum',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Whitney: {e}")
        return []

def search_lacma_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search LACMA collection"""
    if not LACMA_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': LACMA_API_KEY
    }
    
    try:
        response = requests.get(f"{LACMA_API_URL}/collections/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('data', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('artist'):
                context.append(f"Created by {art['artist']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('creditLine'):
                context.append(f"\n{art['creditLine']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('artist', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImage', ''),
                'description': ' '.join(context),
                'source': 'Los Angeles County Museum of Art',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching LACMA: {e}")
        return []

def search_stanford_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Stanford Museums collection"""
    if not STANFORD_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': STANFORD_API_KEY
    }
    
    try:
        response = requests.get(STANFORD_API_URL, params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('objects', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('creator'):
                context.append(f"Created by {art['creator']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('culture'):
                context.append(f"\nCulture: {art['culture']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('creator', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImage', ''),
                'description': ' '.join(context),
                'source': 'Stanford University Museums',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Stanford Museums: {e}")
        return []

def search_princeton_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Princeton Art Museum collection"""
    if not PRINCETON_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': PRINCETON_API_KEY
    }
    
    try:
        response = requests.get(f"{PRINCETON_API_URL}/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('records', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('maker'):
                context.append(f"Created by {art['maker']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('period'):
                context.append(f"\nPeriod: {art['period']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('maker', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImage', ''),
                'description': ' '.join(context),
                'source': 'Princeton University Art Museum',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Princeton Art Museum: {e}")
        return []

def search_oxford_artwork(theme: str) -> List[Dict[str, Any]]:
    """Search Oxford University Museums collection"""
    if not OXFORD_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'api_key': OXFORD_API_KEY
    }
    
    try:
        response = requests.get(f"{OXFORD_API_URL}/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('records', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('creator'):
                context.append(f"Created by {art['creator']}")
            
            if art.get('materials'):
                context.append(f"\nMaterials: {art['materials']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('period') or art.get('culture'):
                period_culture = []
                if art.get('period'): period_culture.append(art['period'])
                if art.get('culture'): period_culture.append(art['culture'])
                context.append(f"\nContext: {', '.join(period_culture)}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('creator', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImage', ''),
                'description': ' '.join(context),
                'source': 'Oxford University Museums',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Oxford Museums: {e}")
        return []

def search_google_arts_culture(theme: str) -> List[Dict[str, Any]]:
    """Search Google Arts & Culture collection"""
    if not GOOGLE_ARTS_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'limit': 20,
        'key': GOOGLE_ARTS_API_KEY
    }
    
    try:
        response = requests.get(f"{GOOGLE_ARTS_API_URL}/search", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('items', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('creator'):
                context.append(f"Created by {art['creator']}")
            
            if art.get('medium'):
                context.append(f"\nMedium: {art['medium']}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description']}")
            
            if art.get('provider'):
                context.append(f"\nProvider: {art['provider']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('creator', 'Unknown Artist'),
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('primaryImageUrl', ''),
                'description': ' '.join(context),
                'source': 'Google Arts & Culture',
                'more_info': art.get('url', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Google Arts & Culture: {e}")
        return []

def search_europeana(theme: str) -> List[Dict[str, Any]]:
    """Search Europeana Collections"""
    if not EUROPEANA_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'query': theme_info['original'],
        'rows': 20,
        'profile': 'rich',
        'wskey': EUROPEANA_API_KEY,
        'media': True,
        'qf': 'TYPE:IMAGE'
    }
    
    try:
        response = requests.get(f"{EUROPEANA_API_URL}/search.json", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('items', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('dcCreator'):
                context.append(f"Created by {art['dcCreator'][0]}")
            
            if art.get('dcFormat'):
                context.append(f"\nMedium: {art['dcFormat'][0]}")
            
            if art.get('dcDescription'):
                context.append(f"\nDescription: {art['dcDescription'][0]}")
            
            if art.get('dataProvider'):
                context.append(f"\nProvider: {art['dataProvider'][0]}")
            
            artworks.append({
                'title': art.get('title', ['Unknown'])[0],
                'artist': art.get('dcCreator', ['Unknown Artist'])[0],
                'date': art.get('year', ['Unknown Date'])[0],
                'image_url': art.get('edmIsShownBy', [''])[0],
                'description': ' '.join(context),
                'source': 'Europeana Collections',
                'more_info': art.get('guid', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('year', [''])[0])
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching Europeana: {e}")
        return []

def search_dpla(theme: str) -> List[Dict[str, Any]]:
    """Search Digital Public Library of America"""
    if not DPLA_API_KEY:
        return []
    
    theme_info = preprocess_theme(theme)
    params = {
        'q': theme_info['original'],
        'page_size': 20,
        'api_key': DPLA_API_KEY,
        'field_type': ['image']
    }
    
    try:
        response = requests.get(f"{DPLA_API_URL}/items", params=params)
        if response.status_code != 200:
            return []
        
        data = response.json()
        artworks = []
        
        for art in data.get('docs', []):
            art['relevance_score'] = calculate_relevance_score(art, theme_info)
            
            context = []
            
            if art.get('creator'):
                context.append(f"Created by {art['creator'][0]}")
            
            if art.get('format'):
                context.append(f"\nFormat: {art['format'][0]}")
            
            if art.get('description'):
                context.append(f"\nDescription: {art['description'][0]}")
            
            if art.get('dataProvider'):
                context.append(f"\nProvider: {art['dataProvider']}")
            
            artworks.append({
                'title': art.get('title', 'Unknown'),
                'artist': art.get('creator', ['Unknown Artist'])[0] if art.get('creator') else 'Unknown Artist',
                'date': art.get('date', 'Unknown Date'),
                'image_url': art.get('object', ''),
                'description': ' '.join(context),
                'source': 'Digital Public Library of America',
                'more_info': art.get('isShownAt', ''),
                'relevance_score': art['relevance_score'],
                'is_contemporary': is_contemporary(art.get('date', ''))
            })
        
        return artworks
    
    except Exception as e:
        print(f"Error searching DPLA: {e}")
        return []

from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
from flask_cors import CORS
import os
import spacy

# Initialize spaCy - make it a global variable
try:
    nlp = spacy.load('en_core_web_lg')
except OSError:
    # If model is not found, download it
    os.system('python -m spacy download en_core_web_lg')
    nlp = spacy.load('en_core_web_lg')

app = Flask(__name__, 
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'),
    static_url_path='/static')
Bootstrap(app)
CORS(app)  # Enable CORS for all routes

# Get port from environment variable (for deployment)
port = int(os.environ.get('PORT', 10000))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        # Try to get theme from JSON data first
        if request.is_json:
            data = request.get_json()
            theme = data.get('theme', '').strip() if data else ''
        else:
            # Fall back to form data
            theme = request.form.get('theme', '').strip()
        
        if not theme:
            return jsonify({'error': 'Theme cannot be empty'}), 400
        
        # Track API errors
        api_errors = []
        all_results = []
        
        # Define all search functions to use
        search_functions = [
            ('Met Museum', search_met_artwork),
            ('Art Institute of Chicago', search_aic_artwork),
            ('Harvard Art Museums', search_harvard_artwork),
            ('Yale University Art Gallery', search_yale_artwork),
            ('Rijksmuseum', search_rijksmuseum_artwork),
            ('Smithsonian', search_smithsonian_artwork),
            ('Victoria and Albert Museum', search_victoria_albert_artwork),
            ('MoMA', search_moma_artwork),
            ('Tate', search_tate_artwork),
            ('Centre Pompidou', search_pompidou_artwork),
            ('Guggenheim', search_guggenheim_artwork),
            ('Whitney Museum', search_whitney_artwork),
            ('LACMA', search_lacma_artwork),
            ('Stanford Museums', search_stanford_artwork),
            ('Princeton Art Museum', search_princeton_artwork),
            ('Oxford Museums', search_oxford_artwork),
            ('Google Arts & Culture', search_google_arts_culture),
            ('Europeana', search_europeana),
            ('Digital Public Library of America', search_dpla)
        ]
        
        # Use ThreadPoolExecutor for parallel API requests
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_api = {
                executor.submit(search_func, theme): api_name 
                for api_name, search_func in search_functions
            }
            
            for future in future_to_api:
                api_name = future_to_api[future]
                try:
                    results = future.result(timeout=30)  # 30 second timeout per API
                    if results:
                        all_results.extend(results)
                except Exception as e:
                    api_errors.append(f"{api_name} API error: {str(e)}")
        
        if not all_results:
            message = "No artworks found matching your theme."
            if api_errors:
                message += " Some APIs encountered errors."
            return jsonify({
                'error': message,
                'api_errors': api_errors
            }), 404
        
        # Sort results by relevance score, prioritizing works from the historical period
        theme_info = preprocess_theme(theme)
        time_period = get_time_period(theme)
        
        def sort_key(artwork):
            score = artwork.get('relevance_score', 0)
            
            # Boost score for works from the historical period
            if time_period['is_historical_period']:
                artwork_year = extract_year_from_date(artwork.get('date', ''))
                if artwork_year and time_period['start'] <= artwork_year <= time_period['end']:
                    score *= 2.0
            
            return score
        
        all_results.sort(key=sort_key, reverse=True)
        
        # Limit to top 20 results (increased from 10 since we have more sources)
        all_results = all_results[:20]
        
        response = {
            'results': all_results,
            'total_sources': len(search_functions),
            'successful_sources': len(search_functions) - len(api_errors)
        }
        
        if api_errors:
            response['api_errors'] = api_errors
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=False)
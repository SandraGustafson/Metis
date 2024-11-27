# Art Education Resource Finder

This web application helps educators find relevant artwork to enhance their lessons by connecting visual art with educational themes. The app searches through multiple major art collections worldwide to find artwork that aligns with teaching topics through imagery, historical relevance, or artist biography.

## Features

- Search for artwork based on educational themes or historical periods
- Smart temporal matching for historical periods (e.g., "Cold War", "World War 2")
- Get 20 curated artwork suggestions from multiple museums
- View high-quality images of artwork
- Get contextual information about each artwork's connection to the theme
- Access artwork from renowned museums and galleries worldwide

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   python -m spacy download en_core_web_lg  # Download spaCy language model
   ```

## Running Locally

1. Activate the virtual environment if not already activated
2. Set up your environment variables in a `.env` file:
   ```
   MET_API_KEY=your_key_here
   AIC_API_KEY=your_key_here
   # Add other API keys as needed
   ```
3. Run the Flask application:
   ```bash
   python app.py
   ```
4. Open your web browser and navigate to `http://localhost:5000`

## Deployment

### Deploy to Heroku

1. Install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Login to Heroku:
   ```bash
   heroku login
   ```
3. Create a new Heroku app:
   ```bash
   heroku create your-app-name
   ```
4. Set environment variables:
   ```bash
   heroku config:set MET_API_KEY=your_key_here
   heroku config:set AIC_API_KEY=your_key_here
   # Set other API keys as needed
   ```
5. Deploy:
   ```bash
   git push heroku main
   ```

### Deploy to Render

1. Create a new Web Service on [Render](https://render.com)
2. Connect your GitHub repository
3. Set the following:
   - Build Command: `pip install -r requirements.txt && python -m spacy download en_core_web_lg`
   - Start Command: `gunicorn app:app`
4. Add environment variables in the Render dashboard
5. Deploy

### Deploy to PythonAnywhere

1. Create an account on [PythonAnywhere](https://www.pythonanywhere.com)
2. Upload your code or clone from GitHub
3. Create a new web app using Flask
4. Set up your virtual environment and install requirements
5. Configure your WSGI file to point to your app
6. Add environment variables through the dashboard

## Data Sources

The app now searches across multiple major art collections:

- Metropolitan Museum of Art
- Art Institute of Chicago
- Harvard Art Museums
- Yale University Art Gallery
- Rijksmuseum
- Smithsonian
- Victoria and Albert Museum
- MoMA
- Tate
- Centre Pompidou
- Guggenheim
- Whitney Museum
- LACMA
- Stanford Museums
- Princeton Art Museum
- Oxford Museums
- Google Arts & Culture
- Europeana
- Digital Public Library of America

## Special Features

### Historical Period Detection

The app includes special handling for historical periods, with enhanced search capabilities for:

- Cold War (1947-1991)
- World Wars (WWI & WWII)
- Civil Rights Movement
- Industrial Revolution
- Renaissance
- Medieval Period
- Victorian Era
- And many more...

For historical period searches, the app will:
1. Prioritize artwork created during the actual time period
2. Include relevant contextual works from shortly after the period
3. Consider period-specific keywords and themes
4. Include modern artistic interpretations of historical events

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

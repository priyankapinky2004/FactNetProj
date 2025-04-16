# FactNet - Fact-Checking Platform

FactNet is a web platform for fact-checking news articles using NLP techniques and news aggregation. It allows users to verify the accuracy of content by comparing it with trusted sources.

## Features

- **News Aggregation**: Automated collection of articles from trusted sources (BBC, Reuters)
- **Article Categorization**: NLP-based categorization of news into topics (Politics, Tech, Health, etc.)
- **Fact Checking**: Compare user-submitted content with trusted articles to determine factual accuracy
- **User Management**: Login with Google OAuth 2.0, save articles, and provide feedback
- **Voting System**: Upvote/downvote articles based on perceived accuracy

## Tech Stack

### Backend
- Django REST Framework
- MongoDB (via Djongo)
- NLP: sentence-transformers, NLTK

### Frontend
- React
- Tailwind CSS
- Axios for API calls

### Infrastructure
- Docker & Docker Compose

## Project Structure

```
factnet/
├── backend/                         # Django backend
│   ├── factnet_api/                 # Main Django project
│   ├── articles/                    # Articles app
│   ├── users/                       # Users app
│   └── requirements.txt             # Python dependencies
│
├── frontend/                        # React frontend
│   ├── public/                      # Static assets
│   ├── src/                         # React source code
│   └── package.json                 # NPM dependencies
│
├── scripts/                         # Standalone Python scripts
│   ├── news_aggregator.py           # News collection
│   ├── news_categorizer.py          # Article categorization
│   ├── similarity_checker.py        # Fact-checking module
│   └── requirements.txt             # Script dependencies
│
├── docker-compose.yml               # Docker Compose config
├── Dockerfile.backend               # Backend container
├── Dockerfile.frontend              # Frontend container
├── Dockerfile.scripts               # Scripts container
└── .env.example                     # Example environment variables
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- (Optional) MongoDB for local development
- (Optional) Node.js and Python for local development

### Running with Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/factnet.git
   cd factnet
   ```

2. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Update the `.env` file with your settings, especially Google OAuth credentials if you want to use Google login.

4. Build and start the Docker containers:
   ```bash
   docker-compose up -d
   ```

5. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - MongoDB: localhost:27017

### Running Scripts Manually

You can run the news aggregator and categorizer scripts manually:

```bash
docker-compose run news-aggregator python news_aggregator.py
docker-compose run news-aggregator python news_categorizer.py
```

## Development

### Backend Development

```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend Development

```bash
cd frontend
npm install
npm start
```

## API Endpoints

### Articles
- `GET /api/articles/` - List all articles
- `GET /api/articles/:id/` - Get article details
- `POST /api/articles/fact_check/` - Submit article for fact checking
- `POST /api/articles/:id/vote/` - Vote on an article

### Auth
- `POST /api/token/` - Get JWT token
- `POST /api/token/refresh/` - Refresh JWT token
- `POST /api/auth/google/` - Login with Google
- `GET /api/auth/profile/` - Get user profile

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with open-source technologies
- Uses NLP techniques for content similarity analysis
- Designed for educational purposes
# Portfolio Simulator

A React-based single-page web application for comparing up to 3 investment portfolios over a 35-year simulation period. Designed for EU/Romanian investors using UCITS-compliant ETFs and Romanian government bonds.

## Features

- **Portfolio Builder**: Create and compare up to 3 portfolios with customizable asset allocations
- **Scenario Configuration**: Three pre-defined scenarios (Pessimistic, Average, Optimistic) with customizable parameters
- **35-Year Simulation**: Track capital growth, income generation, and asset allocation over time
- **Visual Analytics**: Multiple chart types including capital growth, monthly income, income breakdown, and asset allocation
- **Data Persistence**: All portfolios and scenarios are automatically saved to a SQLite database

## Tech Stack

- **Frontend**: React 18+, TypeScript, Recharts, Tailwind CSS
- **Backend**: FastAPI (Python), SQLAlchemy, SQLite
- **Containerization**: Docker, Docker Compose, Nginx

## Project Structure

```
.
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py      # FastAPI application
│   │   ├── database.py  # Database configuration
│   │   ├── models.py    # SQLAlchemy models
│   │   └── schemas.py   # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── docker/
│   ├── Dockerfile       # Production frontend build
│   ├── Dockerfile.dev   # Development frontend
│   └── nginx.conf       # Nginx configuration
├── src/
│   ├── components/      # React components
│   ├── data/           # Initial data (templates, scenarios)
│   ├── hooks/          # Custom React hooks
│   ├── services/       # API service
│   ├── types/          # TypeScript types
│   └── utils/          # Utility functions
├── docker-compose.yml      # Production setup
├── docker-compose.dev.yml  # Development setup
└── package.json
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local development without Docker)

### Development

1. **Start development environment**:
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

2. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

3. **Development features**:
   - Hot reloading for both frontend and backend
   - SQLite database stored in Docker volume
   - CORS enabled for local development

### Production

1. **Build and start production environment**:
   ```bash
   docker-compose up --build -d
   ```

2. **Access the application**:
   - Frontend: http://localhost:80
   - Backend API: http://localhost:8000

### Local Development (without Docker)

1. **Backend**:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

2. **Frontend**:
   ```bash
   npm install
   npm start
   ```

## API Endpoints

- `GET /api/health` - Health check
- `GET /api/data/load` - Load all portfolios and scenarios
- `POST /api/data/save` - Save portfolios and scenarios
- `DELETE /api/data/clear` - Clear all data (for testing)

## Data Persistence

- All portfolio configurations and scenario settings are automatically saved to SQLite database
- Data persists across container restarts via Docker volumes
- Auto-save triggers 1 second after any change
- Save status indicator shows current save state

## Portfolio Assets

- **VWCE**: Vanguard FTSE All-World UCITS ETF
- **TVBETETF**: Romanian Government Bond ETF
- **VGWD**: Vanguard FTSE All-World High Dividend Yield UCITS ETF
- **FIDELIS**: Romanian Government Bonds (FIDELIS)

## License

Private project

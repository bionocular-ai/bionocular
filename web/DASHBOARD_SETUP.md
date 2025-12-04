# Clinical Trials Dashboard - Setup Guide

## Overview

The dashboard is a modern, interactive interface for browsing and exploring 1000+ processed oncology abstracts. It's built with Next.js, TanStack Query, TanStack Table, and Shadcn/UI.

## Architecture

### Frontend Stack
- **Next.js 16** (App Router) - React framework
- **TanStack Query** - Data fetching, caching, and synchronization
- **TanStack Table** - High-performance table component
- **Shadcn/UI** - Professional UI component library
- **TypeScript** - Type safety

### Backend Integration
- **FastAPI** - Python backend API
- **PostgreSQL** - Database for storing processed abstracts

## Features

1. **Data Table Dashboard** (`/dashboard`)
   - Browse 1000+ clinical trial abstracts
   - Filter by title
   - Pagination support
   - Clickable NCT IDs for detailed views

2. **Trial Detail View** (`/trial/[id]`)
   - Full trial information
   - Metadata display
   - Document information

## Setup Instructions

### 1. Backend Setup

Ensure your FastAPI backend is running:

```bash
cd melanoma
# Start your FastAPI server (adjust command based on your setup)
uvicorn src.app.api:app --reload --port 8000
```

The backend should expose:
- `GET /trials` - List all trials with pagination
- `GET /trials/{id}` - Get specific trial details

### 2. Frontend Setup

```bash
cd web
npm install
npm run dev
```

The frontend will run on `http://localhost:3000`

### 3. Environment Variables

Create a `.env.local` file in the `web` directory (optional):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

If not set, it defaults to `http://localhost:8000`

## Usage

1. **Access the Dashboard**
   - Navigate to `http://localhost:3000/dashboard`
   - Or click the "Dashboard" button in the navigation

2. **Browse Trials**
   - Use the search box to filter by title
   - Click on an NCT ID to view detailed information
   - Use pagination controls to navigate through results

3. **View Trial Details**
   - Click any NCT ID in the table
   - View comprehensive trial information
   - Navigate back using the "Back" button

## Project Structure

```
web/
├── src/
│   ├── app/
│   │   ├── dashboard/
│   │   │   └── page.tsx          # Main dashboard page
│   │   ├── trial/
│   │   │   └── [id]/
│   │   │       └── page.tsx      # Trial detail page
│   │   ├── layout.tsx            # Root layout with QueryProvider
│   │   └── page.tsx              # Landing page
│   ├── components/
│   │   ├── providers/
│   │   │   └── query-provider.tsx # TanStack Query provider
│   │   ├── TrialDataTable.tsx    # Main data table component
│   │   └── ui/                   # Shadcn UI components
│   └── lib/
│       ├── api.ts                # API client and types
│       └── utils.ts              # Utility functions
```

## API Endpoints

### GET /trials
Returns a paginated list of trials.

**Query Parameters:**
- `skip` (int, default: 0) - Number of records to skip
- `limit` (int, default: 100) - Maximum number of records to return

**Response:**
```json
{
  "trials": [
    {
      "id": "uuid",
      "nct_id": "NCT12345678",
      "title": "Trial Title",
      "phase": "Phase 3",
      "sponsor": "Sponsor Name",
      "status": "Recruiting",
      "abstract_id": "12345",
      "cancer_type": "Melanoma",
      "year": 2024
    }
  ],
  "total": 1000,
  "skip": 0,
  "limit": 100
}
```

### GET /trials/{id}
Returns detailed information about a specific trial.

**Response:**
```json
{
  "id": "uuid",
  "original_filename": "abstract.pdf",
  "storage_path": "/path/to/file",
  "type": "abstract",
  "upload_date": "2024-01-01T00:00:00Z",
  "hash": "sha256hash",
  "status": "ingested",
  "metadata": {
    "nct_number": "NCT12345678",
    "title": "Trial Title",
    "phase": "Phase 3",
    ...
  }
}
```

## Future Enhancements

- [ ] Add graphs and visualizations using Tremor (when React 19 compatibility is available)
- [ ] Implement AI chat interface with RAG capabilities
- [ ] Add advanced filtering options
- [ ] Export functionality (CSV, JSON)
- [ ] Real-time updates
- [ ] User authentication and authorization

## Troubleshooting

### Backend Connection Issues
- Ensure the FastAPI server is running on port 8000
- Check CORS settings if accessing from a different origin
- Verify the `NEXT_PUBLIC_API_URL` environment variable

### Build Errors
- Run `npm install` to ensure all dependencies are installed
- Check TypeScript errors with `npm run build`
- Verify all imports are correct

### Data Not Loading
- Check browser console for API errors
- Verify backend endpoints are accessible
- Check network tab for failed requests

